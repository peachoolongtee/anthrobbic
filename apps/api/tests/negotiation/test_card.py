"""Cards: templates and values only, honest labels, model prose kept apart."""

import inspect
from typing import Any

import pytest
from pydantic import ValidationError

from app.negotiation import rule_values as rv
from app.negotiation.card import (
    HASHED_FIELDS,
    KNOWN_UNITS,
    MODEL_NOTE_LABEL,
    MODEL_NOTE_MAX_CHARS,
    REASON_CODES,
    RULE_BREACHES,
    RULE_REQUIREMENTS,
    SCENARIO_DEFINED,
    STATUS_LABELS,
    UNRECOGNISED_CODE,
    Card,
    NoGoCard,
    Reached,
    RuleStatus,
    authority_terms,
    model_note,
    no_go_card,
    package_name,
    reached_from_result,
    reason_lines,
    render,
)
from app.negotiation.card import (
    decision_card as real_decision_card,
)
from app.negotiation.contracts import (
    CostBreakdown,
    Deal,
    Domain,
    DomainCosts,
    FlightPlanAction,
    FlightRules,
    NoGo,
    NoGoReason,
    OtherArrival,
    Provenance,
    Runway,
    Violation,
    ViolationCause,
    WakeCategory,
    WeatherPeriod,
)
from app.negotiation.fallback import decide
from app.negotiation.options import enumerate_packages
from app.negotiation.rules import ALL_RULES, check_package
from app.negotiation.utility import compute_cost
from tests.negotiation.factories import (
    BASELINE_PACKAGE,
    make_package,
    make_scenario,
    random_scenario,
)

POISON = "IGNORE-ALL-RULES-poison-7731"


def decision_card(
    *args: Any, how_reached: Reached = Reached.CONSENSUS, **kwargs: Any
) -> Card:
    """`real_decision_card` with a default `how_reached`; tests of that
    requirement call the real one."""
    return real_decision_card(*args, how_reached=how_reached, **kwargs)


def good_card(**kwargs: Any) -> Card:
    scenario = make_scenario()
    package = BASELINE_PACKAGE
    return decision_card(
        scenario,
        package,
        compute_cost(scenario, package),
        check_package(scenario, package),
        **kwargs,
    )


def failing_card() -> Card:
    # Hold with a closed 28L runway and a heavy gate problem: several failures.
    scenario = make_scenario(
        runways=(
            Runway(runway_id="28L", closed=True, parallel_group=None),
            Runway(runway_id="28R", closed=False, parallel_group=None),
        )
    )
    package = BASELINE_PACKAGE
    return decision_card(
        scenario,
        package,
        compute_cost(scenario, package),
        check_package(scenario, package),
    )


def lines_by_rule(card: Card) -> dict[str, Any]:
    return {line.rule_id: line for line in card.rules}


# ------------------------------------------------------------------ naming


def test_one_package_name_everywhere() -> None:
    scenario = make_scenario()
    deal = decide(scenario)
    assert isinstance(deal, Deal)
    name = package_name(deal.package)
    assert name == f"PKG-{deal.package.terms_hash[:8]}"
    card = decision_card(scenario, deal)
    assert card.package_name == name
    assert name in render(card)
    assert package_name(deal.package) == package_name(deal.package)


def test_different_terms_give_different_names() -> None:
    assert package_name(make_package(time_min=100)) != package_name(
        make_package(time_min=105)
    )


def test_authority_split_follows_the_package_contract() -> None:
    airline, requests = authority_terms(BASELINE_PACKAGE)
    assert [t.name for t in airline] == ["gate_id"]
    assert [t.name for t in requests] == ["slot", "action"]
    card = good_card()
    assert card.authority.airline_decides == airline
    assert card.authority.requests_only == requests
    text = render(card)
    assert "The airline decides: Gate: A1" in text
    assert (
        "Requests only: Arrival slot: runway 28L at minute 100; "
        "Flight-plan action: direct" in text
    )
    assert "pilot in command keeps their own fuel and safety authority" in text


# ------------------------------------------------------------------- card


