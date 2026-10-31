"""Decision and no-go cards. Every statement shown as fact is built here.

Text comes from templates in this file and structured values (integers,
enums, scenario identifiers). Nothing a model wrote can reach a `Card`: the
builders take codes that are looked up in `REASON_CODES`, never prose, and they
ignore the free-text `message` and `source` strings on a `Violation`. Model
prose lives in a `ModelNote`, a different type that `Card` cannot hold, and it
is rendered below the facts under a label that says it is unverified.

`card_hash` covers the facts that follow from the scenario and the package. It
leaves out the reasons (explanations), the state version (checked separately)
and the selection counts (which need the whole enumeration), so a changed
explanation or model note never moves it.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    CostBreakdown,
    Deal,
    Domain,
    FrozenModel,
    NoGo,
    NoGoReason,
    Package,
    Provenance,
    Scenario,
    Sourced,
    Violation,
    ViolationCause,
)
from app.negotiation.rules import ALL_RULES

# ---------------------------------------------------------------- names


def package_name(package: Package) -> str:
    """The one name for a package, in the card, the log and the sign-off."""
    return f"PKG-{package.terms_hash[:8]}"


class PackageTerm(FrozenModel):
    """One term. `name` is the stable key; `label` is the heading to show over
    `value`, which never repeats the label's word."""

    name: str
    label: str
    value: str


_TERM_LABELS: Mapping[str, str] = MappingProxyType(
    {"gate_id": "Gate", "slot": "Arrival slot", "action": "Flight-plan action"}
)


def _term(package: Package, name: str) -> PackageTerm:
    return PackageTerm(
        name=name, label=_TERM_LABELS[name], value=_term_value(package, name)
    )


def _term_value(package: Package, name: str) -> str:
    match name:
        case "gate_id":
            return package.gate_id
        case "slot":
            return f"runway {package.slot.runway_id} at minute {package.slot.time_min}"
        case "action":
            return package.action.value
    raise KeyError(name)


def authority_terms(
    package: Package,
) -> tuple[tuple[PackageTerm, ...], tuple[PackageTerm, ...]]:
    """(terms the airline decides, terms it can only request), from
    `Package.AUTHORITY`."""
    decides = Package.AUTHORITY["airline_decides"]
    requests = Package.AUTHORITY["requires_request"]
    return (
        tuple(_term(package, n) for n in decides),
        tuple(_term(package, n) for n in requests),
    )


# ---------------------------------------------------------- reason codes

# Stable code -> sentence. Agents choose codes; the card writes the sentence.
_RULE_REJECTIONS: Mapping[str, str] = {
    "ATC-WAKE-SEP": "Rejected: too little wake separation behind another arrival.",
    "ATC-RWY-CLOSED": "Rejected: the arrival runway is closed or unknown.",
    "ATC-TWY-CLOSED": "Rejected: the taxiway serving the gate is closed or unknown.",
    "ATC-RWY-THROUGHPUT": "Rejected: too many arrivals in an hour at the airport.",
    "ATC-SLOT-WINDOW": "Rejected: the arrival slot is outside the planning window.",
    "PLT-FUEL-POLICY": "Rejected: landing fuel falls below the workbook reserve.",
    "PLT-CREW-DUTY": "Rejected: the flight crew would exceed their maximum duty.",
    "GND-GATE-NOTICE": "Rejected: a gate change would come with too little notice.",
    "GND-GATE-OVERLAP": "Rejected: the gate stay overlaps another flight.",
    "GND-GATE-SIZE": "Rejected: the aircraft does not fit the gate.",
    "GND-TURNAROUND": "Rejected: not enough turnaround time for the next leg.",
}


def _rejection_code(rule_id: str) -> str:
    return "REJECT_" + rule_id.replace("-", "_")


UNRECOGNISED_CODE = "UNRECOGNISED_REASON_CODE"

