"""The one translation from backend structures to the wire shape the UI needs.

Statements shown as fact are taken from `card.py`, never written here. What this
module adds is structure and number formatting: a clock time beside a minute,
and joining the card's own labels and values.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from app.api.wire import (
    ALREADY_DECIDED,
    AirportState,
    CardView,
    DealPackage,
    DealView,
    Fact,
    FaultView,
    FinalDecision,
    LogEntryView,
    ModelNoteView,
    NextLegView,
    NoDealView,
    PackageRef,
    RemovedPackage,
    RequestFact,
    Resource,
    Risk,
    RuleResult,
    ScenarioSummary,
    SignoffResult,
    SignoffTerm,
    Turn,
    TurnResponse,
    VerifyView,
)
from app.negotiation import dot
from app.negotiation.agents.base import Fault
from app.negotiation.card import (
    Card,
    PackageTerm,
    RuleLine,
    RuleStatus,
    authority_terms,
    model_note,
    no_deal_card,
    package_name,
    violation_lines,
)
from app.negotiation.contracts import (
    Deal,
    Domain,
    NoDeal,
    Package,
    Scenario,
    Violation,
)
from app.negotiation.dot import MINUTES_PER_DAY, DotRow
from app.negotiation.log import LogEntry as ChainEntry
from app.negotiation.log import VerifyResult
from app.negotiation.protocol import ModelNote, TurnRecord
from app.negotiation.rules.ground import turnaround_min
from app.negotiation.scenario import earliest_basis, next_leg_of
from app.negotiation.signoff import SignOffOutcome

BLOCKED_PREFIX = "BLOCKED-"

# Where a term's value comes from in the scenario, for its provenance badge. The
# slot's runway is synthetic, which is the weaker of its two parts.
_TERM_FIELDS: Mapping[str, str] = {
    "gate_id": "gates",
    "slot": "runways",
    "action": "decision_point",
}
_DOMAIN_ORDER = tuple(Domain)
# Free text from a model or a person. In the log, never in a summary shown as fact.
_NOTE_FIELDS = frozenset(
    {"unverified_model_note", "unverified_reason", "unverified_note"}
)


def clock(minute: int) -> str:
    """Minutes from the scenario's midnight as a 24-hour string."""
    hours, minutes = divmod(minute % MINUTES_PER_DAY, 60)
    return f"{hours:02d}:{minutes:02d}"


def route(origin: str, destination: str) -> str:
    return f"{origin} to {destination}"


# --- scenarios ---------------------------------------------------------------


def _next_leg_delay(scenario: Scenario) -> int | None:
    """Delay reaching the next leg at the earliest arrival, by the turnaround rule."""
    earliest = scenario.earliest_arrival_min.value
    taxi = scenario.taxi_in_min.value
    depart = scenario.next_departure_min.value
    stay = turnaround_min(scenario)
    if earliest is None or taxi is None or depart is None or stay is None:
        return None
    return max(0, earliest + taxi + stay.value - depart)


def scenario_summary(
    row: DotRow, scenario: Scenario, *, has_recording: bool
) -> ScenarioSummary:
    leg = next_leg_of(row)
    next_leg = None
    if leg is not None:
        next_leg = NextLegView(
            flight_id=leg.flight_id,
            route=route(row.destination_airport, leg.destination),
            scheduled_departure=clock(leg.scheduled_departure_min),
            delay_minutes=_next_leg_delay(scenario),
            provenance=scenario.next_departure_min.provenance,
            delay_provenance=scenario.aircraft_size.provenance,
        )
    scenario_id = scenario.scenario_id.value
    flight_id = scenario.flight_id.value
    assert scenario_id is not None and flight_id is not None
    return ScenarioSummary(
        scenario_id=scenario_id,
        flight_id=flight_id,
        route=route(row.origin_airport, row.destination_airport),
        scheduled_arrival=clock(dot.scheduled_arrival_min(row)),
        cause=row.cause,
        delay_minutes=earliest_basis(row).delay_min,
        delay_provenance=scenario.earliest_arrival_min.provenance,
        next_leg=next_leg,
        has_recording=has_recording,
    )


# --- rules -------------------------------------------------------------------