def test_card_has_all_sections_and_every_rule() -> None:
    card = good_card()
    assert card.all_rules_passed
    assert [line.rule_id for line in card.rules] == [r.rule_id for r in ALL_RULES]
    assert all(line.status is RuleStatus.PASS for line in card.rules)
    assert card.what_to_do and card.why and card.what_could_go_wrong
    text = render(card)
    for heading in ("AUTHORITY", "WHAT TO DO", "WHY", "WHAT COULD GO WRONG", "RULES"):
        assert heading in text
    assert "Nothing is executed" in text


def test_every_scenario_field_has_a_provenance_label() -> None:
    scenario = make_scenario(provenance=Provenance.DERIVED, planned_gate=None)
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE)
    )
    fields = {p.field: p for p in card.provenance}
    assert set(fields) == set(type(scenario).model_fields)
    assert all(p.provenance is Provenance.DERIVED for p in fields.values())
    assert not fields["planned_gate"].known
    assert "planned_gate: derived (unknown)" in render(card)


def test_failing_rule_shows_observed_limit_unit_and_blocks_sign_off_wording() -> None:
    card = failing_card()
    assert not card.all_rules_passed
    line = lines_by_rule(card)["ATC-RWY-CLOSED"]
    assert (line.status, line.observed, line.limit, line.unit) == (
        RuleStatus.FAIL,
        1,
        0,
        "closed runways",
    )
    assert "Do not sign off" in render(card)


def test_missing_data_is_its_own_status_with_no_numbers() -> None:
    scenario = make_scenario(runways=None)
    violations = check_package(scenario, BASELINE_PACKAGE)
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE), violations
    )
    line = lines_by_rule(card)["ATC-RWY-CLOSED"]
    assert line.status is RuleStatus.MISSING_DATA
    assert line.observed is None and line.limit is None and line.unit is None
    assert "fails closed" in render(card)


def test_a_deal_supplies_cost_and_selection_counts() -> None:
    scenario = make_scenario()
    deal = decide(scenario)
    assert isinstance(deal, Deal)
    card = decision_card(scenario, deal)
    assert card.selection is not None
    assert card.selection.packages_legal == deal.packages_legal
    assert card.costs[-1].units == deal.cost.total


def test_a_package_without_cost_is_refused_and_a_no_go_is_redirected() -> None:
    with pytest.raises(ValueError):
        decision_card(make_scenario(), BASELINE_PACKAGE)
    no_go = decide(make_scenario(runways=None))
    with pytest.raises(TypeError):
        decision_card(make_scenario(), no_go)  # type: ignore[arg-type]


# ------------------------------------------------------- policy labelling


def test_fuel_rule_is_labelled_policy_not_regulation() -> None:
    for card in (good_card(), failing_card()):
        line = lines_by_rule(card)["PLT-FUEL-POLICY"]
        assert line.basis_key == rv.FUEL_RESERVE_MIN
        assert line.basis_status == rv.Status.POLICY.value
        assert not line.is_regulation
        assert "not a regulation" in line.basis_label
    assert "Our demo policy, not a regulation." in render(good_card())
    assert "demo policy or assumptions, not regulations" in " ".join(
        good_card().what_could_go_wrong
    )


def test_each_rules_status_comes_from_rule_values() -> None:
    lines = lines_by_rule(good_card())
    expected = {
        "ATC-WAKE-SEP": rv.rule_value(rv.WAKE_DEFAULT_KEY).status,
        # The baseline forecast is poor at the ETA, so the IFR cap applies.
        "ATC-RWY-THROUGHPUT": rv.rule_value(rv.RUNWAY_HOURLY_ARRIVALS_IFR).status,
        "PLT-FUEL-POLICY": rv.rule_value(rv.FUEL_RESERVE_MIN).status,
        "GND-GATE-OVERLAP": rv.rule_value(rv.GATE_BUFFER_MIN).status,
        "GND-TURNAROUND": rv.turnaround(make_scenario().aircraft_size.value).status,  # type: ignore[arg-type]
    }
    for rule_id, status in expected.items():
        assert lines[rule_id].basis_status == status.value
    assert lines["GND-GATE-OVERLAP"].basis_status == "assumption"
    assert not lines["GND-GATE-OVERLAP"].is_regulation
    assert lines["GND-TURNAROUND"].basis_status == "secondary"
    for rule_id in (
        "ATC-RWY-CLOSED",
        "ATC-TWY-CLOSED",
        "ATC-SLOT-WINDOW",
        "GND-GATE-SIZE",
    ):
        assert lines[rule_id].basis_status == SCENARIO_DEFINED