REASON_CODES: Mapping[str, str] = MappingProxyType(
    {
        **{_rejection_code(r): text for r, text in _RULE_REJECTIONS.items()},
        "PREFER_LOW_FUEL_BURN": "Preferred: it burns less fuel absorbing the delay.",
        "PREFER_EARLY_ARRIVAL": "Preferred: it lands earlier.",
        "PREFER_PLANNED_GATE": "Preferred: it keeps the planned gate.",
        "PREFER_PROTECT_CONNECTIONS": "Preferred: it protects passenger connections.",
        "PREFER_AVOID_OVERTIME": "Preferred: it avoids ground crew overtime.",
        "PREFER_PROTECT_TURNAROUND": "Preferred: it protects the next-leg turnaround.",
        "ACCEPT_WITHIN_AUTHORITY": "Accepted: it stays within this domain's authority.",
        "NOTE_CREW_DUTY_LIMIT": "A crew note limits how long the crew can work.",
        "NOTE_RAMP_CAPACITY": "A ramp note limits ground handling capacity.",
        "NOTE_WEATHER_TREND": "A weather note changes the expected conditions.",
        "FALLBACK_NO_CONSENSUS": "Chosen by code: the domains did not agree.",
        "FALLBACK_AFTER_FAULT": "Chosen by code after a fault, not by consensus.",
        "FALLBACK_PACKAGE_BOUND": (
            "Chosen by code: too many candidate packages to offer the agents."
        ),
        "FALLBACK_NOTHING_TO_OFFER": (
            "Decided by code: no package passed every rule to offer the agents."
        ),
        "FALLBACK_LOWEST_COST": "Chosen by code: lowest soft cost among legal ones.",
        UNRECOGNISED_CODE: "A reason code was given that this system does not know.",
    }
)


class ReasonLine(FrozenModel):
    code: str
    text: str


def reason_lines(codes: Sequence[str]) -> tuple[ReasonLine, ...]:
    """Known codes become their template. An unknown code is never echoed."""
    lines: list[ReasonLine] = []
    for code in codes:
        known = isinstance(code, str) and code in REASON_CODES
        key = code if known else UNRECOGNISED_CODE
        lines.append(ReasonLine(code=key, text=REASON_CODES[key]))
    return tuple(lines)


# ------------------------------------------------------ how it was reached


class Reached(StrEnum):
    """How the plan came to be chosen. A fact the card must state."""

    CONSENSUS = "consensus"
    FALLBACK = "fallback"
    FALLBACK_MODEL_OFF = "fallback_model_off"
    FALLBACK_AFTER_FAULT = "fallback_after_fault"


_REACHED_TEXT: Mapping[Reached, str] = MappingProxyType(
    {
        Reached.CONSENSUS: (
            "Reached by agreement: all three domains accepted it, and code "
            "re-checked every rule."
        ),
        Reached.FALLBACK: (
            "Chosen by code, not by agreement: the domains did not agree within "
            "the turn cap."
        ),
        Reached.FALLBACK_MODEL_OFF: (
            "Chosen by rules. The model was off, so the agents did not run."
        ),
        Reached.FALLBACK_AFTER_FAULT: (
            "Chosen by code after a system fault, not by agreement. A call "
            "failed, was refused or could not be logged."
        ),
    }
)


def reached_from_result(
    path: str, faults: Sequence[object], *, model_off: bool = False
) -> Reached:
    """Read it from a protocol result's `path` and `faults`. Any fault means the
    plan did not come cleanly, whatever the path says, so it outranks `model_off`,
    which is whether the protocol logged that the fallback ran because the model
    was switched off."""
    if path not in ("consensus", "fallback"):
        raise ValueError("only a consensus or fallback plan has a package card")
    if faults:
        return Reached.FALLBACK_AFTER_FAULT
    if path == "consensus":
        return Reached.CONSENSUS
    return Reached.FALLBACK_MODEL_OFF if model_off else Reached.FALLBACK


# ---------------------------------------------------- status and labels

SCENARIO_DEFINED = "scenario_defined"

STATUS_LABELS: Mapping[rv.Status, str] = MappingProxyType(
    {
        rv.Status.CONFIRMED: "Limit taken from the cited standard.",
        rv.Status.SECONDARY: (
            "Limit from a secondary source, not checked against the primary rule text."
        ),
        rv.Status.UNVERIFIED: "Limit not yet verified against its source.",
        rv.Status.ASSUMPTION: "Demo assumption, not a regulation.",
        rv.Status.POLICY: "Our demo policy, not a regulation.",
        rv.Status.WORKBOOK: "Challenge workbook limit (synthetic, not a regulation).",
    }
)
SCENARIO_DEFINED_LABEL = "Limit is set by the scenario data, not by a regulation."
_NO_BASIS_LABEL = "Limit basis unknown."
_NOT_REPORTED = "not reported when a rule passes"