def rule_result(line: RuleLine) -> RuleResult:
    direction: Literal["at_least", "at_most"] | None = None
    if line.observed is not None and line.limit is not None:
        direction = "at_least" if line.observed < line.limit else "at_most"
    cause: Literal["constraint", "missing_data"] | None = None
    if line.status is RuleStatus.FAIL:
        cause = "constraint"
    elif line.status is RuleStatus.MISSING_DATA:
        cause = "missing_data"
    return RuleResult(
        rule_id=line.rule_id,
        domain=line.domain,
        label=line.description,
        message=line.message,
        source=line.source,
        observed=line.observed,
        limit=line.limit,
        unit=line.unit or "",
        direction=direction,
        status=line.basis_status,
        status_label=line.basis_label,
        result=line.status,
        cause=cause,
    )


def _violation_results(
    scenario: Scenario, violations: Sequence[Violation], package: Package | None
) -> tuple[RuleResult, ...]:
    return tuple(
        rule_result(line) for line in violation_lines(scenario, violations, package)
    )


# --- packages ----------------------------------------------------------------


def _term_value(term: PackageTerm, package: Package) -> str:
    if term.name == "slot":
        return f"{term.value} ({clock(package.slot.time_min)})"
    return term.value


def package_label(package: Package) -> str:
    airline, requests = authority_terms(package)
    terms = "; ".join(
        f"{t.label}: {_term_value(t, package)}" for t in (*airline, *requests)
    )
    return f"{package_name(package)} ({terms})"


def removed_package(
    scenario: Scenario,
    package: Package,
    violations: Sequence[Violation],
    *,
    turn: int | None,
    injected: bool,
) -> RemovedPackage:
    return RemovedPackage(
        package_id=package.terms_hash,
        label=package_label(package),
        removed_in_turn=turn,
        violations=_violation_results(scenario, violations, package),
        injected=injected,
    )


def deal_view(deal: Deal) -> DealView:
    package = deal.package
    return DealView(
        terms_hash=package.terms_hash,
        package=DealPackage(
            package_id=package.terms_hash,
            label=package_label(package),
            runway_id=package.slot.runway_id,
            gate_id=package.gate_id,
        ),
        packages_considered=deal.packages_considered,
        packages_legal=deal.packages_legal,
    )


def no_deal_view(no_deal: NoDeal, scenario: Scenario) -> NoDealView:
    card = no_deal_card(no_deal, scenario)
    nearest = no_deal.nearest_package
    return NoDealView(
        reason_type=no_deal.reason_type,
        binding_rules=tuple(rule_result(line) for line in card.binding_evidence),
        packages_considered=card.packages_considered,
        nearest_package=(
            PackageRef(package_id=nearest.terms_hash, label=package_label(nearest))
            if nearest is not None
            else None
        ),
        nearest_violations=tuple(rule_result(line) for line in card.nearest_rules),
        what_would_change=tuple(c.text for c in card.what_would_have_to_change),
        reason=card.headline,
        what_to_do=card.what_to_do,
    )


# --- the card ----------------------------------------------------------------


def _fact(term: PackageTerm, package: Package, scenario: Scenario) -> Fact:
    return Fact(
        key=term.name,
        label=term.label,
        value=_term_value(term, package),
        provenance=getattr(scenario, _TERM_FIELDS[term.name]).provenance,
    )


def card_view(card: Card, package: Package, scenario: Scenario) -> CardView:
    airline = tuple(_fact(t, package, scenario) for t in card.authority.airline_decides)
    requested = tuple(_fact(t, package, scenario) for t in card.authority.requests_only)
    return CardView(
        card_hash=card.card_hash,
        field_hashes=dict(card.field_hashes),
        package_name=card.package_name,
        action=card.headline,
        action_facts=(*airline, *requested),
        what_to_do=card.what_to_do,
        why=(*card.why, *(r.text for r in card.reasons)),
        risks=tuple(Risk(text=t) for t in card.what_could_go_wrong),
        airline_decisions=airline,
        # The card's own wording sends both requests to ATC.
        requests=tuple(
            RequestFact(**fact.model_dump(), to=Domain.ATC.value.upper())
            for fact in requested
        ),
        authority_notes=card.authority.notes,
        rules=tuple(rule_result(line) for line in card.rules),
        costs=card.costs,
        provenance=card.provenance,
        all_rules_passed=card.all_rules_passed,
    )


