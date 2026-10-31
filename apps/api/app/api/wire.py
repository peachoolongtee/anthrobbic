"""What the API may return. Every field is named here and extras are forbidden,
so an as-flown outcome column cannot ride along. Mirrors
`apps/web/src/lib/api-types.ts`.
"""

from typing import Literal

from app.negotiation.agents.base import FaultKind
from app.negotiation.card import CostLine, ProvenanceLine, RuleStatus
from app.negotiation.contracts import Domain, FrozenModel, NoDealReason, Provenance
from app.negotiation.dot import Cause
from app.negotiation.protocol import Mode
from app.negotiation.signoff import SignOffStatus


class NextLegView(FrozenModel):
    flight_id: str
    route: str
    scheduled_departure: str
    # Delay reaching the leg if nothing is done, worked out from the schedule and
    # the turnaround rule. None when an input is unknown. Never the as-flown delay.
    delay_minutes: int | None
    # Of the leg itself, from the same file.
    provenance: Provenance
    # Of `delay_minutes`, which rests on the synthetic aircraft size.
    delay_provenance: Provenance


class ScenarioSummary(FrozenModel):
    scenario_id: str
    flight_id: str
    route: str
    scheduled_arrival: str
    cause: Cause
    # The delay signal knowable at the decision point, not the as-flown delay.
    delay_minutes: int
    delay_provenance: Provenance
    next_leg: NextLegView | None
    has_recording: bool


class PackageRef(FrozenModel):
    package_id: str
    label: str


class RuleResult(FrozenModel):
    rule_id: str
    domain: Domain
    # The requirement, shown when the rule held.
    label: str
    # What the plan does wrong, shown when it failed. None when it held.
    message: str | None
    source: str
    observed: int | None
    limit: int | None
    unit: str
    direction: Literal["at_least", "at_most"] | None
    # The basis of the limit: a `rule_values.Status` value or "scenario_defined".
    status: str
    status_label: str
    # Whether the rule held at this state.
    result: RuleStatus
    cause: Literal["constraint", "missing_data"] | None


class TurnResponse(FrozenModel):
    domain: Domain
    acceptable_count: int
    ranking_summary: str
    # The agent's own codes, unverified. `card.py` has no templates for them.
    reason_codes: tuple[str, ...]
    public_reason_classes: tuple[str, ...]


class Turn(FrozenModel):
    turn: int
    responses: tuple[TurnResponse, ...]
    intersection_count: int


class RemovedPackage(FrozenModel):
    package_id: str
    label: str
    # None when no agent turn ran: code removed it before any model was asked.
    removed_in_turn: int | None
    violations: tuple[RuleResult, ...]
    injected: bool


class DealPackage(FrozenModel):
    package_id: str
    label: str
    runway_id: str
    gate_id: str


class DealView(FrozenModel):
    kind: Literal["DEAL"] = "DEAL"
    terms_hash: str
    package: DealPackage
    packages_considered: int
    packages_legal: int


class NoDealView(FrozenModel):
    kind: Literal["NO_DEAL"] = "NO_DEAL"
    reason_type: NoDealReason
    binding_rules: tuple[RuleResult, ...]
    packages_considered: int
    nearest_package: PackageRef | None
    nearest_violations: tuple[RuleResult, ...]
    what_would_change: tuple[str, ...]
    reason: str
    what_to_do: str


class Fact(FrozenModel):
    key: str
    label: str
    value: str
    provenance: Provenance


class RequestFact(Fact):
    to: str


class Risk(FrozenModel):
    text: str


class CardView(FrozenModel):
    card_hash: str
    field_hashes: dict[str, str]
    package_name: str
    action: str
    action_facts: tuple[Fact, ...]
    what_to_do: tuple[str, ...]
    why: tuple[str, ...]
    risks: tuple[Risk, ...]
    airline_decisions: tuple[Fact, ...]
    requests: tuple[RequestFact, ...]
    authority_notes: tuple[str, ...]
    rules: tuple[RuleResult, ...]
    costs: tuple[CostLine, ...]
    provenance: tuple[ProvenanceLine, ...]
    all_rules_passed: bool


class ModelNoteView(FrozenModel):
    domain: Domain
    turn: int
    text: str
    unverified: Literal[True] = True
    label: str


class FaultView(FrozenModel):
    kind: FaultKind
    domain: Domain | None
    turn: int | None
    message: str


class Resource(FrozenModel):
    id: str
    closed: bool


class AirportState(FrozenModel):
    runways: tuple[Resource, ...]
    gates: tuple[Resource, ...]


class Injection(FrozenModel):
    rule_id: str
    # NOT_REACHED: no package could make this rule fire on this row.
    status: Literal["STOPPED", "NOT_REACHED"]
    package_id: str | None


class RunView(FrozenModel):
    run_id: str
    scenario_id: str
    mode: Mode
    state_version: str
    field_versions: dict[str, str]
    path: Literal["consensus", "fallback", "no_deal"]
    # Why the fallback ran, as the protocol logged it. None if it did not.
    fallback_trigger: str | None
    turns: tuple[Turn, ...]
    removed_packages: tuple[RemovedPackage, ...]
    # Illegal packages in all; `removed_packages` shows one per distinct failure.
    removed_total: int
    decision: DealView | NoDealView
    card: CardView | None
    model_notes: tuple[ModelNoteView, ...]
    faults: tuple[FaultView, ...]
    log_head: str
    airport: AirportState
    injection: Injection | None


class StateChanged(FrozenModel):
    state_version: str
    field_versions: dict[str, str]
    log_head: str


class SignoffTerm(FrozenModel):
    name: str
    label: str
    value: str


class SignoffResult(FrozenModel):
    status: SignOffStatus
    package_name: str
    violations: tuple[RuleResult, ...]
    changed_fields: tuple[str, ...]
    changed_card_fields: tuple[str, ...]
    airline_decisions: tuple[SignoffTerm, ...]
    requests: tuple[SignoffTerm, ...]
    card_hash: str
    log_head: str


class LogEntryView(FrozenModel):
    seq: int
    kind: str
    summary: str
    hash: str


class VerifyView(FrozenModel):
    valid: bool
    first_bad_seq: int | None
    reason: str | None


class RunLog(FrozenModel):
    entries: tuple[LogEntryView, ...]
    verify: VerifyView
    head: str


class VerifyLogResult(VerifyView):
    # True when this result is about a tampered copy, not the real log.
    tampered_copy: bool
    tampered_seq: int | None
    # The real log, checked again afterwards.
    real_log_valid: bool
    head: str


class EvaluationRow(FrozenModel):
    arm: Literal["guarded", "unguarded_model"]
    metric: str
    value: int | float | str
    interval: tuple[float, float] | None
    n: int | None
    evidence_class: str
    commit: str
    mode: str
    seed: int | str


class Evaluation(FrozenModel):
    # "not_yet_run": no output exists. "unreadable": output exists but is not usable.
    status: Literal["ok", "not_yet_run", "unreadable"]
    rows: tuple[EvaluationRow, ...]
    limits: tuple[str, ...]
