"""Runs: build, override, negotiate, then hold for sign-off and log checks.

Runs live in memory in one process, keyed by run ID, and used sign-off tokens are
per process. Both vanish on restart and are not shared between workers. The oldest
runs are dropped past `MAX_RUNS`. Each run's evidence log is also a JSONL file, which
outlives the run; log checks read that file, not this process's memory.

A run has one final decision: approved, rejected or taken over. The check and its
log entry happen together under the run's lock.

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
from typing import Any, Final, Self

from pydantic import Field, model_validator

from app.api import adapter
from app.api.catalogue import Catalogue
from app.api.evaluation import DEFAULT_RESULTS_DIR
from app.api.wire import (
    ALREADY_DECIDED,
    CardView,
    DealView,
    DecisionResult,
    FinalDecision,
    Injection,
    NoDealView,
    RemovedPackage,
    RunLog,
    RunView,
    SignoffResult,
    StateChanged,
    VerifyLogResult,
)
from app.config import Settings
from app.negotiation.agents.base import ModelClient
from app.negotiation.card import Reached, decision_card, reached_from_result
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
from app.negotiation.log import (
    EvidenceLog,
    LogEntry,
    VerifyResult,
    load_entries,
    verify_entries,
)
from app.negotiation.options import PackageBoundError, enumerate_packages
from app.negotiation.protocol import Mode, NegotiationResult, run_negotiation
from app.negotiation.recording import DEFAULT_RECORDINGS_DIR, RecordingClient
from app.negotiation.rules import ALL_RULES, check_package, rule_ids
from app.negotiation.rules.atc import RUNWAY_CLOSED
from app.negotiation.signoff import (
    SignOffRequest,
    SignOffStatus,
    field_versions,
    sign_off,
    state_version,
)

MAX_RUNS: Final = 500
# One append-only file per run, git-ignored. Sign-off anchors and log checks read it.
DEFAULT_LOGS_DIR: Final = Path(__file__).resolve().parents[2] / "run_logs"
MAX_FREE_TEXT_CHARS: Final = 2_000
WRONG_DECISION_KIND: Final = "WRONG_DECISION_KIND"
DECISION_KINDS: Final = frozenset({"signoff", "plan_rejected", "case_taken_over"})
# One package per distinct set of failing rules; the total is reported beside it.
MAX_REMOVED_SHOWN: Final = 12
_UNKNOWN_RESOURCE: Final = "INJECTED-UNKNOWN"
# The fuel rule also reports these, which are about coherence and not fuel.
_INCIDENTAL_UNITS: Final = frozenset({"impossible actions", "min of delay"})
_BLOCK_MARGIN_MIN: Final = 2_880

_TRIGGER_REASONS: Final = {
    "fault": "FALLBACK_AFTER_FAULT",
    "turn_cap_no_agreement": "FALLBACK_NO_CONSENSUS",
}

type Judged = tuple[Package, tuple[Violation, ...]]


class ApiError(Exception):
    """Refused for a stated reason. `status` is the HTTP code."""

    def __init__(self, status: int, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.code = code


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


class _DecisionRequest(FrozenModel):
    decided_by: str

    @model_validator(mode="after")
    def _names_a_person(self) -> Self:
        if not self.decided_by.strip():
            raise ValueError("decided_by must name the person")
        return self


class RejectRequest(_DecisionRequest):
    reason: str | None = Field(default=None, max_length=MAX_FREE_TEXT_CHARS)


class TakeOverRequest(_DecisionRequest):
    note: str | None = Field(default=None, max_length=MAX_FREE_TEXT_CHARS)


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
    # Held until the tanks are empty, however thin the burn rate.
    fuel = scenario.fuel_on_board_kg.value or 0
    burn = max(scenario.hold_burn_kg_per_min.value or 1, 1)
    yield package(runway_id, earliest + fuel // burn + 1, gate_id)
    yield package(runway_id, earliest - 1, gate_id)
    yield package(_UNKNOWN_RESOURCE, earliest, gate_id)
    yield package(runway_id, earliest, _UNKNOWN_RESOURCE)


def _candidates(scenario: Scenario) -> Iterator[Package]:
    try:
        yield from enumerate_packages(scenario)
    except PackageBoundError:
        pass
    yield from _constructed_candidates(scenario)


def _is_the_limit_itself(violation: Violation) -> bool:
    """A real limit broken, not missing data or the fuel rule's coherence checks."""
    return (
        violation.cause is ViolationCause.CONSTRAINT
        and violation.unit not in _INCIDENTAL_UNITS
    )


