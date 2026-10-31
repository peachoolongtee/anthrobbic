"""What the API may return. Every field is named here and extras are forbidden,
so an as-flown outcome column cannot ride along. Mirrors
`apps/web/src/lib/api-types.ts`.
"""

from typing import Any, Final, Literal

from app.negotiation.agents.base import FaultKind
from app.negotiation.card import CostLine, ProvenanceLine, Reached, RuleStatus
from app.negotiation.contracts import Domain, FrozenModel, NoGoReason, Provenance
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


class LookupResult(FrozenModel):
    # A flight that cannot be run is an answer, not an error: `reason` says which.
    status: Literal["one", "several", "none"]
    # Bounded. The same summary the list shows, so no outcome column can ride along.
    matches: tuple[ScenarioSummary, ...]
    # Matches in all, which may be more than `matches` holds.
    total: int
    reason: (
        Literal[
            "outside_dataset",
            "october_excluded",
            "not_in_data",
            "below_thresholds",
            "cancelled_or_diverted",
            "no_tail_number",
        ]
        | None
    )
    message: str | None


class EligibleCount(FrozenModel):
    eligible_total: int


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


class NoGoView(FrozenModel):
    kind: Literal["NO_GO"] = "NO_GO"
    reason_type: NoGoReason
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
    how_reached: Reached
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
    # A runway closed only to judge this plan, when none was closed. Not the run's.
    closed_for_check: str | None = None


class RunView(FrozenModel):
    run_id: str
    scenario_id: str
    mode: Mode
    state_version: str
    field_versions: dict[str, str]
    path: Literal["consensus", "fallback", "no_go"]
    # Why the fallback ran, as the protocol logged it. None if it did not.
    fallback_trigger: str | None
    turns: tuple[Turn, ...]
    removed_packages: tuple[RemovedPackage, ...]
    # Illegal packages in all; `removed_packages` shows one per distinct failure.
    removed_total: int
    decision: DealView | NoGoView
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


# One per run. Refused decisions and refused sign-offs do not set it.
type FinalDecision = Literal["APPROVED", "REJECTED", "TAKEN_OVER"]
ALREADY_DECIDED: Final = "REFUSED_ALREADY_DECIDED"


class DecisionResult(FrozenModel):
    status: Literal["REJECTED", "TAKEN_OVER", "REFUSED_ALREADY_DECIDED"]
    # What stands for this run now, whoever made it.
    final_decision: FinalDecision
    log_head: str


class SignoffResult(FrozenModel):
    # `signoff.py`'s statuses unchanged, plus the run-level refusal it cannot see.
    status: SignOffStatus | Literal["REFUSED_ALREADY_DECIDED"]
    final_decision: FinalDecision | None = None
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


class DeclinedReason(FrozenModel):
    package_id: str
    public_reason: str


class AgentMessage(FrozenModel):
    """One agent's structured reply on one turn. Its own reason codes are
    unverified; no free text or prompt is included."""

    domain: Domain
    acceptable_package_ids: tuple[str, ...]
    ranking: tuple[str, ...]
    reason_codes: tuple[str, ...]
    declined: tuple[DeclinedReason, ...]
    prompt_hash: str
    served_by: str


class ConsensusTurn(FrozenModel):
    turn: int
    agents: tuple[AgentMessage, ...]
    intersection: tuple[str, ...]


class HowReached(FrozenModel):
    path: Literal["consensus", "fallback", "no_go"]
    # What the card states. None for a no-go, which has no plan.
    reached: Reached | None
    # Why the fallback ran, as the protocol logged it. None if it did not.
    fallback_trigger: str | None


class ExportedEntry(FrozenModel):
    """A log entry exactly as stored, so `verify_entries` accepts the list."""

    seq: int
    kind: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
    ts: str | None = None


class ExportedLog(FrozenModel):
    entries: tuple[ExportedEntry, ...]
    # The head now, and the head recorded when the run was made.
    head: str
    anchored_head: str
    # The stored file checked against the anchored head. Invalid is reported here
    # and the entries are still returned as they are on disk.
    verify: VerifyView


class EvaluationReference(FrozenModel):
    """Which offline evaluation sits beside this run. Not a property of the run."""

    commits: tuple[str, ...]
    modes: tuple[str, ...]


class ConsensusLog(FrozenModel):
    """The downloadable record of one run. Built only from the run and its log."""

    format: Literal["consensus-log/1"] = "consensus-log/1"
    run_id: str
    mode: Mode
    scenario_id: str
    # None if the scenario is no longer in the catalogue.
    scenario: ScenarioSummary | None
    field_provenance: dict[str, Provenance]
    state_version: str
    field_versions: dict[str, str]
    airport: AirportState
    injection: Injection | None
    turns: tuple[ConsensusTurn, ...]
    removed_packages: tuple[RemovedPackage, ...]
    removed_total: int
    decision: DealView | NoGoView
    card: CardView | None
    how_reached: HowReached
    faults: tuple[FaultView, ...]
    final_decision: FinalDecision | None
    log: ExportedLog
    evaluation: EvaluationReference | None


class EvaluationRow(FrozenModel):
    arm: Literal["guarded", "unguarded_model"]
    metric: str
    value: int | float | str
    interval: tuple[float, float] | None
    interval_text: str | None
    n: int | None
    evidence_class: str
    panel: str
    note: str
    commit: str
    mode: str
    seed: int | str


class Evaluation(FrozenModel):
    # "not_yet_run": no output exists. "unreadable": output exists but is not usable.
    status: Literal["ok", "not_yet_run", "unreadable"]
    rows: tuple[EvaluationRow, ...]
    limits: tuple[str, ...]
    # Controls that failed in the run. Shown first: they outrank every number.
    failures: tuple[str, ...] = ()