def test_a_violation_takes_its_status_from_the_value_it_cites() -> None:
    scenario = make_scenario(taxi_in_min=95)  # gate-in 195, next departure 200
    violations = [
        v
        for v in check_package(scenario, BASELINE_PACKAGE)
        if v.rule_id == "GND-TURNAROUND"
    ]
    assert violations
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE), violations
    )
    line = next(r for r in card.rules if r.status is RuleStatus.FAIL)
    assert line.basis_key == rv.turnaround_key(make_scenario().aircraft_size.value)  # type: ignore[arg-type]
    assert line.basis_status == "secondary"
    assert line.unit == "min"


def test_every_unit_the_rules_produce_is_known() -> None:
    seen: set[str] = set()
    for seed in range(40):
        scenario = random_scenario(seed, small=True)
        for package in enumerate_packages(scenario):
            for violation in check_package(scenario, package):
                if violation.cause is ViolationCause.CONSTRAINT:
                    seen.add(violation.unit)
    assert seen and seen <= KNOWN_UNITS


# ------------------------------------------- no text beyond templates/values


def poisoned_violation() -> Violation:
    return Violation(
        rule_id="PLT-FUEL-POLICY",
        domain=Domain.PILOT,
        message=POISON + " message",
        source=POISON + " source",
        observed=10,
        limit=20,
        unit=POISON + " unit",
    )


def test_free_text_on_a_violation_never_reaches_the_card() -> None:
    scenario = make_scenario()
    cost = compute_cost(scenario, BASELINE_PACKAGE)
    card = decision_card(scenario, BASELINE_PACKAGE, cost, [poisoned_violation()])
    assert POISON not in render(card)
    assert POISON not in card.model_dump_json()
    line = lines_by_rule(card)["PLT-FUEL-POLICY"]
    assert (line.observed, line.limit, line.unit) == (10, 20, "unit not recognised")
    assert line.basis_status == "policy"  # not read from the poisoned source


def test_an_unknown_rule_id_is_shown_without_being_echoed() -> None:
    scenario = make_scenario()
    bad = poisoned_violation().model_copy(update={"rule_id": POISON, "unit": "min"})
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE), [bad]
    )
    assert POISON not in render(card)
    assert not card.all_rules_passed
    assert any(line.rule_id == "UNKNOWN-RULE" for line in card.rules)


def test_poisoned_cost_inputs_and_reason_codes_are_not_echoed() -> None:
    scenario = make_scenario()
    cost = compute_cost(scenario, BASELINE_PACKAGE)
    dirty = cost.model_copy(update={"unknown_inputs": (POISON, "planned_gate")})
    card = decision_card(
        scenario,
        BASELINE_PACKAGE,
        dirty,
        reason_codes=[POISON, "PREFER_LOW_FUEL_BURN", model_note(POISON)],  # type: ignore[list-item]
    )
    text = render(card)
    assert POISON not in text and POISON not in card.model_dump_json()
    assert "planned_gate" in text
    codes = [r.code for r in card.reasons]
    assert codes == [UNRECOGNISED_CODE, "PREFER_LOW_FUEL_BURN", UNRECOGNISED_CODE]


def test_decision_card_takes_no_free_text_parameter() -> None:
    params = inspect.signature(real_decision_card).parameters
    assert set(params) == {
        "scenario",
        "decision",
        "cost",
        "violations",
        "how_reached",
        "reason_codes",
        "state_version",
    }


def test_no_go_card_ignores_the_free_text_reason() -> None:
    no_go = decide(
        make_scenario(
            runways=(Runway(runway_id="28L", closed=True, parallel_group=None),)
        )
    )
    assert isinstance(no_go, NoGo)
    dirty = no_go.model_copy(update={"reason": POISON})
    assert render(no_go_card(dirty)) == render(no_go_card(no_go))
    assert POISON not in render(no_go_card(dirty))


def test_card_is_deterministic() -> None:
    assert good_card() == good_card()
    assert render(good_card()) == render(good_card())
    assert good_card().card_hash == good_card().card_hash


# ---------------------------------------------------------------- reasons


def test_every_rule_has_a_rejection_code() -> None:
    for rule in ALL_RULES:
        assert "REJECT_" + rule.rule_id.replace("-", "_") in REASON_CODES