def injection_scenario(scenario: Scenario, rule_id: str) -> tuple[Scenario, str | None]:
    """What an injected plan is judged against, and any runway closed only for that.

    With every runway open, a closed-runway plan cannot exist, so one runway is
    closed for this check alone. The run itself still uses `scenario`, and the
    response and the log both name the runway.
    """
    runways = scenario.runways.value or ()
    if rule_id != RUNWAY_CLOSED or not runways or any(r.closed for r in runways):
        return scenario, None
    runway_id = runways[0].runway_id
    closed = apply_state_change(scenario, StateChange(closed_runways=(runway_id,)))
    return closed, runway_id


def build_injected(
    scenario: Scenario, rule_id: str, *, real: Scenario | None = None
) -> Judged | None:
    """A package the named rule stops, preferring a real limit over missing data.

    None if no candidate makes that rule fire on this scenario: the control was
    not reached, and the caller says so rather than claiming a catch. When `scenario`
    was altered for the check, `real` is the run's own: the plan must be illegal
    there too, so that it can never also be the plan the run chose.
    """
    rule = next(r for r in ALL_RULES if r.rule_id == rule_id)
    chosen: Package | None = None
    fallback: Package | None = None
    for package in _candidates(real or scenario):
        found = rule.check(scenario, package)
        if real is not None and not check_package(real, package):
            continue
        if any(_is_the_limit_itself(v) for v in found):
            chosen = package
            break
        if found and fallback is None:
            fallback = package
    chosen = chosen or fallback
    if chosen is None:
        return None

    # The named rule's real limit first, so the catch reads as what was asked for.
    def order(violation: Violation) -> tuple[bool, bool]:
        return (violation.rule_id != rule_id, not _is_the_limit_itself(violation))

    return chosen, tuple(sorted(check_package(scenario, chosen), key=order))


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
    log_path: Path
    scenario: Scenario
    # None for a no-deal run. Only ever a package from `run_negotiation`: sign-off
    # takes it from here, never from the client, and no unguarded result reaches it.
    package: Package | None
    # How the plan was chosen, from the protocol result. Never from the client.
    reached: Reached | None
    anchor: str
    # Guards the state, every decision and its log entry as one step.
    lock: threading.Lock = field(default_factory=threading.Lock)
    final: FinalDecision | None = None

    def stored(self) -> tuple[tuple[LogEntry, ...], VerifyResult]:
        """The log as it is on disk, checked against the anchor. A file that cannot
        even be parsed is invalid, with the entries this process remembers."""
        result = self.log.verify(self.anchor)
        try:
            return load_entries(self.log_path), result
        except ValueError:
            return self.log.entries, result