# Units the rules report. Anything else is shown as unrecognised, not echoed.
_RULE_UNITS = frozenset(
    {
        "min",
        "kg",
        "arrivals per hour",
        "closed runways",
        "closed taxiways",
        "size class",
        "min of delay",
        "min off grid",
        "impossible actions",
    }
)
KNOWN_UNITS = _RULE_UNITS | frozenset(v.unit for v in rv.RULE_VALUES.values())
_UNKNOWN_UNIT = "unit not recognised"

_RULES_BY_ID = {rule.rule_id: rule for rule in ALL_RULES}
_SCENARIO_DEFINED_RULES = frozenset(
    {"ATC-RWY-CLOSED", "ATC-TWY-CLOSED", "ATC-SLOT-WINDOW", "GND-GATE-SIZE"}
)
_DEFAULT_BASIS: Mapping[str, str] = MappingProxyType(
    {
        "ATC-WAKE-SEP": rv.WAKE_DEFAULT_KEY,
        "PLT-FUEL-POLICY": rv.FUEL_RESERVE_MIN,
        "GND-GATE-OVERLAP": rv.GATE_BUFFER_MIN,
    }
)


# Matches the dashboard: a held rule is a requirement (a noun phrase); a broken
# rule says what the plan does wrong (a verb sentence).
RULE_REQUIREMENTS: Mapping[str, str] = MappingProxyType(
    {
        "ATC-WAKE-SEP": "Spacing behind the aircraft ahead",
        "ATC-RWY-CLOSED": "An open arrival runway",
        "ATC-TWY-CLOSED": "An open taxiway to the gate",
        "ATC-RWY-THROUGHPUT": "Arrivals per hour at the airport",
        "ATC-SLOT-WINDOW": "An arrival slot inside the planning window",
        "PLT-FUEL-POLICY": "Fuel at landing against the workbook reserve",
        "PLT-CREW-DUTY": "Flight crew inside their maximum duty",
        "GND-GATE-NOTICE": "A gate change decided in time",
        "GND-GATE-OVERLAP": "A gate that is free for the turnaround",
        "GND-GATE-SIZE": "A gate that fits the aircraft",
        "GND-TURNAROUND": "Time to turn the aircraft round",
    }
)
RULE_BREACHES: Mapping[str, str] = MappingProxyType(
    {
        "ATC-WAKE-SEP": "Lands too close behind the aircraft ahead",
        "ATC-RWY-CLOSED": "Uses a closed runway",
        "ATC-TWY-CLOSED": "Uses a gate that is occupied or blocked",
        "ATC-RWY-THROUGHPUT": "Puts too many arrivals into the airport in an hour",
        "ATC-SLOT-WINDOW": "Lands outside the planning window or off the slot grid",
        "PLT-FUEL-POLICY": "Lands with less fuel than the workbook reserve allows",
        "PLT-CREW-DUTY": "Keeps the flight crew on duty past their maximum",
        "GND-GATE-NOTICE": "Changes gate with too little notice",
        "GND-GATE-OVERLAP": "Uses a gate that is occupied or blocked",
        "GND-GATE-SIZE": "Uses a gate too small for the aircraft",
        "GND-TURNAROUND": "Leaves too little time to turn the aircraft round",
    }
)
UNKNOWN_RULE_REQUIREMENT = "A rule this system does not know"
UNKNOWN_RULE_BREACH = "Breaks a rule this system does not know"
MISSING_DATA_MESSAGE = (
    "Cannot be checked because an input is unknown or invalid, so it is blocked"
)


class RuleStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MISSING_DATA = "missing_data"


class RuleLine(FrozenModel):
    rule_id: str
    domain: Domain
    # The requirement as a noun phrase, shown when the rule holds.
    description: str
    # What the plan does wrong, as a sentence; None when the rule holds.
    message: str | None
    status: RuleStatus
    observed: int | None
    limit: int | None
    unit: str | None
    # The rule value behind the limit, with its status taken from rule_values.
    basis_key: str | None
    basis_status: str  # a `rule_values.Status` value or SCENARIO_DEFINED
    basis_label: str
    is_regulation: bool
    # Where the limit comes from: the rule value's source, else the rule's own.
    source: str


