"""Real DOT rows offered to the dashboard, with stable IDs.

A fixed, seeded pool is sampled once per process, so an ID means the same row
for any `limit` and across restarts. Rows that have a complete recording come
first; "complete" is tested by replaying the row, not guessed from file names.
"""

import json
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from itertools import zip_longest
from pathlib import Path
from typing import Final

from app.api import adapter
from app.api.wire import LookupResult, ScenarioSummary
from app.negotiation import dot
from app.negotiation.agents.base import FaultKind
from app.negotiation.contracts import Scenario
from app.negotiation.dot import Cause, DotRow, FlightQuery
from app.negotiation.protocol import run_negotiation
from app.negotiation.recording import RecordingClient
from app.negotiation.scenario import build_scenario

logger = logging.getLogger(__name__)

POOL_SIZE: Final = 200
POOL_SEED: Final = 0
SCENARIO_SEED: Final = 0
# Bounds the replay check. A row must already match a brief to reach it.
MAX_RECORDING_CANDIDATES: Final = 200

_BRIEF_FLIGHT = re.compile(
    r'"flight_id":\s*\{\s*"provenance":\s*"\w+",\s*"value":\s*"([^"]+)"'
)
_BRIEF_EARLIEST = re.compile(
    r'"earliest_arrival_min":\s*\{\s*"provenance":\s*"\w+",\s*"value":\s*(-?\d+)'
)
_DOT_FLIGHT = re.compile(r"[A-Z0-9]{2}\d+")

DATA_YEAR: Final = 2015
MAX_LOOKUP_RESULTS: Final = 20
# Looked-up rows kept for runs. A forgotten one is simply found again from its ID.
MAX_FOUND_ENTRIES: Final = 1_000
_ROW_ID = re.compile(
    r"DOT-(\d{4})(\d{2})(\d{2})-([A-Z0-9]{2})(\d{1,4})-([A-Z]{3})([A-Z]{3})-s"
    + str(SCENARIO_SEED)
)


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    summary: ScenarioSummary
    scenario: Scenario


def recorded_briefs(directory: Path) -> frozenset[tuple[str, int]]:
    """(flight ID, earliest arrival) from the briefs of the recordings on disk. A
    flight number recurs through the year; the pair narrows it to its real rows."""
    found: set[tuple[str, int]] = set()
    for path in directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            messages = document["request"]["messages"]
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("skipping unreadable recording %s", path.name)
            continue
        for message in messages:
            content = str(message.get("content", ""))
            flight = _BRIEF_FLIGHT.search(content)
            earliest = _BRIEF_EARLIEST.search(content)
            if flight is not None and earliest is not None:
                found.add((flight.group(1), int(earliest.group(1))))
    return frozenset(found)


def replays_cleanly(scenario: Scenario, directory: Path) -> bool:
    """True when recordings answer every call this scenario makes."""
    result = run_negotiation(
        scenario, "recorded", client=RecordingClient(directory=directory)
    )
    return result.model_calls > 0 and not any(
        fault.kind is FaultKind.RECORDING_MISS for fault in result.faults
    )