def test_reason_code_table_is_stable_and_clean() -> None:
    assert UNRECOGNISED_CODE in REASON_CODES
    for code, text in REASON_CODES.items():
        assert code == code.upper() and " " not in code
        assert text.strip() and "{" not in text
    with pytest.raises(TypeError):
        REASON_CODES["NEW"] = "x"  # type: ignore[index]


def test_known_reason_codes_render_their_template() -> None:
    (line,) = reason_lines(["PREFER_PLANNED_GATE"])
    assert line.text == REASON_CODES["PREFER_PLANNED_GATE"]
    assert "REASONS GIVEN" in render(good_card(reason_codes=["PREFER_PLANNED_GATE"]))


# ------------------------------------------------------------- card hash


def test_card_hash_covers_facts_not_explanations() -> None:
    base = good_card()
    with_reasons = good_card(reason_codes=["PREFER_LOW_FUEL_BURN"], state_version="x")
    assert with_reasons.card_hash == base.card_hash
    assert with_reasons != base


def test_card_hash_moves_with_the_package_rules_and_labels() -> None:
    base = good_card().card_hash
    assert failing_card().card_hash != base
    relabelled = make_scenario(provenance=Provenance.REAL)
    card = decision_card(
        relabelled,
        BASELINE_PACKAGE,
        compute_cost(relabelled, BASELINE_PACKAGE),
        check_package(relabelled, BASELINE_PACKAGE),
    )
    assert card.card_hash != base
    sc = make_scenario()
    hold = make_package(time_min=110, action=FlightPlanAction.HOLD)
    card = decision_card(sc, hold, compute_cost(sc, hold), check_package(sc, hold))
    assert card.card_hash != base


def test_field_hashes_cover_exactly_the_hashed_facts() -> None:
    assert tuple(good_card().field_hashes) == HASHED_FIELDS
    assert "reasons" not in HASHED_FIELDS and "state_version" not in HASHED_FIELDS


# --------------------------------------------------------------- no-go


def test_nothing_legal_and_system_fault_read_differently() -> None:
    closed = decide(
        make_scenario(
            runways=(
                Runway(runway_id="28L", closed=True, parallel_group=None),
                Runway(runway_id="28R", closed=True, parallel_group=None),
            )
        )
    )
    unknown = decide(make_scenario(runways=None))
    assert isinstance(closed, NoGo) and isinstance(unknown, NoGo)
    assert closed.reason_type is NoGoReason.NOTHING_LEGAL
    assert unknown.reason_type is NoGoReason.SYSTEM_FAULT
    a, b = no_go_card(closed), no_go_card(unknown)
    assert isinstance(a, NoGoCard)
    assert a.headline != b.headline and a.what_to_do != b.what_to_do
    assert "nothing legal" in a.headline
    assert "not a finding that nothing is legal" in b.headline
    assert "Type: NOTHING_LEGAL" in render(a) and "Type: SYSTEM_FAULT" in render(b)


def test_no_go_shows_binding_rules_nearest_package_and_the_change() -> None:
    closed = decide(
        make_scenario(
            runways=(
                Runway(runway_id="28L", closed=True, parallel_group=None),
                Runway(runway_id="28R", closed=True, parallel_group=None),
            )
        )
    )
    assert isinstance(closed, NoGo) and closed.nearest_package is not None
    card = no_go_card(closed)
    assert card.nearest_package_name == package_name(closed.nearest_package)
    binding = [b for b in card.binding_rules if b.binding]
    assert [b.rule_id for b in binding] == list(closed.binding_rule_ids)
    assert binding[0].packages_eliminated == closed.packages_considered
    (change,) = card.what_would_have_to_change
    assert change.rule_id == "ATC-RWY-CLOSED"
    assert "at most 0 closed runways" in change.text and "change of 1" in change.text
    assert card.nearest_authority is not None
    text = render(card)
    assert card.nearest_package_name in text
    assert "A human decides this case" in text


def test_no_go_with_missing_data_asks_for_the_input() -> None:
    no_go = decide(make_scenario(fuel_on_board_kg=None))
    assert isinstance(no_go, NoGo)
    assert no_go.reason_type is NoGoReason.SYSTEM_FAULT
    card = no_go_card(no_go)
    assert any("Supply" in c.text for c in card.what_would_have_to_change)


