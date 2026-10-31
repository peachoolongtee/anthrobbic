"""The evidence log: chain, tamper detection and the limits of an unanchored head."""

import dataclasses
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from app.negotiation.log import (
    GENESIS_HASH,
    EvidenceLog,
    LogEntry,
    LogIntegrityError,
    VerifyReason,
    canonical_json,
    load_entries,
    verify_entries,
)

PAYLOADS: list[tuple[str, dict[str, Any]]] = [
    ("proposal", {"turn": 1, "author": "atc", "package": "PKG-1"}),
    ("response", {"turn": 1, "responder": "pilot", "acceptable": ["PKG-1"]}),
    ("verdict", {"rule_ids": ["ATC-RWY-CLOSED"], "passed": False}),
    ("fault", {"kind": "timeout", "agent": "ground"}),
    ("consensus", {"turn": 2, "package": "PKG-2"}),
]


def build(path: Path | None = None) -> EvidenceLog:
    log = EvidenceLog(path)
    for kind, payload in PAYLOADS:
        log.append(kind, payload)
    return log


def rewrite(
    entries: Sequence[LogEntry],
    edit: Callable[[LogEntry], tuple[str, dict[str, Any]]],
) -> tuple[LogEntry, ...]:
    """A fully recomputed, self-consistent log with some entries changed."""
    forged = EvidenceLog()
    for entry in entries:
        kind, payload = edit(entry)
        forged.append(kind, payload)
    return forged.entries


def replace_at(
    entries: Sequence[LogEntry], index: int, **changes: Any
) -> list[LogEntry]:
    out = list(entries)
    out[index] = dataclasses.replace(out[index], **changes)
    return out


# ------------------------------------------------------------------ basics


def test_empty_log_head_is_genesis() -> None:
    log = EvidenceLog()
    assert log.head == GENESIS_HASH
    assert log.entries == ()
    assert verify_entries(()).valid


def test_append_links_entries() -> None:
    log = build()
    assert [e.seq for e in log.entries] == [0, 1, 2, 3, 4]
    assert log.entries[0].prev_hash == GENESIS_HASH
    for before, after in zip(log.entries, log.entries[1:], strict=False):
        assert after.prev_hash == before.entry_hash
    assert log.head == log.entries[-1].entry_hash
    assert verify_entries(log.entries) == verify_entries(log.entries)
    assert verify_entries(log.entries).valid


def test_same_input_gives_same_chain_with_no_clock() -> None:
    assert build().head == build().head
    assert [e.ts for e in build().entries] == [None] * 5


def test_hash_ignores_payload_key_order() -> None:
    a, b = EvidenceLog(), EvidenceLog()
    a.append("k", {"x": 1, "y": [1, 2]})
    b.append("k", {"y": [1, 2], "x": 1})
    assert a.head == b.head
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_stored_payload_is_detached_from_the_callers_dict() -> None:
    payload: dict[str, Any] = {"items": [1, 2]}
    log = EvidenceLog()
    log.append("k", payload)
    payload["items"].append(3)
    payload["extra"] = True
    assert verify_entries(log.entries).valid
    assert log.entries[0].payload == {"items": [1, 2]}


def test_tuples_hash_like_lists() -> None:
    a, b = EvidenceLog(), EvidenceLog()
    a.append("k", {"x": (1, 2)})
    b.append("k", {"x": [1, 2]})
    assert a.head == b.head


@pytest.mark.parametrize(
    "payload",
    [{"x": {1, 2}}, {"x": float("nan")}, {"x": object()}, {1: "int key"}],
)
def test_non_json_payload_is_rejected_and_nothing_recorded(payload: Any) -> None:
    log = EvidenceLog()
    with pytest.raises((TypeError, ValueError)):
        log.append("k", payload)
    assert log.entries == ()
    assert log.head == GENESIS_HASH


@pytest.mark.parametrize("kind", ["", None, 3])
def test_bad_kind_is_rejected(kind: Any) -> None:
    with pytest.raises(ValueError):
        EvidenceLog().append(kind, {})


