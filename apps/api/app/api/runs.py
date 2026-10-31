"""Runs: build, override, negotiate, then hold for sign-off and log checks.

Runs live in memory in one process, keyed by run ID, and used sign-off tokens are
per process. Both vanish on restart and are not shared between workers. The oldest
runs are dropped past `MAX_RUNS`.

An injected unsafe package is judged by the same `check_package` the protocol
uses. It is never offered to an agent and never held as the run's package, so
sign-off cannot reach it, and a run that ended on it is refused outright.
"""

import threading
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from pydantic import Field

from app.api import adapter
from app.api.catalogue import Catalogue
from app.api.evaluation import DEFAULT_RESULTS_DIR
from app.api.wire import (
    CardView,
    Injection,
    RemovedPackage,
    RunLog,
    RunView,
    SignoffResult,
    StateChanged,
    VerifyLogResult,
)
from app.config import Settings
from app.negotiation.agents.base import ModelClient
from app.negotiation.card import decision_card
from app.negotiation.contracts import (
    ArrivalSlot,
    Deal,
    FlightPlanAction,
    FrozenModel,
    GateOccupancy,
    Package,
    Runway,
    Scenario,
    Sourced,
    Violation,
    ViolationCause,
)
from app.negotiation.log import EvidenceLog, verify_entries
from app.negotiation.options import PackageBoundError, enumerate_packages
from app.negotiation.protocol import Mode, NegotiationResult, run_negotiation
from app.negotiation.recording import DEFAULT_RECORDINGS_DIR, RecordingClient
from app.negotiation.rules import ALL_RULES, check_package, rule_ids
from app.negotiation.signoff import (
    SignOffRequest,
    field_versions,
    sign_off,
    state_version,
)

MAX_RUNS: Final = 500
# One package per distinct set of failing rules; the total is reported beside it.
MAX_REMOVED_SHOWN: Final = 12
# Far enough past any window that a package held this long runs out of fuel.
_FUEL_EXHAUSTING_DELAY_MIN: Final = 100_000
_UNKNOWN_RESOURCE: Final = "INJECTED-UNKNOWN"
_BLOCK_MARGIN_MIN: Final = 2_880

_TRIGGER_REASONS: Final = {
    "fault": "FALLBACK_AFTER_FAULT",
    "turn_cap_no_agreement": "FALLBACK_NO_CONSENSUS",
}

type Judged = tuple[Package, tuple[Violation, ...]]


