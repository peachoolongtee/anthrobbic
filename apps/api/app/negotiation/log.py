"""Append-only, hash-chained evidence log.

Each entry commits to the one before it, so editing, deleting, reordering or
inserting an entry breaks the chain at a findable point. A chain on its own
cannot catch a full rewrite (someone who recomputes every hash produces a log
that verifies) or the removal of entries from the tail (what is left is still a
valid chain). Only a head recorded somewhere the rewriter cannot reach (an
anchor) exposes either. Anchoring proves the entries up to the anchor are
unchanged; it says nothing about what was appended after it.

A file log is also checked as bytes: every line must be the canonical JSON of
its entry, so reformatting or duplicate keys fail even when the hashes hold.

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
    """The stored log does not verify, so nothing may be appended to it.

    `line` is the 0-based line of the file at fault, when one can be named.
    """

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.line = line


class VerifyReason(StrEnum):
    OK = "ok"
    MALFORMED_ENTRY = "malformed_entry"
    SEQ_MISMATCH = "seq_mismatch"  # deleted, reordered or inserted entry
    PREV_HASH_MISMATCH = "prev_hash_mismatch"  # chain link broken
    ENTRY_HASH_MISMATCH = "entry_hash_mismatch"  # entry content edited
    ANCHOR_NOT_FOUND = "anchor_not_found"  # rewritten, truncated or diverged
    NON_CANONICAL_LINE = "non_canonical_line"  # file line is not canonical JSON
    FILE_DIVERGED = "file_diverged"  # the file no longer matches what was written
    LOG_FAILED = "log_failed"  # a failed write could not be rolled back


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


def _load(path: Path) -> tuple[tuple[LogEntry, ...], int | None]:
    """Parse a JSONL log. Also returns the 0-based index of the first line that
    is not the canonical JSON of its entry, or None."""
    if not path.exists():
        return (), None
    entries: list[LogEntry] = []
    non_canonical: int | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(handle):
            line = raw[:-1] if raw.endswith("\n") else raw
            if not line.strip():
                raise LogIntegrityError(f"line {index + 1} is blank", index)
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LogIntegrityError(f"line {index + 1} is not JSON", index) from exc
            if not isinstance(data, dict):
                raise LogIntegrityError(f"line {index + 1} is not an object", index)
            try:
                entries.append(LogEntry.from_dict(data))
                canonical = canonical_json(data) + "\n" == raw
            except (LogIntegrityError, TypeError, ValueError) as exc:
                raise LogIntegrityError(
                    f"line {index + 1} is malformed", index
                ) from exc
            if not canonical and non_canonical is None:
                non_canonical = index
    return tuple(entries), non_canonical


def load_entries(path: Path) -> tuple[LogEntry, ...]:
    """Read a JSONL log without verifying it, so a tampered copy can be shown.

    A line that is not a JSON object raises `LogIntegrityError`.
    """
    return _load(path)[0]


def verify_file(
    path: Path,
    anchored_head: str | None = None,
    expected: Sequence[LogEntry] | None = None,
) -> VerifyResult:
    """Verify the file itself: the chain, the anchor, canonical lines and,
    when `expected` is given, that the file still holds exactly those entries."""
    try:
        entries, non_canonical = _load(path)
    except LogIntegrityError as exc:
        return VerifyResult(False, exc.line, VerifyReason.MALFORMED_ENTRY)
    result = verify_entries(entries, anchored_head)
    if not result.valid:
        return result
    if non_canonical is not None:
        return VerifyResult(False, non_canonical, VerifyReason.NON_CANONICAL_LINE)
    if expected is not None and tuple(expected) != entries:
        shared = min(len(expected), len(entries))
        first = next((i for i in range(shared) if expected[i] != entries[i]), shared)
        return VerifyResult(False, first, VerifyReason.FILE_DIVERGED)
    return result


def _stat_key(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_size, stat.st_mtime_ns


def _plain(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A deep, detached copy that is guaranteed to be plain JSON data.

    Round-tripping through canonical JSON means later changes to the caller's
    dict cannot reach the stored entry, and tuples become lists as they will on
    reload, so the hash is the same before and after a restart.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    _check_plain(payload)
    plain: dict[str, Any] = json.loads(canonical_json(dict(payload)))
    return plain


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
    verify raises `LogIntegrityError` rather than being extended. Before each
    append the file is re-verified if its size or modification time moved since
    this log last wrote it, so a live edit stops further appends; `verify()`
    always reads the whole file. A write that fails is rolled back by
    truncation; if even that fails the log refuses all further appends. One
    process may write a file at a time.
    """

    def __init__(
        self, path: Path | None = None, *, clock: Callable[[], str] | None = None
    ) -> None:
        self._path = path
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: list[LogEntry] = []
        self._failed: str | None = None
        self._known_stat: tuple[int, int] | None = None
        if path is not None:
            result = verify_file(path)
            if not result.valid:
                raise LogIntegrityError(
                    f"{path} does not verify: {result.reason} at seq "
                    f"{result.first_bad_seq}"
                )
            self._entries = list(load_entries(path))
            self._known_stat = _stat_key(path)

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
            if self._failed is not None:
                raise LogIntegrityError(
                    f"log is unusable after a failed write: {self._failed}"
                )
            self._check_file_unchanged()
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

    def _check_file_unchanged(self) -> None:
        if self._path is None or _stat_key(self._path) == self._known_stat:
            return
        result = verify_file(self._path, expected=self._entries)
        if not result.valid:
            raise LogIntegrityError(
                f"{self._path} changed and does not verify: {result.reason} at "
                f"seq {result.first_bad_seq}"
            )
        self._known_stat = _stat_key(self._path)

    def _write(self, entry: LogEntry) -> None:
        assert self._path is not None
        line = canonical_json(entry.as_dict()) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        size = self._path.stat().st_size if self._path.exists() else 0
        try:
            with self._path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException as exc:
            # The caller is told this failed, so the file must not say it worked.
            try:
                os.truncate(self._path, size)
            except OSError:
                self._failed = type(exc).__name__
            raise
        self._known_stat = _stat_key(self._path)

    def verify(self, anchored_head: str | None = None) -> VerifyResult:
        """Verify what is stored: the file when there is one, not memory."""
        if self._failed is not None:
            return VerifyResult(False, len(self._entries), VerifyReason.LOG_FAILED)
        if self._path is None:
            return verify_entries(self.entries, anchored_head)
        return verify_file(self._path, anchored_head, expected=self._entries)