def _basis(
    rule_id: str,
    scenario: Scenario | None,
    package: Package | None,
    violation: Violation | None,
) -> rv.RuleValue | None:
    """The rule value behind a rule's limit, or None when scenario-defined or
    unknown. A violation's source is read only for a key that is in the
    table; the text itself is never shown."""
    if violation is not None:
        key = violation.source.split("=", 1)[0]
        if key == rv.AIRPORT_OPS_KEY and violation.limit is not None:
            return rv.airport_ops_per_hour(violation.limit)
        if key == rv.AIRPORT_TURNAROUND_KEY and violation.limit is not None:
            return rv.airport_min_turnaround(violation.limit)
        if key in rv.RULE_VALUES:
            return rv.RULE_VALUES[key]
    if rule_id in _DEFAULT_BASIS:
        return rv.RULE_VALUES[_DEFAULT_BASIS[rule_id]]
    if scenario is None:
        return None
    ops = scenario.airport_ops_per_hour.value
    if rule_id == "ATC-RWY-THROUGHPUT" and ops is not None:
        return rv.airport_ops_per_hour(ops)
    turnaround = scenario.min_turnaround_min.value
    if rule_id == "GND-TURNAROUND" and turnaround is not None:
        return rv.airport_min_turnaround(turnaround)
    return None


def _rule_line(
    rule_id: str,
    scenario: Scenario | None,
    package: Package | None,
    violation: Violation | None,
) -> RuleLine:
    rule = _RULES_BY_ID.get(rule_id)
    basis = _basis(rule_id, scenario, package, violation) if rule else None
    if basis is not None:
        basis_status, label = basis.status.value, STATUS_LABELS[basis.status]
    elif rule_id in _SCENARIO_DEFINED_RULES:
        basis_status, label = SCENARIO_DEFINED, SCENARIO_DEFINED_LABEL
    else:
        basis_status, label = "unknown", _NO_BASIS_LABEL
    message: str | None
    if violation is None:
        status = RuleStatus.PASS
        observed = limit = unit = message = None
    else:
        missing = violation.cause is ViolationCause.MISSING_DATA
        status = RuleStatus.MISSING_DATA if missing else RuleStatus.FAIL
        observed, limit = violation.observed, violation.limit
        unit = None if missing else _safe_unit(violation.unit)
        message = (
            MISSING_DATA_MESSAGE
            if missing
            else RULE_BREACHES.get(rule_id, UNKNOWN_RULE_BREACH)
        )
    return RuleLine(
        rule_id=rule_id if rule else "UNKNOWN-RULE",
        domain=rule.domain if rule else (violation.domain if violation else Domain.ATC),
        description=RULE_REQUIREMENTS.get(rule_id, UNKNOWN_RULE_REQUIREMENT),
        message=message,
        status=status,
        observed=observed,
        limit=limit,
        unit=unit,
        basis_key=basis.key if basis else None,
        basis_status=basis_status,
        basis_label=label,
        is_regulation=basis is not None and basis.status is rv.Status.CONFIRMED,
        source=basis.source if basis else (rule.source if rule else "unknown"),
    )


def _safe_unit(unit: str) -> str:
    return unit if unit in KNOWN_UNITS else _UNKNOWN_UNIT


def violation_lines(
    scenario: Scenario | None,
    violations: Sequence[Violation],
    package: Package | None = None,
) -> tuple[RuleLine, ...]:
    """One line per violation, with no pass lines."""
    return tuple(_rule_line(v.rule_id, scenario, package, v) for v in violations)


def rule_lines(
    scenario: Scenario | None,
    violations: Sequence[Violation],
    package: Package | None = None,
) -> tuple[RuleLine, ...]:
    """One line per violation, plus a pass line for each rule with none."""
    by_rule: dict[str, list[Violation]] = {}
    for violation in violations:
        by_rule.setdefault(violation.rule_id, []).append(violation)
    lines: list[RuleLine] = []
    for rule in ALL_RULES:
        found = by_rule.pop(rule.rule_id, [])
        if found:
            lines.extend(_rule_line(rule.rule_id, scenario, package, v) for v in found)
        else:
            lines.append(_rule_line(rule.rule_id, scenario, package, None))
    for stray in by_rule.values():  # rule IDs outside the registry
        lines.extend(_rule_line(v.rule_id, scenario, package, v) for v in stray)
    return tuple(lines)