class ApiError(Exception):
    """Refused for a stated reason. `status` is the HTTP code."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class StateChange(FrozenModel):
    closed_runways: tuple[str, ...] = ()
    closed_gates: tuple[str, ...] = ()


class Overrides(StateChange):
    inject_unsafe: str | None = None


class RunRequest(FrozenModel):
    scenario_id: str
    mode: Mode
    overrides: Overrides = Field(default_factory=Overrides)


class VerifyRequest(FrozenModel):
    tamper: bool = False


def _rebuild(scenario: Scenario, updates: dict[str, Sourced[Any]]) -> Scenario:
    """A new validated `Scenario`; the original is never touched."""
    fields = {name: getattr(scenario, name) for name in Scenario.model_fields}
    return Scenario(**{**fields, **updates})


def apply_state_change(scenario: Scenario, change: StateChange) -> Scenario:
    """Close runways and block gates. A blocked gate is an occupancy over the whole
    planning horizon, since a `Gate` has no closed flag: the gate rule stops it."""
    runways = scenario.runways.value or ()
    gates = scenario.gates.value or ()
    unknown = sorted(
        ({*change.closed_runways} - {r.runway_id for r in runways})
        | ({*change.closed_gates} - {g.gate_id for g in gates})
    )
    if unknown:
        raise ApiError(422, f"Unknown runway or gate: {', '.join(unknown)}")

    updates: dict[str, Sourced[Any]] = {}
    if change.closed_runways:
        updates["runways"] = Sourced(
            value=tuple(
                Runway(
                    runway_id=r.runway_id,
                    closed=r.closed or r.runway_id in change.closed_runways,
                    parallel_group=r.parallel_group,
                )
                for r in runways
            ),
            provenance=scenario.runways.provenance,
        )
    if change.closed_gates:
        occupancies = scenario.gate_occupancies.value or ()
        present = {o.flight_id for o in occupancies}
        earliest = scenario.earliest_arrival_min.value or 0
        latest = scenario.latest_arrival_min.value or earliest
        blocks = tuple(
            GateOccupancy(
                gate_id=gate_id,
                flight_id=f"{adapter.BLOCKED_PREFIX}{gate_id}",
                start_min=earliest - _BLOCK_MARGIN_MIN,
                end_min=latest + _BLOCK_MARGIN_MIN,
            )
            for gate_id in dict.fromkeys(change.closed_gates)
            if f"{adapter.BLOCKED_PREFIX}{gate_id}" not in present
        )
        updates["gate_occupancies"] = Sourced(
            value=(*occupancies, *blocks),
            provenance=scenario.gate_occupancies.provenance,
        )
    return _rebuild(scenario, updates) if updates else scenario


def _constructed_candidates(scenario: Scenario) -> Iterator[Package]:
    """Packages outside the enumeration, for rules it can never break by itself."""
    earliest = scenario.earliest_arrival_min.value or 0
    runways = scenario.runways.value or ()
    gates = scenario.gates.value or ()
    taxi = scenario.taxi_in_min.value or 0
    runway_id = runways[0].runway_id if runways else _UNKNOWN_RESOURCE
    gate_id = gates[0].gate_id if gates else _UNKNOWN_RESOURCE

    def package(runway: str, time_min: int, gate: str) -> Package:
        return Package(
            slot=ArrivalSlot(runway_id=runway, time_min=time_min),
            gate_id=gate,
            action=FlightPlanAction.HOLD,
        )

    for other in scenario.other_arrivals.value or ():
        yield package(other.runway_id, other.time_min, gate_id)
    for occupancy in scenario.gate_occupancies.value or ():
        yield package(runway_id, occupancy.start_min - taxi, occupancy.gate_id)
    yield package(runway_id, earliest + _FUEL_EXHAUSTING_DELAY_MIN, gate_id)
    yield package(runway_id, earliest - 1, gate_id)
    yield package(_UNKNOWN_RESOURCE, earliest, gate_id)
    yield package(runway_id, earliest, _UNKNOWN_RESOURCE)


def _candidates(scenario: Scenario) -> Iterator[Package]:
    try:
        yield from enumerate_packages(scenario)
    except PackageBoundError:
        pass
    yield from _constructed_candidates(scenario)


def build_injected(scenario: Scenario, rule_id: str) -> Judged | None:
    """A package the named rule stops, preferring a real limit over missing data.

    None if no candidate makes that rule fire on this scenario: the control was
    not reached, and the caller says so rather than claiming a catch.
    """
    rule = next(r for r in ALL_RULES if r.rule_id == rule_id)
    chosen: Package | None = None
    for package in _candidates(scenario):
        found = rule.check(scenario, package)
        if any(v.cause is ViolationCause.CONSTRAINT for v in found):
            chosen = package
            break
        if found and chosen is None:
            chosen = package
    if chosen is None:
        return None
    # The named rule first, so the catch reads as the control the user asked for.
    judged = sorted(check_package(scenario, chosen), key=lambda v: v.rule_id != rule_id)
    return chosen, tuple(judged)


def removed_by_rules(scenario: Scenario) -> tuple[list[Judged], int]:
    """One illegal package per distinct failure, and how many were illegal in all."""
    try:
        packages = enumerate_packages(scenario)
    except PackageBoundError:
        return [], 0
    shown: dict[frozenset[str], Judged] = {}
    total = 0
    for package in packages:
        violations = check_package(scenario, package)
        if not violations:
            continue
        total += 1
        key = frozenset(v.rule_id for v in violations)
        if key not in shown and len(shown) < MAX_REMOVED_SHOWN:
            shown[key] = (package, violations)
    return list(shown.values()), total


def _trigger(result: NegotiationResult) -> str | None:
    for event in result.events:
        if event.kind == "fallback":
            trigger = event.payload.get("trigger")
            return str(trigger) if trigger is not None else None
    return None


def _reason_codes(result: NegotiationResult, trigger: str | None) -> tuple[str, ...]:
    """Codes for `card.py` templates. Agents' own codes have no template, so they
    are shown on their turn as unverified and not on the card."""
    if result.path == "consensus":
        return ()
    return (_TRIGGER_REASONS.get(trigger or "", "FALLBACK_LOWEST_COST"),)


def _removed_views(
    scenario: Scenario, result: NegotiationResult, injected: Judged | None
) -> tuple[tuple[RemovedPackage, ...], int]:
    turn = 1 if result.turns else None
    shown, total = removed_by_rules(scenario)
    views: list[RemovedPackage] = []
    injected_id = injected[0].terms_hash if injected else None
    if injected is not None:
        views.append(
            adapter.removed_package(
                scenario, injected[0], injected[1], turn=turn, injected=True
            )
        )
    views.extend(
        adapter.removed_package(scenario, package, found, turn=turn, injected=False)
        for package, found in shown
        if package.terms_hash != injected_id
    )
    return tuple(views), total


@dataclass(slots=True)
class RunRecord:
    view: RunView
    log: EvidenceLog
    scenario: Scenario
    # None for a no-deal run. Only ever a package from `run_negotiation`.
    package: Package | None
    anchor: str
    lock: threading.Lock = field(default_factory=threading.Lock)


class RunService:
    def __init__(
        self,
        settings: Settings,
        *,
        recordings_dir: Path = DEFAULT_RECORDINGS_DIR,
        results_dir: Path = DEFAULT_RESULTS_DIR,
        live_client: ModelClient | None = None,
    ) -> None:
        self.settings = settings
        self.recordings_dir = recordings_dir
        self.results_dir = results_dir
        self.catalogue = Catalogue(recordings_dir)
        self._live_client = live_client
        self._runs: OrderedDict[str, RunRecord] = OrderedDict()
        self._lock = threading.Lock()
        self._used_tokens: set[str] = set()

    def _record(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            raise ApiError(
                404,
                "Unknown run. Runs live in memory in one process, so a restart "
                "forgets them. Make a new recovery plan.",
            )
        return record

    def _client(self, mode: Mode) -> ModelClient | None:
        if mode == "recorded":
            return RecordingClient(directory=self.recordings_dir)
        return self._live_client if mode == "live" else None

    def create_run(self, request: RunRequest) -> RunView:
        if request.mode == "live" and not self.settings.ALLOW_LIVE:
            raise ApiError(
                403,
                "Live mode is off, so no model call was made and nothing was spent. "
                "Set ALLOW_LIVE=1 on the API to enable it.",
            )
        overrides = request.overrides
        inject = overrides.inject_unsafe
        if inject is not None and inject not in rule_ids():
            raise ApiError(422, f"Unknown rule to inject: {inject}")
        entry = self.catalogue.get(request.scenario_id)
        if entry is None:
            raise ApiError(404, f"Unknown scenario: {request.scenario_id}")
        scenario = apply_state_change(
            entry.scenario,
            StateChange(
                closed_runways=overrides.closed_runways,
                closed_gates=overrides.closed_gates,
            ),
        )

        log = EvidenceLog()
        log.append(
            "run_context",
            {
                "scenario_id": request.scenario_id,
                "mode": request.mode,
                "state_version": state_version(scenario),
                "closed_runways": list(overrides.closed_runways),
                "closed_gates": list(overrides.closed_gates),
                "inject_unsafe": inject,
            },
        )
        injected = build_injected(scenario, inject) if inject is not None else None
        injection = None
        if inject is not None:
            injection = Injection(
                rule_id=inject,
                status="STOPPED" if injected else "NOT_REACHED",
                package_id=injected[0].terms_hash if injected else None,
            )
            log.append(
                "injected_unsafe",
                {
                    **injection.model_dump(),
                    "stopped_by": (
                        sorted({v.rule_id for v in injected[1]}) if injected else []
                    ),
                },
            )

        result = run_negotiation(
            scenario, request.mode, sink=log, client=self._client(request.mode)
        )
        decision = result.decision
        if (
            injected is not None
            and isinstance(decision, Deal)
            and decision.package.terms_hash == injected[0].terms_hash
        ):
            # The rules stopped it, so this cannot happen. Fail closed if it does.
            raise ApiError(500, "An injected unsafe plan reached a deal. Run refused.")

        version = state_version(scenario)
        trigger = _trigger(result)
        package: Package | None = None
        card: CardView | None = None
        if isinstance(decision, Deal):
            package = decision.package
            built = decision_card(
                scenario,
                decision,
                violations=check_package(scenario, package),
                reason_codes=_reason_codes(result, trigger),
                state_version=version,
            )
            card = adapter.card_view(built, package, scenario)
            log.append(
                "card_shown",
                {
                    "package_name": built.package_name,
                    "terms_hash": built.terms_hash,
                    "card_hash": built.card_hash,
                    "state_version": version,
                },
            )

        removed, removed_total = _removed_views(scenario, result, injected)
        run_id = uuid.uuid4().hex
        view = RunView(
            run_id=run_id,
            scenario_id=request.scenario_id,
            mode=request.mode,
            state_version=version,
            field_versions=dict(field_versions(scenario)),
            path=result.path,
            fallback_trigger=trigger,
            turns=tuple(adapter.turn_view(t) for t in result.turns),
            removed_packages=removed,
            removed_total=removed_total,
            decision=(
                adapter.deal_view(decision)
                if isinstance(decision, Deal)
                else adapter.no_deal_view(decision, scenario)
            ),
            card=card,
            model_notes=adapter.model_notes_view(result.model_notes),
            faults=tuple(adapter.fault_view(f) for f in result.faults),
            log_head=log.head,
            airport=adapter.airport_view(scenario),
            injection=injection,
        )
        record = RunRecord(
            view=view, log=log, scenario=scenario, package=package, anchor=log.head
        )
        with self._lock:
            self._runs[run_id] = record
            while len(self._runs) > MAX_RUNS:
                self._runs.popitem(last=False)
        return view

    def change_state(self, run_id: str, change: StateChange) -> StateChanged:
        record = self._record(run_id)
        with record.lock:
            before = state_version(record.scenario)
            record.scenario = apply_state_change(record.scenario, change)
            after = state_version(record.scenario)
            record.log.append(
                "state_change",
                {
                    "closed_runways": list(change.closed_runways),
                    "closed_gates": list(change.closed_gates),
                    "state_version_before": before,
                    "state_version_after": after,
                },
            )
            return StateChanged(
                state_version=after,
                field_versions=dict(field_versions(record.scenario)),
                log_head=record.log.head,
            )

    def sign_off(self, run_id: str, request: SignOffRequest) -> SignoffResult:
        record = self._record(run_id)
        if record.package is None:
            raise ApiError(409, "This run has no plan to sign: it ended in no deal.")
        with record.lock:
            outcome = sign_off(
                request,
                record.package,
                record.scenario,
                record.log,
                self._used_tokens,
            )
            return adapter.signoff_result(outcome, record.package, record.scenario)

    def log(self, run_id: str) -> RunLog:
        record = self._record(run_id)
        return RunLog(
            entries=tuple(adapter.log_entry_view(e) for e in record.log.entries),
            verify=adapter.verify_view(record.log.verify(record.anchor)),
            head=record.log.head,
        )

    def verify_log(self, run_id: str, request: VerifyRequest) -> VerifyLogResult:
        """With `tamper`, checks an edited copy. The real log is never altered."""
        record = self._record(run_id)
        entries = list(record.log.entries)
        tampered_seq: int | None = None
        if request.tamper:
            tampered_seq = len(entries) // 2
            target = entries[tampered_seq]
            entries[tampered_seq] = replace(
                target, payload={**deepcopy(dict(target.payload)), "tampered": True}
            )
        checked = adapter.verify_view(verify_entries(entries, record.anchor))
        return VerifyLogResult(
            **checked.model_dump(),
            tampered_copy=request.tamper,
            tampered_seq=tampered_seq,
            real_log_valid=record.log.verify(record.anchor).valid,
            head=record.log.head,
        )