# --- the negotiation ---------------------------------------------------------


def _ranking_summary(ranking: Sequence[str], shown: int = 3) -> str:
    """The top package names, in the agent's order. Names only, no prose."""
    return ", ".join(f"PKG-{package_id[:8]}" for package_id in ranking[:shown])


def turn_view(record: TurnRecord) -> Turn:
    return Turn(
        turn=record.turn,
        responses=tuple(
            TurnResponse(
                domain=agent.domain,
                acceptable_count=len(agent.acceptable_package_ids),
                ranking_summary=_ranking_summary(agent.ranking),
                reason_codes=agent.reason_codes,
                public_reason_classes=tuple(
                    dict.fromkeys(
                        d.public_reason.value for d in agent.public_reason_classes
                    )
                ),
            )
            for agent in record.agents
        ),
        intersection_count=len(record.intersection),
    )


def model_notes_view(notes: Sequence[ModelNote]) -> tuple[ModelNoteView, ...]:
    """Grouped by domain in a fixed order, each labelled by `card.model_note`."""
    views: list[ModelNoteView] = []
    for domain in _DOMAIN_ORDER:
        for note in notes:
            if note.domain is domain:
                wrapped = model_note(note.text)
                views.append(
                    ModelNoteView(
                        domain=domain,
                        turn=note.turn,
                        text=wrapped.text,
                        label=wrapped.label,
                    )
                )
    return tuple(views)


def fault_view(fault: Fault) -> FaultView:
    return FaultView(
        kind=fault.kind, domain=fault.domain, turn=fault.turn, message=fault.detail
    )


def airport_view(scenario: Scenario) -> AirportState:
    occupancies = scenario.gate_occupancies.value or ()
    blocked = {o.gate_id for o in occupancies if o.flight_id.startswith(BLOCKED_PREFIX)}
    return AirportState(
        runways=tuple(
            Resource(id=r.runway_id, closed=r.closed)
            for r in scenario.runways.value or ()
        ),
        gates=tuple(
            Resource(id=g.gate_id, closed=g.gate_id in blocked)
            for g in scenario.gates.value or ()
        ),
    )


# --- sign-off and the log ----------------------------------------------------


def signoff_result(
    outcome: SignOffOutcome, package: Package, scenario: Scenario
) -> SignoffResult:
    def terms(items: Sequence[PackageTerm]) -> tuple[SignoffTerm, ...]:
        return tuple(
            SignoffTerm(name=t.name, label=t.label, value=_term_value(t, package))
            for t in items
        )

    return SignoffResult(
        status=outcome.status,
        package_name=outcome.package_name,
        violations=_violation_results(scenario, outcome.violations, package),
        changed_fields=outcome.changed_fields,
        changed_card_fields=outcome.changed_card_fields,
        airline_decisions=terms(outcome.airline_decisions),
        requests=terms(outcome.requests),
        card_hash=outcome.card_hash,
        log_head=outcome.log_head,
    )


def already_decided(
    package: Package, card_hash: str, final: FinalDecision, log_head: str
) -> SignoffResult:
    """The sign-off refusal shape, for a run whose decision is already final."""
    return SignoffResult(
        status=ALREADY_DECIDED,
        final_decision=final,
        package_name=package_name(package),
        violations=(),
        changed_fields=(),
        changed_card_fields=(),
        airline_decisions=(),
        requests=(),
        card_hash=card_hash,
        log_head=log_head,
    )


def _summary(entry: ChainEntry) -> str:
    """The entry's own scalar values. Model prose is left out: it is not a fact."""
    parts: list[str] = []
    for key, value in entry.payload.items():
        if key in _NOTE_FIELDS or value is None:
            continue
        if isinstance(value, list | dict):
            parts.append(f"{key}: {len(value)}")
        else:
            parts.append(f"{key}: {value}")
    return "; ".join(parts)


def log_entry_view(entry: ChainEntry) -> LogEntryView:
    return LogEntryView(
        seq=entry.seq,
        kind=entry.kind,
        summary=_summary(entry),
        hash=entry.entry_hash,
    )


def verify_view(result: VerifyResult) -> VerifyView:
    return VerifyView(
        valid=result.valid,
        first_bad_seq=result.first_bad_seq,
        reason=None if result.valid else str(result.reason),
    )
