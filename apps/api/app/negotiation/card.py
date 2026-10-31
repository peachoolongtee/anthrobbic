"""Decision and no-deal cards. Every statement shown as fact is built here.

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
    NoDeal,
    NoDealReason,
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
    name: str
    value: str


def _term_value(package: Package, name: str) -> str:
    match name:
        case "gate_id":
            return f"gate {package.gate_id}"
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
        tuple(PackageTerm(name=n, value=_term_value(package, n)) for n in decides),
        tuple(PackageTerm(name=n, value=_term_value(package, n)) for n in requests),
    )


# ---------------------------------------------------------- reason codes

# Stable code -> sentence. Agents choose codes; the card writes the sentence.
_RULE_REJECTIONS: Mapping[str, str] = {
    "ATC-WAKE-SEP": "Rejected: too little wake separation behind another arrival.",
    "ATC-RWY-CLOSED": "Rejected: the arrival runway is closed or unknown.",
    "ATC-TWY-CLOSED": "Rejected: the taxiway serving the gate is closed or unknown.",
    "ATC-RWY-THROUGHPUT": "Rejected: too many arrivals in an hour on the runway.",
    "PLT-FUEL-POLICY": "Rejected: landing fuel falls below the policy reserve.",
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


# ---------------------------------------------------- status and labels

SCENARIO_DEFINED = "scenario_defined"

STATUS_LABELS: Mapping[rv.Status, str] = MappingProxyType(
    {
        rv.Status.CONFIRMED: "Limit taken from the cited standard.",
        rv.Status.SECONDARY: "Limit from a published study, not a rule.",
        rv.Status.UNVERIFIED: "Limit not yet verified against its source.",
        rv.Status.ASSUMPTION: "Demo assumption, not a regulation.",
        rv.Status.POLICY: "Our demo policy, not a regulation.",
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
        "impossible actions",
    }
)
KNOWN_UNITS = _RULE_UNITS | frozenset(v.unit for v in rv.RULE_VALUES.values())
_UNKNOWN_UNIT = "unit not recognised"

_RULES_BY_ID = {rule.rule_id: rule for rule in ALL_RULES}
_SCENARIO_DEFINED_RULES = frozenset(
    {"ATC-RWY-CLOSED", "ATC-TWY-CLOSED", "GND-GATE-SIZE"}
)
_DEFAULT_BASIS: Mapping[str, str] = MappingProxyType(
    {
        "ATC-WAKE-SEP": rv.WAKE_DEFAULT_KEY,
        "PLT-FUEL-POLICY": rv.FUEL_RESERVE_MIN,
        "GND-GATE-OVERLAP": rv.GATE_BUFFER_MIN,
    }
)


class RuleStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MISSING_DATA = "missing_data"


class RuleLine(FrozenModel):
    rule_id: str
    domain: Domain
    description: str
    status: RuleStatus
    observed: int | None
    limit: int | None
    unit: str | None
    # The rule value behind the limit, with its status taken from rule_values.
    basis_key: str | None
    basis_status: str  # a `rule_values.Status` value or SCENARIO_DEFINED
    basis_label: str
    is_regulation: bool


def _basis(
    rule_id: str, scenario: Scenario | None, violation: Violation | None
) -> rv.RuleValue | None:
    """The rule value behind a rule's limit, or None when scenario-defined or
    unknown. A violation's source is read only for a key that is in the
    table; the text itself is never shown."""
    if violation is not None:
        key = violation.source.split("=", 1)[0]
        if key in rv.RULE_VALUES:
            return rv.RULE_VALUES[key]
    if rule_id in _DEFAULT_BASIS:
        return rv.RULE_VALUES[_DEFAULT_BASIS[rule_id]]
    if scenario is None:
        return None
    if rule_id == "ATC-RWY-THROUGHPUT" and scenario.flight_rules.value is not None:
        return rv.runway_hourly_arrivals(scenario.flight_rules.value)
    if rule_id == "GND-TURNAROUND" and scenario.aircraft_size.value is not None:
        return rv.turnaround(scenario.aircraft_size.value)
    return None


def _rule_line(
    rule_id: str, scenario: Scenario | None, violation: Violation | None
) -> RuleLine:
    rule = _RULES_BY_ID.get(rule_id)
    basis = _basis(rule_id, scenario, violation) if rule else None
    if basis is not None:
        basis_status, label = basis.status.value, STATUS_LABELS[basis.status]
    elif rule_id in _SCENARIO_DEFINED_RULES:
        basis_status, label = SCENARIO_DEFINED, SCENARIO_DEFINED_LABEL
    else:
        basis_status, label = "unknown", _NO_BASIS_LABEL
    if violation is None:
        status = RuleStatus.PASS
        observed = limit = unit = None
    else:
        missing = violation.cause is ViolationCause.MISSING_DATA
        status = RuleStatus.MISSING_DATA if missing else RuleStatus.FAIL
        observed, limit = violation.observed, violation.limit
        unit = None if missing else _safe_unit(violation.unit)
    return RuleLine(
        rule_id=rule_id if rule else "UNKNOWN-RULE",
        domain=rule.domain if rule else (violation.domain if violation else Domain.ATC),
        description=rule.description if rule else "A rule this system does not know.",
        status=status,
        observed=observed,
        limit=limit,
        unit=unit,
        basis_key=basis.key if basis else None,
        basis_status=basis_status,
        basis_label=label,
        is_regulation=basis is not None and basis.status is rv.Status.CONFIRMED,
    )


def _safe_unit(unit: str) -> str:
    return unit if unit in KNOWN_UNITS else _UNKNOWN_UNIT


def rule_lines(
    scenario: Scenario | None, violations: Sequence[Violation]
) -> tuple[RuleLine, ...]:
    """One line per violation, plus a pass line for each rule with none."""
    by_rule: dict[str, list[Violation]] = {}
    for violation in violations:
        by_rule.setdefault(violation.rule_id, []).append(violation)
    lines: list[RuleLine] = []
    for rule in ALL_RULES:
        found = by_rule.pop(rule.rule_id, [])
        if found:
            lines.extend(_rule_line(rule.rule_id, scenario, v) for v in found)
        else:
            lines.append(_rule_line(rule.rule_id, scenario, None))
    for stray in by_rule.values():  # rule IDs outside the registry
        lines.extend(_rule_line(stray[0].rule_id, scenario, v) for v in stray)
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
        CostLine(name="total", units=cost.total),
    )


def decision_card(
    scenario: Scenario,
    decision: Deal | Package,
    cost: CostBreakdown | None = None,
    violations: Sequence[Violation] = (),
    *,
    reason_codes: Sequence[str] = (),
    state_version: str | None = None,
) -> Card:
    """The card for one package at the given state.

    `decision` is a `Deal` or a bare `Package`. A `NoDeal` has no package; use
    `no_deal_card`. `violations` are those the rules report at this state.
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
        raise TypeError("decision_card needs a Deal or a Package; see no_deal_card")
    if cost is None:
        raise ValueError("a cost breakdown is required for a Package")

    name = package_name(package)
    airline, requests = authority_terms(package)
    lines = rule_lines(scenario, violations)
    failing = [line for line in lines if line.status is not RuleStatus.PASS]
    passed = not failing
    provenance = _provenance_lines(scenario)

    if passed:
        headline = f"{name}: every hard rule passes at the current state."
        todo = (
            f"Decide the gate for {name} as the airline.",
            f"Send the slot and action for {name} to ATC as requests.",
            "Approval records that requests were issued. Nothing is executed.",
        )
        why = (
            f"Every hard rule passes at the current state. Soft cost is "
            f"{cost.total} units.",
        )
    else:
        headline = f"{name}: do not sign off; {len(failing)} rule result(s) fail."
        todo = (f"Do not sign off {name}. Choose another package or hand the case on.",)
        why = (f"{len(failing)} rule result(s) fail at the current state.",)

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
    risks.append("The rules are a subset of real ATC procedure.")

    return Card(
        package_name=name,
        terms_hash=package.terms_hash,
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


# ------------------------------------------------------------ no deal

_NO_DEAL_HEADLINES: Mapping[NoDealReason, str] = MappingProxyType(
    {
        NoDealReason.NOTHING_LEGAL: (
            "NO DEAL: nothing legal. A real constraint blocks every candidate package."
        ),
        NoDealReason.SYSTEM_FAULT: (
            "NO DEAL: system fault. Missing data or a failure blocked the search; "
            "this is not a finding that nothing is legal."
        ),
    }
)
_NO_DEAL_ACTIONS: Mapping[NoDealReason, str] = MappingProxyType(
    {
        NoDealReason.NOTHING_LEGAL: (
            "A human decides this case. Nothing has been approved or requested."
        ),
        NoDealReason.SYSTEM_FAULT: (
            "Fix the fault or supply the missing data, then run again. Nothing has "
            "been approved or requested."
        ),
    }
)


NO_RULE = "NO-RULE"
_NO_PACKAGE_CHANGES: Mapping[NoDealReason, str] = MappingProxyType(
    {
        NoDealReason.NOTHING_LEGAL: (
            "No candidate package fits the planning window; widen the window."
        ),
        NoDealReason.SYSTEM_FAULT: (
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


class NoDealCard(FrozenModel):
    kind: Literal["NO_DEAL"] = "NO_DEAL"
    reason_type: NoDealReason
    headline: str
    what_to_do: str
    packages_considered: int
    binding_rules: tuple[BindingRule, ...]
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


def no_deal_card(no_deal: NoDeal, scenario: Scenario | None = None) -> NoDealCard:
    """The card for a `NoDeal`. `NoDeal.reason` is free text and is not used."""
    counts = {e.rule_id: e.packages_eliminated for e in no_deal.eliminations}
    binding_ids = set(no_deal.binding_rule_ids)
    binding = tuple(
        BindingRule(
            rule_id=rule_id if rule_id in _RULES_BY_ID else "UNKNOWN-RULE",
            description=(
                _RULES_BY_ID[rule_id].description
                if rule_id in _RULES_BY_ID
                else "A rule this system does not know."
            ),
            packages_eliminated=counts.get(rule_id, 0),
            binding=rule_id in binding_ids,
        )
        for rule_id in dict.fromkeys((*no_deal.binding_rule_ids, *counts))
    )
    nearest = no_deal.nearest_package
    lines = rule_lines(scenario, no_deal.nearest_violations) if nearest else ()
    failing = tuple(line for line in lines if line.status is not RuleStatus.PASS)
    authority: AuthoritySplit | None = None
    if nearest is not None:
        airline, requests = authority_terms(nearest)
        authority = AuthoritySplit(
            airline_decides=airline, requests_only=requests, notes=_AUTHORITY_NOTES
        )
    return NoDealCard(
        reason_type=no_deal.reason_type,
        headline=_NO_DEAL_HEADLINES[no_deal.reason_type],
        what_to_do=_NO_DEAL_ACTIONS[no_deal.reason_type],
        packages_considered=no_deal.packages_considered,
        binding_rules=binding,
        nearest_package_name=package_name(nearest) if nearest else None,
        nearest_authority=authority,
        nearest_rules=failing,
        what_would_have_to_change=(
            tuple(_change(line) for line in failing)
            if nearest is not None
            else (
                ChangeLine(
                    rule_id=NO_RULE, text=_NO_PACKAGE_CHANGES[no_deal.reason_type]
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
    return "; ".join(f"{t.name}: {t.value}" for t in terms) or "none"


def _rule_text(line: RuleLine) -> str:
    if line.status is RuleStatus.PASS:
        values = _NOT_REPORTED
    elif line.observed is None:
        values = "input unknown, so the rule fails closed"
    else:
        values = f"observed {line.observed}, limit {line.limit}, {line.unit}"
    return (
        f"  [{line.status.value.upper()}] {line.rule_id} ({line.domain.value}): "
        f"{values}. Basis {line.basis_status}: {line.basis_label}"
    )


def _render_note(note: ModelNote) -> list[str]:
    # Every line is prefixed so the note cannot pose as a card heading.
    body = [f"> {ln}" for ln in note.text.splitlines() or [""]]
    return ["", f"MODEL NOTE ({note.label})", *body]


def render(card: Card | NoDealCard, note: ModelNote | None = None) -> str:
    """Plain text. Facts first; a model note, if any, last and quoted."""
    out: list[str] = [card.headline]
    if isinstance(card, Card):
        out += [
            f"Package: {card.package_name} (terms {card.terms_hash})",
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
