"""Append-only, hash-chained evidence log.

Each entry commits to the one before it, so editing, deleting, reordering or
inserting an entry breaks the chain at a findable point. A chain on its own
cannot catch a full rewrite: someone who recomputes every hash produces a log
that verifies. Only a head recorded somewhere the rewriter cannot reach (an
anchor) exposes that. Anchoring proves the entries up to the anchor are
unchanged; it says nothing about what was appended after it.

No wall-clock time is read here. A timestamp enters the hash only when the
caller injects a clock, so tests and replays stay deterministic.
"""

import hashlib
import json
import os
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


class LogIntegrityError(ValueError):
    """The stored log does not verify, so nothing may be appended to it."""


class VerifyReason(StrEnum):
    OK = "ok"
    MALFORMED_ENTRY = "malformed_entry"
    SEQ_MISMATCH = "seq_mismatch"  # deleted, reordered or inserted entry
    PREV_HASH_MISMATCH = "prev_hash_mismatch"  # chain link broken
    ENTRY_HASH_MISMATCH = "entry_hash_mismatch"  # entry content edited
    ANCHOR_NOT_FOUND = "anchor_not_found"  # rewritten, truncated or diverged


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no spaces, ASCII, no NaN or Infinity.

    Raises `TypeError` or `ValueError` for anything that is not plain JSON data.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class LogEntry:
    seq: int
    kind: str
    payload: Mapping[str, Any]
    prev_hash: str
    entry_hash: str
    # Present only when the log was given a clock; then it is inside the hash.
    ts: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "seq": self.seq,
            "kind": self.kind,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }
        if self.ts is not None:
            data["ts"] = self.ts
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LogEntry":
        extra = set(data) - {"seq", "kind", "payload", "prev_hash", "entry_hash", "ts"}
        if extra:
            raise LogIntegrityError(f"unexpected entry fields: {sorted(extra)}")
        try:
            return cls(
                seq=data["seq"],
                kind=data["kind"],
                payload=data["payload"],
                prev_hash=data["prev_hash"],
                entry_hash=data["entry_hash"],
                ts=data.get("ts"),
            )
        except KeyError as exc:
            raise LogIntegrityError(f"entry is missing {exc.args[0]}") from exc


@dataclass(frozen=True, slots=True)
class VerifyResult:
    valid: bool
    first_bad_seq: int | None
    reason: str