# --------------------------------------------------------------- tampering


def test_edited_payload_is_detected_at_that_entry() -> None:
    entries = build().entries
    tampered = replace_at(entries, 2, payload={"rule_ids": [], "passed": True})
    result = verify_entries(tampered)
    assert not result.valid
    assert result.first_bad_seq == 2
    assert result.reason == VerifyReason.ENTRY_HASH_MISMATCH


def test_edited_kind_is_detected() -> None:
    result = verify_entries(replace_at(build().entries, 1, kind="proposal"))
    assert (result.valid, result.first_bad_seq) == (False, 1)
    assert result.reason == VerifyReason.ENTRY_HASH_MISMATCH


def test_deleted_middle_entry_is_detected_at_the_gap() -> None:
    entries = list(build().entries)
    del entries[2]
    result = verify_entries(entries)
    assert (result.valid, result.first_bad_seq) == (False, 2)
    assert result.reason == VerifyReason.SEQ_MISMATCH


def test_deleted_first_entry_is_detected() -> None:
    result = verify_entries(build().entries[1:])
    assert (result.valid, result.first_bad_seq) == (False, 0)


def test_reordered_entries_are_detected() -> None:
    entries = list(build().entries)
    entries[1], entries[2] = entries[2], entries[1]
    result = verify_entries(entries)
    assert (result.valid, result.first_bad_seq) == (False, 1)
    assert result.reason == VerifyReason.SEQ_MISMATCH


def test_inserted_entry_is_detected() -> None:
    entries = list(build().entries)
    # A forged entry with a valid own hash, spliced in after entry 1.
    forged = EvidenceLog()
    forged.append("proposal", {"turn": 1})
    forged.append("response", {"turn": 1})
    fake = forged.append("fabricated", {"x": 1})
    entries.insert(2, fake)
    result = verify_entries(entries)
    assert not result.valid
    assert result.first_bad_seq == 2  # the spliced entry does not link


def test_inserted_entry_with_renumbered_seq_still_breaks_the_chain() -> None:
    entries = list(build().entries)
    fake = LogEntry(
        seq=2,
        kind="fabricated",
        payload={},
        prev_hash=entries[1].entry_hash,
        entry_hash="f" * 64,
    )
    entries.insert(2, fake)
    result = verify_entries(entries)
    assert (result.valid, result.first_bad_seq) == (False, 2)
    assert result.reason == VerifyReason.ENTRY_HASH_MISMATCH


def test_broken_link_is_detected() -> None:
    result = verify_entries(replace_at(build().entries, 3, prev_hash="a" * 64))
    assert (result.valid, result.first_bad_seq) == (False, 3)
    assert result.reason == VerifyReason.PREV_HASH_MISMATCH


def test_forged_hash_without_the_chain_is_detected() -> None:
    result = verify_entries(replace_at(build().entries, 0, entry_hash="b" * 64))
    assert (result.valid, result.first_bad_seq) == (False, 0)


def test_edit_with_rehash_of_one_middle_entry_breaks_the_next_link() -> None:
    entries = build().entries
    forged = EvidenceLog()
    for entry in entries[:2]:
        forged.append(entry.kind, entry.payload)
    forged.append("verdict", {"rule_ids": [], "passed": True})  # edited entry 2
    spliced = [*forged.entries, *entries[3:]]  # original 3 and 4 kept
    result = verify_entries(spliced)
    assert (result.valid, result.first_bad_seq) == (False, 3)
    assert result.reason == VerifyReason.PREV_HASH_MISMATCH


def test_non_entry_objects_are_malformed() -> None:
    result = verify_entries([build().entries[0], "not an entry"])  # type: ignore[list-item]
    assert (result.valid, result.first_bad_seq) == (False, 1)
    assert result.reason == VerifyReason.MALFORMED_ENTRY


def test_non_json_payload_in_a_loaded_entry_is_malformed() -> None:
    result = verify_entries(replace_at(build().entries, 0, payload={"x": {1}}))
    assert (result.valid, result.first_bad_seq) == (False, 0)
    assert result.reason == VerifyReason.MALFORMED_ENTRY