# ------------------------------------------------------------- cards


class AuthoritySplit(FrozenModel):
    airline_decides: tuple[PackageTerm, ...]
    requests_only: tuple[PackageTerm, ...]
    notes: tuple[str, ...]


class CostLine(FrozenModel):
    name: str
    units: int


class ProvenanceLine(FrozenModel):
    field: str
    provenance: Provenance
    known: bool


class Selection(FrozenModel):
    packages_considered: int
    packages_legal: int


_AUTHORITY_NOTES = (
    "The airline decides the gate. It can only request the arrival slot and the "
    "flight-plan action; ATC and the airport grant or refuse those.",
    "Next-leg handling is the airline's own and is not a term of this package.",
    "The pilot in command keeps their own fuel and safety authority.",
)

# The facts `card_hash` covers. Reasons, state version and selection are not.
HASHED_FIELDS = (
    "kind",
    "how_reached",
    "package_name",
    "terms_hash",
    "headline",
    "authority",
    "what_to_do",
    "why",
    "what_could_go_wrong",
    "rules",
    "costs",
    "provenance",
    "all_rules_passed",
)

_COST_UNKNOWN_NAMES = frozenset(
    {
        "connections",
        "taxi_in_min",
        "ground_shift_end_min",
        "aircraft_size",
        "next_departure_min",
        "fuel inputs",
        "planned_gate",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class Card(FrozenModel):
    """Facts about one package at one state. Holds no model-written text."""

    kind: Literal["DECISION"] = "DECISION"
    package_name: str
    terms_hash: str
    how_reached: Reached
    headline: str
    authority: AuthoritySplit
    what_to_do: tuple[str, ...]
    why: tuple[str, ...]
    what_could_go_wrong: tuple[str, ...]
    rules: tuple[RuleLine, ...]
    costs: tuple[CostLine, ...]
    provenance: tuple[ProvenanceLine, ...]
    all_rules_passed: bool
    # Not in `card_hash`.
    reasons: tuple[ReasonLine, ...] = ()
    state_version: str | None = None
    selection: Selection | None = None

    @property
    def field_hashes(self) -> Mapping[str, str]:
        """A hash per hashed fact, so a change can be traced to its field."""
        return {name: _digest(_dump(getattr(self, name))) for name in HASHED_FIELDS}

    @property
    def card_hash(self) -> str:
        return _digest(dict(self.field_hashes))


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_dump(v) for v in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


def changed_card_fields(
    seen: Mapping[str, str] | None, current: Mapping[str, str]
) -> tuple[str, ...]:
    """Fact names whose hash differs. Empty `seen` cannot attribute a change."""
    if seen is None:
        return ()
    names = [n for n in HASHED_FIELDS if seen.get(n) != current.get(n)]
    return tuple(names)


def card_hash_of(field_hashes: Mapping[str, str]) -> str:
    return _digest(dict(field_hashes))


def _provenance_lines(scenario: Scenario) -> tuple[ProvenanceLine, ...]:
    lines: list[ProvenanceLine] = []
    for name in type(scenario).model_fields:
        sourced: Sourced[Any] = getattr(scenario, name)
        lines.append(
            ProvenanceLine(
                field=name,
                provenance=sourced.provenance,
                known=sourced.value is not None,
            )
        )
    return tuple(lines)


def _cost_lines(cost: CostBreakdown) -> tuple[CostLine, ...]:
    return (
        CostLine(name="fuel burn", units=cost.fuel_burn),
        CostLine(name="connections at risk", units=cost.connections_at_risk),
        CostLine(name="gate moves", units=cost.gate_moves),
        CostLine(name="ground overtime", units=cost.overtime),
        CostLine(name="turnaround delay", units=cost.turnaround_delay),
        CostLine(name="arrival delay", units=cost.arrival_delay),
        CostLine(name="total", units=cost.total),
    )


def decision_card(
    scenario: Scenario,
    decision: Deal | Package,
    cost: CostBreakdown | None = None,
    violations: Sequence[Violation] = (),
    *,
    how_reached: Reached,
    reason_codes: Sequence[str] = (),
    state_version: str | None = None,
) -> Card:
    """The card for one package at the given state.

    `how_reached` is required: the card states how the plan was chosen, and it is
    part of the card hash. `decision` is a `Deal` or a bare `Package`. A
    `NoGo` has no package; use `no_go_card`. `violations` are those the
    rules report at this state.
    """
    if isinstance(decision, Deal):
        package, cost = decision.package, cost if cost is not None else decision.cost
        selection: Selection | None = Selection(
            packages_considered=decision.packages_considered,
            packages_legal=decision.packages_legal,
        )
    elif isinstance(decision, Package):
        package, selection = decision, None
    else:
        raise TypeError("decision_card needs a Deal or a Package; see no_go_card")
    if cost is None:
        raise ValueError("a cost breakdown is required for a Package")

    name = package_name(package)
    airline, requests = authority_terms(package)
    lines = rule_lines(scenario, violations, package)
    failing = [line for line in lines if line.status is not RuleStatus.PASS]
    passed = not failing
    provenance = _provenance_lines(scenario)

    todo: tuple[str, ...]
    why: tuple[str, ...]
    if passed:
        headline = f"{name}: every hard rule passes at the current state."
        todo = (
            f"Decide the gate for {name} as the airline.",
            f"Send the slot and action for {name} to ATC as requests.",
            "Approval records that requests were issued. Nothing is executed.",
        )
        why = (
            _REACHED_TEXT[how_reached],
            f"Every hard rule passes at the current state. Soft cost is "
            f"{cost.total} units.",
        )
    else:
        headline = f"{name}: do not sign off; {len(failing)} rule result(s) fail."
        todo = (f"Do not sign off {name}. Choose another package or hand the case on.",)
        why = (
            _REACHED_TEXT[how_reached],
            f"{len(failing)} rule result(s) fail at the current state.",
        )

    risks = [
        "ATC or the airport may refuse or change the requested slot and action.",
        "Gate, runway or traffic state can change before sign-off; sign-off "
        "re-checks every rule and refuses if the state changed.",
        "The pilot in command may decline on fuel or safety grounds.",
    ]
    counts = {p: sum(1 for x in provenance if x.provenance is p) for p in Provenance}
    risks.append(
        f"{counts[Provenance.SYNTHETIC]} scenario inputs are synthetic, "
        f"{counts[Provenance.DERIVED]} derived and {counts[Provenance.REAL]} real."
    )
    unknown = [p.field for p in provenance if not p.known]
    if unknown:
        risks.append("Unknown scenario inputs: " + ", ".join(unknown) + ".")
    left_out = sorted(n for n in cost.unknown_inputs if n in _COST_UNKNOWN_NAMES)
    if left_out:
        risks.append("Soft cost left out unknown inputs: " + ", ".join(left_out) + ".")
    if any(
        line.basis_status in (rv.Status.POLICY.value, rv.Status.ASSUMPTION.value)
        for line in lines
    ):
        risks.append("Some limits are our demo policy or assumptions, not regulations.")
    if any(line.basis_status == rv.Status.WORKBOOK.value for line in lines):
        risks.append(
            "Some limits come from the challenge workbook: synthetic planning "
            "limits, not regulations."
        )
    risks.append("The rules are a subset of real ATC procedure.")

    return Card(
        package_name=name,
        terms_hash=package.terms_hash,
        how_reached=how_reached,
        headline=headline,
        authority=AuthoritySplit(
            airline_decides=airline, requests_only=requests, notes=_AUTHORITY_NOTES
        ),
        what_to_do=todo,
        why=why,
        what_could_go_wrong=tuple(risks),
        rules=lines,
        costs=_cost_lines(cost),
        provenance=provenance,
        all_rules_passed=passed,
        reasons=reason_lines(reason_codes),
        state_version=state_version,
        selection=selection,
    )


# ------------------------------------------------------------ no-go

_NO_GO_HEADLINES: Mapping[NoGoReason, str] = MappingProxyType(
    {
        NoGoReason.NOTHING_LEGAL: (
            "NO-GO: nothing legal. A real constraint blocks every candidate package."
        ),
        NoGoReason.SYSTEM_FAULT: (
            "NO-GO: system fault. Missing data or a failure blocked the search; "
            "this is not a finding that nothing is legal."
        ),
    }
)
_NO_GO_ACTIONS: Mapping[NoGoReason, str] = MappingProxyType(
    {
        NoGoReason.NOTHING_LEGAL: (
            "A human decides this case. Nothing has been approved or requested."
        ),
        NoGoReason.SYSTEM_FAULT: (
            "Fix the fault or supply the missing data, then run again. Nothing has "
            "been approved or requested."
        ),
    }
)


NO_RULE = "NO-RULE"
_NO_PACKAGE_CHANGES: Mapping[NoGoReason, str] = MappingProxyType(
    {
        NoGoReason.NOTHING_LEGAL: (
            "No candidate package fits the planning window; widen the window."
        ),
        NoGoReason.SYSTEM_FAULT: (
            "No candidate package could be built; supply the missing scenario inputs."
        ),
    }
)


class BindingRule(FrozenModel):
    rule_id: str
    description: str
    packages_eliminated: int
    binding: bool


class ChangeLine(FrozenModel):
    rule_id: str
    text: str


class NoGoCard(FrozenModel):
    kind: Literal["NO_GO"] = "NO_GO"
    reason_type: NoGoReason
    headline: str
    what_to_do: str
    packages_considered: int
    binding_rules: tuple[BindingRule, ...]
    # One violation per binding rule with its numbers, limit, unit and source.
    binding_evidence: tuple[RuleLine, ...]
    nearest_package_name: str | None
    nearest_authority: AuthoritySplit | None
    nearest_rules: tuple[RuleLine, ...]
    what_would_have_to_change: tuple[ChangeLine, ...]


def _change(line: RuleLine) -> ChangeLine:
    if line.status is RuleStatus.MISSING_DATA or line.observed is None:
        return ChangeLine(
            rule_id=line.rule_id,
            text="Supply the missing input this rule needs.",
        )
    unit = line.unit or _UNKNOWN_UNIT
    if line.limit is None:
        return ChangeLine(
            rule_id=line.rule_id, text=f"Observed {line.observed} {unit}."
        )
    gap = abs(line.observed - line.limit)
    direction = "at least" if line.observed < line.limit else "at most"
    return ChangeLine(
        rule_id=line.rule_id,
        text=(
            f"Observed {line.observed} {unit}; it must be {direction} "
            f"{line.limit} {unit}, a change of {gap}."
        ),
    )


def no_go_card(no_go: NoGo, scenario: Scenario | None = None) -> NoGoCard:
    """The card for a `NoGo`. `NoGo.reason` is free text and is not used."""
    counts = {e.rule_id: e.packages_eliminated for e in no_go.eliminations}
    binding_ids = set(no_go.binding_rule_ids)
    binding = tuple(
        BindingRule(
            rule_id=rule_id if rule_id in _RULES_BY_ID else "UNKNOWN-RULE",
            description=(
                RULE_REQUIREMENTS[rule_id]
                if rule_id in RULE_REQUIREMENTS and rule_id in _RULES_BY_ID
                else UNKNOWN_RULE_REQUIREMENT
            ),
            packages_eliminated=counts.get(rule_id, 0),
            binding=rule_id in binding_ids,
        )
        for rule_id in dict.fromkeys((*no_go.binding_rule_ids, *counts))
    )
    nearest = no_go.nearest_package
    lines = rule_lines(scenario, no_go.nearest_violations, nearest) if nearest else ()
    failing = tuple(line for line in lines if line.status is not RuleStatus.PASS)
    authority: AuthoritySplit | None = None
    if nearest is not None:
        airline, requests = authority_terms(nearest)
        authority = AuthoritySplit(
            airline_decides=airline, requests_only=requests, notes=_AUTHORITY_NOTES
        )
    return NoGoCard(
        reason_type=no_go.reason_type,
        headline=_NO_GO_HEADLINES[no_go.reason_type],
        what_to_do=_NO_GO_ACTIONS[no_go.reason_type],
        packages_considered=no_go.packages_considered,
        binding_rules=binding,
        binding_evidence=violation_lines(scenario, no_go.binding_violations),
        nearest_package_name=package_name(nearest) if nearest else None,
        nearest_authority=authority,
        nearest_rules=failing,
        what_would_have_to_change=(
            tuple(_change(line) for line in failing)
            if nearest is not None
            else (
                ChangeLine(
                    rule_id=NO_RULE, text=_NO_PACKAGE_CHANGES[no_go.reason_type]
                ),
            )
        ),
    )


# --------------------------------------------------------- model notes

MODEL_NOTE_LABEL = "Written by a model. Not verified. Not a fact of this card."
MODEL_NOTE_MAX_CHARS = 2000


class ModelNote(FrozenModel):
    """Model prose. A separate type, so a `Card` cannot hold it."""

    text: str

    @property
    def label(self) -> str:
        return MODEL_NOTE_LABEL


def model_note(text: str) -> ModelNote:
    """Wrap model prose, capped in length with control characters removed."""
    if not isinstance(text, str):
        raise TypeError("a model note is text")
    cleaned = "".join(ch for ch in text if ch == "\n" or ch.isprintable())
    return ModelNote(text=cleaned[:MODEL_NOTE_MAX_CHARS])


# ------------------------------------------------------------ rendering


def _terms(terms: Sequence[PackageTerm]) -> str:
    return "; ".join(f"{t.label}: {t.value}" for t in terms) or "none"


def _rule_text(line: RuleLine) -> str:
    if line.status is RuleStatus.PASS:
        values = _NOT_REPORTED
    elif line.observed is None:
        values = "input unknown, so the rule fails closed"
    else:
        values = f"observed {line.observed}, limit {line.limit}, {line.unit}"
    text = line.message or line.description
    return (
        f"  [{line.status.value.upper()}] {line.rule_id} ({line.domain.value}) "
        f"{text}: {values}. Basis {line.basis_status}: {line.basis_label} "
        f"Source: {line.source}"
    )


def _render_note(note: ModelNote) -> list[str]:
    # Every line is prefixed so the note cannot pose as a card heading.
    body = [f"> {ln}" for ln in note.text.splitlines() or [""]]
    return ["", f"MODEL NOTE ({note.label})", *body]


def render(card: Card | NoGoCard, note: ModelNote | None = None) -> str:
    """Plain text. Facts first; a model note, if any, last and quoted."""
    out: list[str] = [card.headline]
    if isinstance(card, Card):
        out += [
            f"Package: {card.package_name} (terms {card.terms_hash})",
            f"How reached: {card.how_reached.value}",
            f"Card hash: {card.card_hash}",
            "AUTHORITY",
            f"  The airline decides: {_terms(card.authority.airline_decides)}",
            f"  Requests only: {_terms(card.authority.requests_only)}",
            *(f"  {n}" for n in card.authority.notes),
            "WHAT TO DO",
            *(f"  {t}" for t in card.what_to_do),
            "WHY",
            *(f"  {t}" for t in card.why),
            *(
                ["REASONS GIVEN (picked from a fixed list; not checked by code)"]
                if card.reasons
                else []
            ),
            *(f"  {r.text}" for r in card.reasons),
            "WHAT COULD GO WRONG",
            *(f"  {t}" for t in card.what_could_go_wrong),
            "RULES",
            *(_rule_text(r) for r in card.rules),
            "SOFT COST",
            *(f"  {c.name}: {c.units}" for c in card.costs),
            "PROVENANCE",
            *(
                f"  {p.field}: {p.provenance.value}{'' if p.known else ' (unknown)'}"
                for p in card.provenance
            ),
        ]
    else:
        out += [
            f"Type: {card.reason_type.value}",
            "WHAT TO DO",
            f"  {card.what_to_do}",
            f"Packages considered: {card.packages_considered}",
            "BINDING RULES",
            *(
                f"  {'*' if b.binding else ' '} {b.rule_id}: {b.description}; "
                f"eliminated {b.packages_eliminated}"
                for b in card.binding_rules
            ),
            "BINDING RULE EVIDENCE",
            *(_rule_text(r) for r in card.binding_evidence),
            f"Nearest package: {card.nearest_package_name or 'none'}",
        ]
        if card.nearest_authority is not None:
            out += [
                f"  The airline decides: "
                f"{_terms(card.nearest_authority.airline_decides)}",
                f"  Requests only: {_terms(card.nearest_authority.requests_only)}",
            ]
        out += [
            "WHAT WOULD HAVE TO CHANGE",
            *(f"  {c.rule_id}: {c.text}" for c in card.what_would_have_to_change),
            "NEAREST PACKAGE RULES",
            *(_rule_text(r) for r in card.nearest_rules),
        ]
    if note is not None:
        out += _render_note(note)
    return "\n".join(out)