class RunService:
    def __init__(
        self,
        settings: Settings,
        *,
        recordings_dir: Path = DEFAULT_RECORDINGS_DIR,
        results_dir: Path = DEFAULT_RESULTS_DIR,
        logs_dir: Path = DEFAULT_LOGS_DIR,
        live_client: ModelClient | None = None,
    ) -> None:
        self.settings = settings
        self.recordings_dir = recordings_dir
        self.results_dir = results_dir
        self.logs_dir = logs_dir
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

        run_id = uuid.uuid4().hex
        log_path = self.logs_dir / f"{run_id}.jsonl"
        log = EvidenceLog(log_path)
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
        injected: Judged | None = None
        closed_for_check: str | None = None
        if inject is not None:
            judged_on, closed_for_check = injection_scenario(scenario, inject)
            injected = build_injected(
                judged_on,
                inject,
                real=scenario if closed_for_check is not None else None,
            )
        injection = None
        if inject is not None:
            injection = Injection(
                rule_id=inject,
                status="STOPPED" if injected else "NOT_REACHED",
                package_id=injected[0].terms_hash if injected else None,
                closed_for_check=closed_for_check,
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
        reached: Reached | None = None
        card: CardView | None = None
        if isinstance(decision, Deal):
            package = decision.package
            reached = reached_from_result(
                result.path, result.faults, model_off=trigger == "llm_off"
            )
            built = decision_card(
                scenario,
                decision,
                violations=check_package(scenario, package),
                how_reached=reached,
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
            view=view,
            log=log,
            log_path=log_path,
            scenario=scenario,
            package=package,
            reached=reached,
            anchor=log.head,
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
        package = record.package
        reached = record.reached
        if package is None or reached is None:
            raise ApiError(
                409,
                "This run has no plan to sign: it ended in no deal.",
                WRONG_DECISION_KIND,
            )
        with record.lock:
            # Replaying the exact approval keeps sign-off's own REFUSED_ALREADY_USED.
            replay = record.final == "APPROVED" and request.token in self._used_tokens
            if record.final is not None and not replay:
                head = self._log_refused(record, "signoff", request.decided_by)
                card = record.view.card
                assert card is not None
                return adapter.already_decided(
                    package, card.card_hash, record.final, head
                )
            outcome = sign_off(
                request,
                package,
                record.scenario,
                record.log,
                self._used_tokens,
                reached=reached,
            )
            if outcome.status is SignOffStatus.APPROVED:
                record.final = "APPROVED"
            return adapter.signoff_result(outcome, package, record.scenario)

    @staticmethod
    def _log_refused(record: RunRecord, attempted: str, decided_by: str) -> str:
        """Caller holds the run's lock. Refusals are evidence, as sign-off's are."""
        return record.log.append(
            "decision_refused",
            {
                "status": ALREADY_DECIDED,
                "attempted": attempted,
                "final_decision": record.final,
                "decided_by": decided_by,
                "issued": False,
            },
        ).entry_hash

    def reject(self, run_id: str, request: RejectRequest) -> DecisionResult:
        """Records a rejection. Issues nothing, so it does not re-run the rules."""
        record = self._record(run_id)
        decision = record.view.decision
        card = record.view.card
        if not isinstance(decision, DealView) or card is None:
            raise ApiError(
                409,
                "This run has no plan to reject: it ended in no deal.",
                WRONG_DECISION_KIND,
            )
        with record.lock:
            if record.final is not None:
                head = self._log_refused(record, "reject", request.decided_by)
                return DecisionResult(
                    status=ALREADY_DECIDED, final_decision=record.final, log_head=head
                )
            entry = record.log.append(
                "plan_rejected",
                {
                    "package_id": decision.terms_hash,
                    "package_name": card.package_name,
                    "card_hash": card.card_hash,
                    "decided_by": request.decided_by,
                    "unverified_reason": request.reason or None,
                    "has_unverified_reason": bool(request.reason),
                    "issued": False,
                },
            )
            record.final = "REJECTED"
            return DecisionResult(
                status="REJECTED", final_decision="REJECTED", log_head=entry.entry_hash
            )

    def take_over(self, run_id: str, request: TakeOverRequest) -> DecisionResult:
        """Records that a person has the case. No approval or request is created."""
        record = self._record(run_id)
        decision = record.view.decision
        if not isinstance(decision, NoDealView):
            raise ApiError(
                409,
                "This run has a plan: approve or reject it instead.",
                WRONG_DECISION_KIND,
            )
        with record.lock:
            if record.final is not None:
                head = self._log_refused(record, "take_over", request.decided_by)
                return DecisionResult(
                    status=ALREADY_DECIDED, final_decision=record.final, log_head=head
                )
            entry = record.log.append(
                "case_taken_over",
                {
                    # SYSTEM_FAULT and NOTHING_LEGAL stay distinct in the evidence.
                    "reason_type": decision.reason_type.value,
                    "decided_by": request.decided_by,
                    "unverified_note": request.note or None,
                    "has_unverified_note": bool(request.note),
                    "issued": False,
                },
            )
            record.final = "TAKEN_OVER"
            return DecisionResult(
                status="TAKEN_OVER",
                final_decision="TAKEN_OVER",
                log_head=entry.entry_hash,
            )

    def log(self, run_id: str) -> RunLog:
        record = self._record(run_id)
        with record.lock:
            entries, result = record.stored()
            return RunLog(
                entries=tuple(adapter.log_entry_view(e) for e in entries),
                verify=adapter.verify_view(result),
                head=record.log.head,
            )

    def verify_log(self, run_id: str, request: VerifyRequest) -> VerifyLogResult:
        """With `tamper`, checks an edited copy. The real log is never altered."""
        record = self._record(run_id)
        with record.lock:
            stored, real = record.stored()
            head = record.log.head
        entries = list(stored)
        tampered_seq: int | None = None
        checked = real
        if request.tamper and entries:
            # The last decision when there is one, else an entry from the middle.
            decisions = [
                i for i, entry in enumerate(entries) if entry.kind in DECISION_KINDS
            ]
            tampered_seq = decisions[-1] if decisions else len(entries) // 2
            target = entries[tampered_seq]
            entries[tampered_seq] = replace(
                target, payload={**deepcopy(dict(target.payload)), "tampered": True}
            )
            checked = verify_entries(entries, record.anchor)
        return VerifyLogResult(
            **adapter.verify_view(checked).model_dump(),
            tampered_copy=request.tamper,
            tampered_seq=tampered_seq,
            real_log_valid=real.valid,
            head=head,
        )