class Catalogue:
    """Loaded once, on first use. A missing CSV raises `dot.DotError` every time."""

    def __init__(self, recordings_dir: Path) -> None:
        self._recordings_dir = recordings_dir
        self._lock = threading.Lock()
        self._entries: dict[str, CatalogueEntry] | None = None
        self._briefs: frozenset[tuple[str, int]] | None = None
        self._found: OrderedDict[str, CatalogueEntry] = OrderedDict()

    def _recording_briefs(self) -> frozenset[tuple[str, int]]:
        if self._briefs is None:
            self._briefs = recorded_briefs(self._recordings_dir)
        return self._briefs

    def _recorded_entries(self) -> list[CatalogueEntry]:
        briefs = self._recording_briefs()
        flights = {flight for flight, _ in briefs if _DOT_FLIGHT.fullmatch(flight)}
        if not flights:
            return []  # nothing can match a DOT row, so skip scanning the file
        entries: list[CatalogueEntry] = []
        tried = 0
        for row in dot.iter_eligible_rows():
            if row.flight_id not in flights:
                continue
            scenario = build_scenario(row, SCENARIO_SEED)
            earliest = scenario.earliest_arrival_min.value
            if earliest is None or (row.flight_id, earliest) not in briefs:
                continue
            tried += 1
            if tried > MAX_RECORDING_CANDIDATES:
                logger.warning("recording check stopped at the candidate bound")
                break
            if replays_cleanly(scenario, self._recordings_dir):
                entries.append(_entry(row, scenario, has_recording=True))
        return entries

    def _load(self) -> dict[str, CatalogueEntry]:
        by_cause: dict[Cause, list[DotRow]] = {"weather": [], "late_aircraft": []}
        for row in dot.sample_rows(POOL_SIZE, POOL_SEED):
            by_cause[row.cause].append(row)
        # Interleaved, so any limit shows both causes.
        pool = [
            row
            for pair in zip_longest(by_cause["weather"], by_cause["late_aircraft"])
            for row in pair
            if row is not None
        ]
        entries: dict[str, CatalogueEntry] = {}
        for recorded in self._recorded_entries():
            entries.setdefault(recorded.summary.scenario_id, recorded)
        for row in pool:
            scenario = build_scenario(row, SCENARIO_SEED)
            entry = _entry(row, scenario, has_recording=False)
            # The ID names date, flight and route: a repeat cannot be told apart.
            entries.setdefault(entry.summary.scenario_id, entry)
        return entries

    def entries(self) -> dict[str, CatalogueEntry]:
        with self._lock:
            if self._entries is None:
                self._entries = self._load()
            return self._entries

    def summaries(self, cause: Cause | None, limit: int) -> list[ScenarioSummary]:
        rows = [entry.summary for entry in self.entries().values()]
        if cause is not None:
            rows = [summary for summary in rows if summary.cause == cause]
        return rows[:limit]

    def get(self, scenario_id: str) -> CatalogueEntry | None:
        """A row in the sampled pool, or any other eligible row named by its ID."""
        known = self.entries().get(scenario_id)
        if known is not None:
            return known
        with self._lock:
            found = self._found.get(scenario_id)
        if found is not None:
            return found
        match = _ROW_ID.fullmatch(scenario_id)
        if match is None:
            return None
        year, month, day, airline, number, origin, destination = match.groups()
        try:
            when = date(int(year), int(month), int(day))
        except ValueError:
            return None
        rows = dot.find_eligible(
            FlightQuery(when, int(number), airline, origin, destination)
        )
        return self._entry_for(rows[0]) if rows else None

    def _entry_for(self, row: DotRow) -> CatalogueEntry:
        """The same seed and parameters as the pool, so a row's ID means one plan."""
        scenario = build_scenario(row, SCENARIO_SEED)
        scenario_id = scenario.scenario_id.value
        entries = self.entries()
        assert scenario_id is not None
        if scenario_id in entries:
            return entries[scenario_id]
        with self._lock:
            found = self._found.get(scenario_id)
            briefs = self._recording_briefs()
        if found is not None:
            return found
        earliest = scenario.earliest_arrival_min.value
        recorded = (
            earliest is not None
            and (row.flight_id, earliest) in briefs
            and replays_cleanly(scenario, self._recordings_dir)
        )
        entry = _entry(row, scenario, has_recording=recorded)
        with self._lock:
            self._found[scenario_id] = entry
            while len(self._found) > MAX_FOUND_ENTRIES:
                self._found.popitem(last=False)
        return entry

    def eligible_total(self) -> int:
        return dot.eligible_count()

    def lookup(self, query: FlightQuery) -> LookupResult:
        """Any eligible row, or a plain reason why this flight is not one."""
        if query.date.year != DATA_YEAR:
            return _none("outside_dataset", f"The flight data covers {DATA_YEAR} only.")
        if query.date.month == dot.EXCLUDED_MONTH:
            return _none(
                "october_excluded",
                f"October {DATA_YEAR} is excluded from this data, because that "
                "month's airport codes are numeric, not the usual three letters.",
            )
        rows = dot.find_eligible(query)
        if not rows:
            return _not_eligible(query, dot.scheduled_flights(query))
        matches = tuple(
            self._entry_for(row).summary for row in rows[:MAX_LOOKUP_RESULTS]
        )
        return LookupResult(
            status="one" if len(rows) == 1 else "several",
            matches=matches,
            total=len(rows),
            reason=None,
            message=None,
        )


def _none(reason: str, message: str) -> LookupResult:
    return LookupResult.model_validate(
        {
            "status": "none",
            "matches": (),
            "total": 0,
            "reason": reason,
            "message": message,
        }
    )


def _not_eligible(
    query: FlightQuery, scheduled: list[dot.FlightOnFile]
) -> LookupResult:
    """Says which kind of no. Only the classification leaves here, never a delay."""
    if not scheduled:
        return _none(
            "not_in_data",
            f"No flight numbered {query.flight_number} matches that search on "
            f"{query.date.isoformat()} in the {DATA_YEAR} flight data.",
        )
    if any(f.arrived and f.has_tail for f in scheduled):
        return _none(
            "below_thresholds",
            "That flight is in the data, but it is not a disruption case: it did "
            f"not have more than {dot.WEATHER_THRESHOLD_MIN} minutes of weather "
            f"delay or more than {dot.LATE_AIRCRAFT_THRESHOLD_MIN} minutes of "
            "late-aircraft delay.",
        )
    if any(f.arrived for f in scheduled):
        return _none(
            "no_tail_number",
            "That flight is in the data, but it has no aircraft tail number, so "
            "it is not an eligible case.",
        )
    return _none(
        "cancelled_or_diverted",
        "That flight is in the data, but it was cancelled or diverted, so it has "
        "no delay causes and is not an eligible case.",
    )


def _entry(row: DotRow, scenario: Scenario, *, has_recording: bool) -> CatalogueEntry:
    return CatalogueEntry(
        summary=adapter.scenario_summary(row, scenario, has_recording=has_recording),
        scenario=scenario,
    )