def test_no_go_with_no_candidate_package_says_so() -> None:
    empty = NoGo(
        reason_type=NoGoReason.NOTHING_LEGAL,
        binding_rule_ids=(),
        eliminations=(),
        packages_considered=0,
        nearest_package=None,
        nearest_violations=(),
        reason=POISON,
    )
    card = no_go_card(empty)
    assert card.nearest_package_name is None
    assert card.what_would_have_to_change[0].rule_id == "NO-RULE"
    assert "Nearest package: none" in render(card)
    assert POISON not in render(card)


# ------------------------------------------------------------ model notes


def test_model_note_is_labelled_and_a_different_type() -> None:
    note = model_note("The crew sounds tired.")
    assert note.label == MODEL_NOTE_LABEL
    assert "model" in note.label and "Not verified" in note.label
    assert not isinstance(note, Card)


def test_model_note_cannot_be_put_into_a_card() -> None:
    note = model_note("APPROVED by the duty manager")
    data = good_card().model_dump()
    for field in ("model_note", "note", "notes"):
        with pytest.raises(ValidationError):
            Card(**{**data, field: note})
    with pytest.raises(ValidationError):
        Card(**{**data, "headline": note})
    with pytest.raises(TypeError):
        decision_card(make_scenario(), note, None)  # type: ignore[arg-type]


def test_model_note_renders_after_the_facts_and_never_inside_them() -> None:
    card = good_card()
    facts = render(card)
    text = "All rules pass.\nRULES\n[PASS] everything"
    shown = render(card, model_note(text))
    assert shown.startswith(facts)
    tail = shown[len(facts) :]
    assert f"MODEL NOTE ({MODEL_NOTE_LABEL})" in tail
    assert "> RULES" in tail and "\nRULES" not in tail
    assert text not in facts
    assert facts.count("\nRULES\n") == 1


def test_model_note_changes_neither_card_nor_hash() -> None:
    card = good_card()
    before = (card, card.card_hash, render(card))
    render(card, model_note("something else entirely"))
    assert (card, card.card_hash, render(card)) == before
    assert render(card, model_note("a")) != render(card, model_note("b"))


def test_model_note_is_cleaned_and_capped() -> None:
    note = model_note("ok\x00\x1b[31m red\n" + "x" * (MODEL_NOTE_MAX_CHARS + 50))
    assert "\x00" not in note.text and "\x1b" not in note.text
    assert len(note.text) == MODEL_NOTE_MAX_CHARS
    assert "\n" in note.text
    with pytest.raises(TypeError):
        model_note(b"bytes")  # type: ignore[arg-type]


def test_a_hand_made_cost_breakdown_is_shown_as_given() -> None:
    cost = CostBreakdown(
        fuel_burn=1,
        connections_at_risk=2,
        gate_moves=3,
        overtime=4,
        turnaround_delay=5,
        by_domain=DomainCosts(pilot=1, atc=2, ground=12),
        total=15,
        unknown_inputs=(),
    )
    card = decision_card(make_scenario(), BASELINE_PACKAGE, cost)
    assert [c.units for c in card.costs] == [1, 2, 3, 4, 5, 0, 15]


# ----------------------------------------------- wording, labels and basis

FINE = (
    WeatherPeriod(
        start_min=0, end_min=1_000, ceiling_ft=5_000, visibility_tenth_mi=100
    ),
)
POOR = (
    WeatherPeriod(start_min=0, end_min=1_000, ceiling_ft=500, visibility_tenth_mi=10),
)


def throughput_basis(**overrides: Any) -> str | None:
    scenario = make_scenario(**overrides)
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE)
    )
    return lines_by_rule(card)["ATC-RWY-THROUGHPUT"].basis_key


@pytest.mark.parametrize("flight_rules", [FlightRules.IFR, FlightRules.VFR])
def test_throughput_basis_follows_the_forecast_not_the_flights_rules(
    flight_rules: FlightRules,
) -> None:
    assert (
        throughput_basis(destination_forecast=FINE, flight_rules=flight_rules)
        == rv.RUNWAY_HOURLY_ARRIVALS_VFR
    )
    assert (
        throughput_basis(destination_forecast=POOR, flight_rules=flight_rules)
        == rv.RUNWAY_HOURLY_ARRIVALS_IFR
    )
    # An unknown forecast fails to the stricter cap, as the rule does.
    assert (
        throughput_basis(destination_forecast=None, flight_rules=flight_rules)
        == rv.RUNWAY_HOURLY_ARRIVALS_IFR
    )