def compute_entry_hash(
    seq: int, kind: str, payload: Mapping[str, Any], prev_hash: str, ts: str | None
) -> str:
    body: dict[str, Any] = {
        "seq": seq,
        "kind": kind,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    if ts is not None:
        body["ts"] = ts
    return hashlib.sha256(canonical_json(body).encode("ascii")).hexdigest()


def _well_formed(entry: object) -> bool:
    return (
        isinstance(entry, LogEntry)
        and isinstance(entry.seq, int)
        and not isinstance(entry.seq, bool)
        and isinstance(entry.kind, str)
        and isinstance(entry.payload, Mapping)
        and isinstance(entry.prev_hash, str)
        and isinstance(entry.entry_hash, str)
        and (entry.ts is None or isinstance(entry.ts, str))
    )


def verify_entries(
    entries: Sequence[LogEntry], anchored_head: str | None = None
) -> VerifyResult:
    """Check the chain, and the anchor when one is given.

    `first_bad_seq` is the sequence number the first broken entry should have
    had, which for a deletion is the position of the gap. An anchor failure has
    no single bad entry, so `first_bad_seq` is None there.

    Without `anchored_head` a fully recomputed rewrite passes. With it, the
    anchor must be the head of some prefix of the log (the empty prefix
    included), so honest appends after the anchor still verify.
    """
    previous = GENESIS_HASH
    prefix_heads = {GENESIS_HASH}
    for expected_seq, entry in enumerate(entries):
        if not _well_formed(entry):
            return VerifyResult(False, expected_seq, VerifyReason.MALFORMED_ENTRY)
        if entry.seq != expected_seq:
            return VerifyResult(False, expected_seq, VerifyReason.SEQ_MISMATCH)
        if entry.prev_hash != previous:
            return VerifyResult(False, expected_seq, VerifyReason.PREV_HASH_MISMATCH)
        try:
            recomputed = compute_entry_hash(
                entry.seq, entry.kind, entry.payload, entry.prev_hash, entry.ts
            )
        except (TypeError, ValueError):
            return VerifyResult(False, expected_seq, VerifyReason.MALFORMED_ENTRY)
        if entry.entry_hash != recomputed:
            return VerifyResult(False, expected_seq, VerifyReason.ENTRY_HASH_MISMATCH)
        previous = entry.entry_hash
        prefix_heads.add(previous)
    # Only the head of the whole log is not a prefix head of the empty log, so
    # an anchor of GENESIS matches only when nothing was ever anchored past it.
    if anchored_head is not None and anchored_head not in prefix_heads:
        return VerifyResult(False, None, VerifyReason.ANCHOR_NOT_FOUND)
    return VerifyResult(True, None, VerifyReason.OK)


def load_entries(path: Path) -> tuple[LogEntry, ...]:
    """Read a JSONL log without verifying it, so a tampered copy can be shown.

    A line that is not a JSON object raises `LogIntegrityError`.
    """
    if not path.exists():
        return ()
    entries: list[LogEntry] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                raise LogIntegrityError(f"line {number} is blank")
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LogIntegrityError(f"line {number} is not JSON") from exc
            if not isinstance(data, dict):
                raise LogIntegrityError(f"line {number} is not an object")
            entries.append(LogEntry.from_dict(data))
    return tuple(entries)


def _plain(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A deep, detached copy that is guaranteed to be plain JSON data.

    Round-tripping through canonical JSON means later changes to the caller's
    dict cannot reach the stored entry, and tuples become lists as they will on
    reload, so the hash is the same before and after a restart.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    _check_plain(payload)
    return json.loads(canonical_json(dict(payload)))


def _check_plain(value: Any) -> None:
    """Reject what JSON would silently change, such as non-string keys."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("payload keys must be strings")
            _check_plain(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _check_plain(item)


class EvidenceLog:
    """An append-only hash chain, in memory or in a JSONL file.

    With a path, existing entries are loaded and verified; a file that does not
    verify raises `LogIntegrityError` rather than being extended. One process
    may write a file at a time.
    """

    def __init__(
        self, path: Path | None = None, *, clock: Callable[[], str] | None = None
    ) -> None:
        self._path = path
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: list[LogEntry] = []
        if path is not None:
            loaded = load_entries(path)
            result = verify_entries(loaded)
            if not result.valid:
                raise LogIntegrityError(
                    f"{path} does not verify: {result.reason} at seq "
                    f"{result.first_bad_seq}"
                )
            self._entries = list(loaded)

    @property
    def head(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    @property
    def entries(self) -> tuple[LogEntry, ...]:
        return tuple(self._entries)

    def append(self, kind: str, payload: Mapping[str, Any]) -> LogEntry:
        """Add one entry. Nothing is recorded if hashing or writing fails."""
        if not isinstance(kind, str) or not kind:
            raise ValueError("kind must be a non-empty string")
        plain = _plain(payload)
        with self._lock:
            seq = len(self._entries)
            prev_hash = self.head
            ts = self._clock() if self._clock is not None else None
            entry = LogEntry(
                seq=seq,
                kind=kind,
                payload=plain,
                prev_hash=prev_hash,
                entry_hash=compute_entry_hash(seq, kind, plain, prev_hash, ts),
                ts=ts,
            )
            if self._path is not None:
                self._write(entry)
            self._entries.append(entry)
            return entry

    def _write(self, entry: LogEntry) -> None:
        assert self._path is not None
        line = canonical_json(entry.as_dict()) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def verify(self, anchored_head: str | None = None) -> VerifyResult:
        return verify_entries(self.entries, anchored_head)