# ------------------------------------------------- anchoring and its limits


def rewritten_log() -> tuple[tuple[LogEntry, ...], tuple[LogEntry, ...]]:
    original = build().entries

    def lie(entry: LogEntry) -> tuple[str, dict[str, Any]]:
        if entry.kind == "verdict":
            return entry.kind, {"rule_ids": [], "passed": True}
        return entry.kind, dict(entry.payload)

    return original, rewrite(original, lie)


def test_full_recomputed_rewrite_passes_without_an_anchor() -> None:
    """The stated limit: a chain alone cannot catch a full rewrite."""
    original, forged = rewritten_log()
    assert forged[2].payload != original[2].payload
    assert forged[-1].entry_hash != original[-1].entry_hash
    assert verify_entries(forged).valid


def test_full_recomputed_rewrite_is_rejected_with_the_anchored_head() -> None:
    original, forged = rewritten_log()
    anchor = original[-1].entry_hash
    result = verify_entries(forged, anchored_head=anchor)
    assert not result.valid
    assert result.reason == VerifyReason.ANCHOR_NOT_FOUND
    assert result.first_bad_seq is None
    assert verify_entries(original, anchored_head=anchor).valid


def test_rewriting_only_the_last_entry_passes_unanchored_and_fails_anchored() -> None:
    original = build().entries
    last = len(original) - 1
    forged = rewrite(
        original, lambda e: (e.kind, {"turn": 9} if e.seq == last else dict(e.payload))
    )
    assert verify_entries(forged).valid
    assert not verify_entries(forged, anchored_head=original[-1].entry_hash).valid


def test_truncation_passes_unanchored_and_fails_anchored() -> None:
    original = build().entries
    truncated = original[:3]
    assert verify_entries(truncated).valid
    assert not verify_entries(truncated, anchored_head=original[-1].entry_hash).valid


def test_anchor_accepts_honest_appends_after_it() -> None:
    log = build()
    anchor = log.head
    log.append("signoff", {"status": "APPROVED"})
    assert verify_entries(log.entries, anchored_head=anchor).valid


def test_anchor_does_not_protect_what_came_after_it() -> None:
    """The anchor fixes the past, not later entries. Say so publicly."""
    log = build()
    anchor = log.head
    log.append("signoff", {"status": "REFUSED"})
    forged = rewrite(
        log.entries,
        lambda e: (e.kind, {"status": "APPROVED"} if e.seq == 5 else dict(e.payload)),
    )
    assert verify_entries(forged, anchored_head=anchor).valid


def test_anchor_still_catches_tampering_before_it() -> None:
    log = build()
    anchor = log.head
    tampered = replace_at(log.entries, 1, payload={"turn": 1})
    assert not verify_entries(tampered, anchored_head=anchor).valid


def test_genesis_anchor_means_the_log_was_empty() -> None:
    assert verify_entries(build().entries, anchored_head=GENESIS_HASH).valid
    assert not verify_entries(build().entries, anchored_head="c" * 64).valid


# --------------------------------------------------------------------- file


def test_file_log_round_trips_and_continues_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    first = build(path)
    reopened = EvidenceLog(path)
    assert reopened.head == first.head
    assert reopened.entries == first.entries
    reopened.append("later", {"n": 1})
    assert len(path.read_text().splitlines()) == 6
    assert EvidenceLog(path).verify(anchored_head=first.head).valid


def test_file_and_memory_logs_have_the_same_head(tmp_path: Path) -> None:
    assert build(tmp_path / "a.jsonl").head == build().head