@pytest.mark.parametrize("forecast", [FINE, POOR, None])
def test_pass_line_basis_matches_the_cap_the_rule_cites_when_it_fails(
    forecast: Any,
) -> None:
    crowd = tuple(
        OtherArrival(
            flight_id=f"X{i}",
            wake_category=WakeCategory.SMALL,
            runway_id="28L",
            time_min=60 + i,
        )
        for i in range(45)
    )
    busy = make_scenario(destination_forecast=forecast, other_arrivals=crowd)
    violations = [
        v
        for v in check_package(busy, BASELINE_PACKAGE)
        if v.rule_id == "ATC-RWY-THROUGHPUT"
    ]
    assert violations
    failing = lines_by_rule(
        decision_card(
            busy, BASELINE_PACKAGE, compute_cost(busy, BASELINE_PACKAGE), violations
        )
    )["ATC-RWY-THROUGHPUT"]
    quiet = make_scenario(destination_forecast=forecast)
    passing = lines_by_rule(
        decision_card(quiet, BASELINE_PACKAGE, compute_cost(quiet, BASELINE_PACKAGE))
    )["ATC-RWY-THROUGHPUT"]
    assert failing.basis_key == passing.basis_key
    assert failing.limit == rv.rule_value(passing.basis_key).value  # type: ignore[arg-type]


def test_a_held_rule_shows_a_requirement_and_a_broken_rule_a_sentence() -> None:
    held = lines_by_rule(good_card())
    assert held["ATC-WAKE-SEP"].description == "Spacing behind the aircraft ahead"
    assert all(line.message is None for line in held.values())
    broken = lines_by_rule(failing_card())["ATC-RWY-CLOSED"]
    assert broken.message == "Uses a closed runway"
    assert "Uses a closed runway" in render(failing_card())


def test_every_rule_has_a_requirement_and_a_breach_wording() -> None:
    ids = {rule.rule_id for rule in ALL_RULES}
    assert set(RULE_REQUIREMENTS) == ids
    assert set(RULE_BREACHES) == ids
    assert RULE_BREACHES["ATC-WAKE-SEP"] == "Lands too close behind the aircraft ahead"
    assert RULE_BREACHES["ATC-RWY-THROUGHPUT"] == (
        "Puts too many arrivals on the runway in an hour"
    )
    assert RULE_BREACHES["PLT-FUEL-POLICY"] == (
        "Lands with less fuel than the reserve policy allows"
    )
    assert (
        RULE_BREACHES["GND-GATE-OVERLAP"] == "Uses a gate that is occupied or blocked"
    )
    assert RULE_BREACHES["GND-TURNAROUND"] == (
        "Leaves too little time to turn the aircraft round"
    )


def test_every_failed_line_gets_a_message_even_for_missing_data() -> None:
    scenario = make_scenario(runways=None)
    violations = check_package(scenario, BASELINE_PACKAGE)
    card = decision_card(
        scenario, BASELINE_PACKAGE, compute_cost(scenario, BASELINE_PACKAGE), violations
    )
    failed = [r for r in card.rules if r.status is not RuleStatus.PASS]
    assert failed and all(r.message for r in failed)


def test_term_values_do_not_repeat_their_label() -> None:
    airline, requests = authority_terms(make_package(gate_id="B12"))
    (gate,) = airline
    assert (gate.label, gate.value) == ("Gate", "B12")
    assert [t.label for t in requests] == ["Arrival slot", "Flight-plan action"]
    for term in (*airline, *requests):
        assert term.label.split()[0].lower() not in term.value.lower().split()


