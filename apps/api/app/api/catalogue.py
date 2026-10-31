"""Real DOT rows offered to the dashboard, with stable IDs.

A fixed, seeded pool is sampled once per process, so an ID means the same row
for any `limit` and across restarts. Rows that have a complete recording come
first; "complete" is tested by replaying the row, not guessed from file names.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Final

from app.api import adapter
from app.api.wire import ScenarioSummary
from app.negotiation import dot
from app.negotiation.agents.base import FaultKind
from app.negotiation.contracts import Scenario
from app.negotiation.dot import Cause, DotRow
from app.negotiation.protocol import run_negotiation
from app.negotiation.recording import RecordingClient
from app.negotiation.scenario import build_scenario

logger = logging.getLogger(__name__)

POOL_SIZE: Final = 200
POOL_SEED: Final = 0
SCENARIO_SEED: Final = 0
# Bounds the replay check when a recorded flight number recurs through the year.
MAX_RECORDING_CANDIDATES: Final = 100

_BRIEF_FLIGHT = re.compile(
    r'"flight_id":\s*\{\s*"provenance":\s*"\w+",\s*"value":\s*"([^"]+)"'
)
_DOT_FLIGHT = re.compile(r"[A-Z0-9]{2}\d+")


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    summary: ScenarioSummary
    scenario: Scenario


def recorded_flights(directory: Path) -> frozenset[str]:
    """Flight IDs named in the briefs of the recordings on disk."""
    found: set[str] = set()
    for path in directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            messages = document["request"]["messages"]
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("skipping unreadable recording %s", path.name)
            continue
        for message in messages:
            found.update(_BRIEF_FLIGHT.findall(str(message.get("content", ""))))
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

    def _recorded_entries(self) -> list[CatalogueEntry]:
        flights = recorded_flights(self._recordings_dir)
        if not any(_DOT_FLIGHT.fullmatch(flight) for flight in flights):
            return []  # nothing can match a DOT row, so skip scanning the file
        entries: list[CatalogueEntry] = []
        tried = 0
        for row in dot.iter_eligible_rows():
            if row.flight_id not in flights:
                continue
            tried += 1
            if tried > MAX_RECORDING_CANDIDATES:
                logger.warning("recording check stopped at the candidate bound")
                break
            scenario = build_scenario(row, SCENARIO_SEED)
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
        return self.entries().get(scenario_id)


def _entry(row: DotRow, scenario: Scenario, *, has_recording: bool) -> CatalogueEntry:
    return CatalogueEntry(
        summary=adapter.scenario_summary(row, scenario, has_recording=has_recording),
        scenario=scenario,
    )