def test_tampered_file_is_refused_on_open_but_can_be_inspected(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    build(path)
    lines = path.read_text().splitlines()
    record = json.loads(lines[2])
    record["payload"]["passed"] = True
    lines[2] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n")

    with pytest.raises(LogIntegrityError):
        EvidenceLog(path)
    result = verify_entries(load_entries(path))
    assert (result.valid, result.first_bad_seq) == (False, 2)


@pytest.mark.parametrize("bad_line", ["not json", "[1, 2]", ""])
def test_corrupt_line_is_an_integrity_error(tmp_path: Path, bad_line: str) -> None:
    path = tmp_path / "evidence.jsonl"
    build(path)
    with path.open("a") as handle:
        handle.write(bad_line + "\n")
    with pytest.raises(LogIntegrityError):
        EvidenceLog(path)


def test_unexpected_entry_field_is_an_integrity_error(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    build(path)
    lines = path.read_text().splitlines()
    record = json.loads(lines[0])
    record["extra"] = 1
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(LogIntegrityError):
        load_entries(path)


def test_failed_write_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = build(tmp_path / "evidence.jsonl")
    head = log.head

    def boom(entry: LogEntry) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(log, "_write", boom)
    with pytest.raises(OSError):
        log.append("lost", {})
    assert log.head == head
    assert len(log.entries) == 5


# -------------------------------------------------------------------- clock


def test_injected_clock_is_hashed_and_tamper_checked() -> None:
    ticks = iter(["t0", "t1", "t2"])
    log = EvidenceLog(clock=lambda: next(ticks))
    for n in range(3):
        log.append("k", {"n": n})
    assert [e.ts for e in log.entries] == ["t0", "t1", "t2"]
    assert verify_entries(log.entries).valid
    result = verify_entries(replace_at(log.entries, 1, ts="t9"))
    assert (result.valid, result.first_bad_seq) == (False, 1)
    result = verify_entries(replace_at(build().entries, 1, ts="t9"))
    assert not result.valid  # adding a timestamp also changes the hash


def test_clocked_file_survives_reload(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = EvidenceLog(path, clock=lambda: "2026-10-31T09:00:00Z")
    log.append("k", {"n": 1})
    assert EvidenceLog(path).head == log.head


# ------------------------------------------- D2: a failed write rolls back


def test_an_fsync_failure_leaves_file_and_memory_consistent_and_retry_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    before = path.read_bytes()
    head = log.head

    def boom(_: int) -> None:
        raise OSError("fsync failed")

    with monkeypatch.context() as patch:
        patch.setattr("app.negotiation.log.os.fsync", boom)
        with pytest.raises(OSError):
            log.append("signoff", {"status": "APPROVED"})
    # The caller was told it failed, and the file agrees.
    assert path.read_bytes() == before
    assert log.head == head and len(log.entries) == 5

    retried = log.append("signoff", {"status": "APPROVED"})
    assert retried.seq == 5  # not a second line with a repeated seq
    assert [e.seq for e in EvidenceLog(path).entries] == [0, 1, 2, 3, 4, 5]
    assert len(path.read_text().splitlines()) == 6
    reopened = EvidenceLog(path)
    assert reopened.head == log.head == retried.entry_hash
    assert reopened.verify().valid


def test_a_failed_first_write_leaves_no_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "evidence.jsonl"
    log = EvidenceLog(path)

    def boom(_: int) -> None:
        raise OSError("fsync failed")

    with monkeypatch.context() as patch:
        patch.setattr("app.negotiation.log.os.fsync", boom)
        with pytest.raises(OSError):
            log.append("k", {})
    assert path.read_text() == ""
    assert EvidenceLog(path).entries == ()
    assert log.append("k", {}).seq == 0


def test_if_the_rollback_also_fails_the_log_refuses_everything_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = build(tmp_path / "evidence.jsonl")

    def boom(*_: Any) -> None:
        raise OSError("io error")

    with monkeypatch.context() as patch:
        patch.setattr("app.negotiation.log.os.fsync", boom)
        patch.setattr("app.negotiation.log.os.truncate", boom)
        with pytest.raises(OSError):
            log.append("lost", {})
    with pytest.raises(LogIntegrityError):
        log.append("later", {})
    result = log.verify()
    assert not result.valid and result.reason == VerifyReason.LOG_FAILED
    assert len(log.entries) == 5


# --------------------------------------- D3: verify reads the file itself


def edit_line(path: Path, index: int, change: Callable[[dict[str, Any]], None]) -> None:
    lines = path.read_text().splitlines()
    record = json.loads(lines[index])
    change(record)
    lines[index] = canonical_json(record)  # a well-formed, canonical line
    path.write_text("\n".join(lines) + "\n")


def test_verify_reads_the_file_so_a_live_edit_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    assert log.verify().valid
    edit_line(path, 2, lambda r: r["payload"].update(passed=True))
    assert log.entries[2].payload["passed"] is False  # memory is still the old one
    result = log.verify()
    assert (result.valid, result.first_bad_seq) == (False, 2)
    assert result.reason == VerifyReason.ENTRY_HASH_MISMATCH


def test_verify_reports_a_file_cut_short_or_extended_behind_the_logs_back(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:3]) + "\n")
    cut = log.verify()
    assert not cut.valid and cut.reason == VerifyReason.FILE_DIVERGED
    assert cut.first_bad_seq == 3
    # Cut short, the chain is still valid on its own: only the comparison with
    # what was written (or an anchor) can see it.
    assert verify_entries(load_entries(path)).valid
    assert not log.verify(anchored_head=log.head).valid


def test_a_live_edit_stops_further_appends(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    edit_line(path, 1, lambda r: r["payload"].update(turn=9))
    with pytest.raises(LogIntegrityError):
        log.append("later", {})
    assert len(log.entries) == 5
    assert len(path.read_text().splitlines()) == 5


def test_an_appended_foreign_line_stops_further_appends(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    other = EvidenceLog()
    for kind, payload in PAYLOADS:
        other.append(kind, payload)
    extra = other.append("extra", {})
    with path.open("a") as handle:
        handle.write(canonical_json(extra.as_dict()) + "\n")
    with pytest.raises(LogIntegrityError):
        log.append("later", {})


def test_an_untouched_file_keeps_appending_without_error(tmp_path: Path) -> None:
    log = build(tmp_path / "evidence.jsonl")
    for n in range(3):
        log.append("k", {"n": n})
    assert log.verify().valid


def test_a_memory_log_verifies_memory() -> None:
    assert build().verify().valid


# --------------------------------------- L2: only canonical lines verify


def rewrite_line(path: Path, index: int, text: str) -> None:
    lines = path.read_text().splitlines()
    lines[index] = text
    path.write_text("\n".join(lines) + "\n")


def test_a_reformatted_line_fails_verification_though_its_hashes_hold(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    record = json.loads(path.read_text().splitlines()[1])
    rewrite_line(path, 1, json.dumps(record, indent=None))  # spaces after separators
    assert verify_entries(load_entries(path)).valid  # the chain alone is fine
    result = log.verify()
    assert (result.valid, result.first_bad_seq) == (False, 1)
    assert result.reason == VerifyReason.NON_CANONICAL_LINE
    with pytest.raises(LogIntegrityError):
        EvidenceLog(path)


def test_a_duplicate_json_key_fails_verification(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    line = path.read_text().splitlines()[0]
    # A second `kind` key that json.loads would silently resolve to the last one.
    forged = line.replace('"kind":"proposal"', '"kind":"other","kind":"proposal"')
    assert forged != line
    rewrite_line(path, 0, forged)
    assert verify_entries(load_entries(path)).valid
    result = log.verify()
    assert (result.valid, result.first_bad_seq) == (False, 0)
    assert result.reason == VerifyReason.NON_CANONICAL_LINE


def test_crlf_and_a_missing_final_newline_are_not_canonical(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert log.verify().reason == VerifyReason.NON_CANONICAL_LINE
    path.write_bytes(
        b"\n".join(
            line
            for line in path.read_bytes().replace(b"\r\n", b"\n").split(b"\n")
            if line
        )
    )
    assert log.verify().reason == VerifyReason.NON_CANONICAL_LINE


def test_a_broken_line_is_reported_by_verify_not_raised(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    log = build(path)
    rewrite_line(path, 3, "not json")
    result = log.verify()
    assert (result.valid, result.first_bad_seq) == (False, 3)
    assert result.reason == VerifyReason.MALFORMED_ENTRY