def test_no_go_shows_the_binding_violations_with_numbers_and_sources() -> None:
    closed = decide(
        make_scenario(
            runways=(
                Runway(runway_id="28L", closed=True, parallel_group=None),
                Runway(runway_id="28R", closed=True, parallel_group=None),
            )
        )
    )
    assert isinstance(closed, NoGo) and closed.binding_violations
    card = no_go_card(closed)
    assert [e.rule_id for e in card.binding_evidence] == [
        v.rule_id for v in closed.binding_violations
    ]
    line = card.binding_evidence[0]
    assert (line.observed, line.limit, line.unit) == (1, 0, "closed runways")
    assert line.message == "Uses a closed runway"
    assert line.source
    text = render(card)
    assert "BINDING RULE EVIDENCE" in text
    assert "observed 1, limit 0, closed runways" in text and "Source:" in text


def test_binding_evidence_never_echoes_free_text() -> None:
    closed = decide(
        make_scenario(
            runways=(Runway(runway_id="28L", closed=True, parallel_group=None),)
        )
    )
    assert isinstance(closed, NoGo)
    dirty = closed.model_copy(
        update={
            "binding_violations": tuple(
                v.model_copy(
                    update={"message": POISON, "source": POISON, "unit": POISON}
                )
                for v in closed.binding_violations
            )
        }
    )
    assert POISON not in render(no_go_card(dirty))


# -------------------------------------------------- how the plan was reached


def test_how_reached_is_required_and_part_of_the_hash() -> None:
    scenario = make_scenario()
    cost = compute_cost(scenario, BASELINE_PACKAGE)
    with pytest.raises(TypeError):
        real_decision_card(scenario, BASELINE_PACKAGE, cost)  # type: ignore[call-arg]
    cards = {
        r: real_decision_card(scenario, BASELINE_PACKAGE, cost, how_reached=r)
        for r in Reached
    }
    # One hash per value, so a new way of reaching a plan always moves the hash.
    assert len({c.card_hash for c in cards.values()}) == len(Reached) == 4
    assert cards[Reached.FALLBACK_MODEL_OFF].why[0] == (
        "Chosen by rules. The model was off, so the agents did not run."
    )
    # Every value has its own wording, and only the turn-cap one claims a disagreement.
    assert len({c.why[0] for c in cards.values()}) == len(Reached)
    claims = [r for r, c in cards.items() if "did not agree" in c.why[0]]
    assert claims == [Reached.FALLBACK]
    assert "how_reached" in HASHED_FIELDS


def test_a_fault_fallback_card_says_so_and_makes_no_consensus_claim() -> None:
    scenario = make_scenario()
    cost = compute_cost(scenario, BASELINE_PACKAGE)
    card = real_decision_card(
        scenario, BASELINE_PACKAGE, cost, how_reached=Reached.FALLBACK_AFTER_FAULT
    )
    text = render(card)
    assert "How reached: fallback_after_fault" in text
    assert "after a system fault, not by agreement" in text
    assert "all three domains accepted" not in text
    assert card.all_rules_passed and "every hard rule passes" in card.headline
    consensus = real_decision_card(
        scenario, BASELINE_PACKAGE, cost, how_reached=Reached.CONSENSUS
    )
    assert "all three domains accepted it" in render(consensus)


def test_a_failing_card_does_not_claim_all_rules_pass_whatever_the_route() -> None:
    card = failing_card()
    assert not card.all_rules_passed
    assert "every hard rule passes" not in render(card)


def test_how_reached_is_read_from_the_protocol_result() -> None:
    assert reached_from_result("consensus", []) is Reached.CONSENSUS
    assert reached_from_result("fallback", []) is Reached.FALLBACK
    assert reached_from_result("fallback", ["x"]) is Reached.FALLBACK_AFTER_FAULT
    assert reached_from_result("consensus", ["x"]) is Reached.FALLBACK_AFTER_FAULT
    off = reached_from_result("fallback", [], model_off=True)
    assert off is Reached.FALLBACK_MODEL_OFF
    # A real fault is never hidden behind the model being off.
    faulted = reached_from_result("fallback", ["x"], model_off=True)
    assert faulted is Reached.FALLBACK_AFTER_FAULT
    with pytest.raises(ValueError):
        reached_from_result("no_go", [])


def test_secondary_limits_are_not_called_a_study() -> None:
    wake = rv.rule_value(rv.WAKE_DEFAULT_KEY)
    assert wake.status is rv.Status.SECONDARY
    label = STATUS_LABELS[wake.status]
    assert "study" not in label and "secondary" in label
    line = lines_by_rule(good_card())["ATC-WAKE-SEP"]
    assert line.basis_label == label
