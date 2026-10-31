"""Sign-off: approves only the exact package, state and card the manager saw."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.negotiation.card import (
    decision_card,
    model_note,
    package_name,
    render,
)
from app.negotiation.contracts import (
    AircraftSize,
    ArrivalSlot,
    Connection,
    FlightPlanAction,
    Gate,
    GateOccupancy,
    Package,
    Proposal,
    Provenance,
    Runway,
    Scenario,
    Sourced,
)
from app.negotiation.log import EvidenceLog, verify_entries
from app.negotiation.rules import check_package
from app.negotiation.signoff import (
    UNATTRIBUTED,
    SignOffOutcome,
    SignOffRequest,
    SignOffStatus,
    field_versions,
    render_record,
    sign_off,
    state_version,
)
from app.negotiation.utility import DEFAULT_WEIGHTS, CostWeights, compute_cost
from tests.negotiation.factories import BASELINE_PACKAGE, make_package, make_scenario

PACKAGE = BASELINE_PACKAGE
HOLD = make_package(time_min=110, action=FlightPlanAction.HOLD)


def view(
    scenario: Scenario,
    package: Package = PACKAGE,
    *,
    weights: CostWeights = DEFAULT_WEIGHTS,
    detail: bool = True,
    **overrides: Any,
) -> SignOffRequest:
    """The request a manager would send after looking at this scenario."""
    card = decision_card(
        scenario,
        package,
        compute_cost(scenario, package, weights),
        check_package(scenario, package),
    )
    fields: dict[str, Any] = {
        "terms_hash": package.terms_hash,
        "state_version_seen": state_version(scenario),
        "card_hash_seen": card.card_hash,
        "decided_by": "duty.manager@example.com",
        "airline_decisions_approved": True,
        "requests_to_send": True,
    }
    if detail:
        fields["field_versions_seen"] = dict(field_versions(scenario))
        fields["card_field_hashes_seen"] = dict(card.field_hashes)
    return SignOffRequest(**{**fields, **overrides})


def run(
    request: SignOffRequest,
    scenario: Scenario,
    package: Package = PACKAGE,
    log: EvidenceLog | None = None,
    used: set[str] | None = None,
    **kwargs: Any,
) -> tuple[SignOffOutcome, EvidenceLog, set[str]]:
    log = log if log is not None else EvidenceLog()
    used = used if used is not None else set()
    return sign_off(request, package, scenario, log, used, **kwargs), log, used


# ------------------------------------------------------------- approval


def test_unchanged_everything_is_approved() -> None:
    scenario = make_scenario()
    outcome, log, used = run(view(scenario), scenario)
    assert outcome.status is SignOffStatus.APPROVED
    assert outcome.violations == ()
    assert outcome.changed_fields == () and outcome.changed_card_fields == ()
    assert [t.name for t in outcome.airline_decisions] == ["gate_id"]
    assert [t.name for t in outcome.requests] == ["slot", "action"]
    assert outcome.package_name == package_name(PACKAGE)
    assert len(used) == 1


def test_outcome_is_logged_with_card_hash_and_an_anchorable_head() -> None:
    scenario = make_scenario()
    request = view(scenario)
    outcome, log, _ = run(request, scenario)
    (entry,) = log.entries
    assert entry.kind == "signoff"
    assert outcome.log_head == entry.entry_hash == log.head
    assert entry.payload["card_hash"] == outcome.card_hash == request.card_hash_seen
    assert entry.payload["status"] == "APPROVED"
    assert entry.payload["log_head_before"] == "0" * 64
    assert entry.payload["executed"] is False
    assert entry.payload["requests_issued_not_granted"] is True
    assert entry.payload["package_name"] == package_name(PACKAGE)
    log.append("later", {"n": 1})
    assert verify_entries(log.entries, anchored_head=outcome.log_head).valid


def test_record_prints_card_hash_and_log_head_and_does_not_claim_execution() -> None:
    scenario = make_scenario()
    outcome, _, _ = run(view(scenario), scenario)
    record = render_record(outcome)
    assert outcome.card_hash in record and outcome.log_head in record
    assert package_name(PACKAGE) in record
    assert "Requests were issued, not granted. Nothing has been executed." in record
    assert "Gate: A1" in record


def test_only_the_parts_the_manager_chose_are_approved() -> None:
    scenario = make_scenario()
    outcome, _, _ = run(view(scenario, requests_to_send=False), scenario)
    assert outcome.status is SignOffStatus.APPROVED
    assert [t.name for t in outcome.airline_decisions] == ["gate_id"]
    assert outcome.requests == ()
    outcome, _, _ = run(view(scenario, airline_decisions_approved=False), scenario)
    assert outcome.airline_decisions == ()
    assert [t.name for t in outcome.requests] == ["slot", "action"]


def test_a_request_must_approve_something_and_name_the_person() -> None:
    scenario = make_scenario()
    with pytest.raises(ValidationError):
        view(scenario, airline_decisions_approved=False, requests_to_send=False)
    with pytest.raises(ValidationError):
        view(scenario, decided_by="   ")


def test_sign_off_is_deterministic() -> None:
    scenario = make_scenario()
    first, log_a, _ = run(view(scenario), scenario)
    second, log_b, _ = run(view(scenario), scenario)
    assert first == second
    assert log_a.head == log_b.head


# ------------------------------------------------------- state version


def test_state_version_is_stable_and_a_hash() -> None:
    a, b = state_version(make_scenario()), state_version(make_scenario())
    assert a == b and len(a) == 64
    assert int(a, 16) >= 0


@pytest.mark.parametrize(
    "change",
    [
        {
            "runways": (
                Runway(runway_id="28L", closed=True),
                Runway(runway_id="28R", closed=False),
            )
        },
        {
            "gates": (
                Gate(gate_id="A1", taxiway_id="T1", max_size=AircraftSize.REGIONAL),
            )
        },
        {"gate_occupancies": ()},
        {"other_arrivals": ()},
        {"fuel_on_board_kg": 9_999},
        {"ground_shift_end_min": 301},
        {"connections": (Connection(passengers=21, departure_min=150),)},
        {"planned_gate": "A2"},
        {"earliest_arrival_min": 101},
        {"next_leg_turnaround_hard": False},
        {"destination_forecast": None},
    ],
)
def test_every_kind_of_operational_change_moves_the_state_version(
    change: dict[str, Any],
) -> None:
    assert state_version(make_scenario(**change)) != state_version(make_scenario())


def test_a_provenance_relabel_moves_the_state_version() -> None:
    relabelled = make_scenario(provenance=Provenance.REAL)
    assert state_version(relabelled) != state_version(make_scenario())


# ------------------------------------------------------------- refusals


def test_changed_gate_is_refused_and_names_the_field() -> None:
    seen = make_scenario()
    request = view(seen)
    now = make_scenario(
        gates=(
            Gate(gate_id="A1", taxiway_id="T1", max_size=AircraftSize.REGIONAL),
            Gate(gate_id="A2", taxiway_id="T1", max_size=AircraftSize.REGIONAL),
            Gate(gate_id="B1", taxiway_id="T2", max_size=AircraftSize.WIDE_BODY),
        )
    )
    outcome, log, used = run(request, now)
    assert outcome.status is SignOffStatus.REFUSED_STATE_CHANGED
    assert outcome.changed_fields == ("gates",)
    assert outcome.airline_decisions == () and outcome.requests == ()
    assert used == set()
    assert log.entries[0].payload["status"] == "REFUSED_STATE_CHANGED"
    assert "State fields changed: gates" in render_record(outcome)


def test_gate_occupancy_appearing_while_reading_is_refused() -> None:
    now = make_scenario(
        gate_occupancies=(
            GateOccupancy(gate_id="A1", flight_id="NEW", start_min=100, end_min=140),
        )
    )
    outcome, _, _ = run(view(make_scenario()), now)
    assert outcome.status is SignOffStatus.REFUSED_STATE_CHANGED
    assert outcome.changed_fields == ("gate_occupancies",)
    assert {v.rule_id for v in outcome.violations} == {"GND-GATE-OVERLAP"}


def test_closed_runway_is_refused_with_the_violation() -> None:
    now = make_scenario(
        runways=(
            Runway(runway_id="28L", closed=True),
            Runway(runway_id="28R", closed=False),
        )
    )
    outcome, _, used = run(view(make_scenario()), now)
    assert outcome.status is SignOffStatus.REFUSED_STATE_CHANGED
    assert outcome.changed_fields == ("runways",)
    assert [v.rule_id for v in outcome.violations] == ["ATC-RWY-CLOSED"]
    assert used == set()


def test_changed_state_without_field_detail_cannot_name_the_field() -> None:
    now = make_scenario(planned_gate="A2")
    outcome, _, _ = run(view(make_scenario(), detail=False), now)
    assert outcome.status is SignOffStatus.REFUSED_STATE_CHANGED
    assert outcome.changed_fields == (UNATTRIBUTED,)


def test_field_detail_that_does_not_add_up_is_not_trusted() -> None:
    seen = make_scenario()
    forged = dict(field_versions(make_scenario(planned_gate="A2")))
    request = view(seen, field_versions_seen=forged)
    outcome, _, _ = run(request, make_scenario(planned_gate="A2"))
    assert outcome.status is SignOffStatus.REFUSED_STATE_CHANGED
    assert outcome.changed_fields == (UNATTRIBUTED,)


def test_changed_package_is_refused() -> None:
    scenario = make_scenario()
    request = view(scenario)
    other = make_package(time_min=105, action=FlightPlanAction.VECTOR)
    outcome, log, used = run(request, scenario, package=other)
    assert outcome.status is SignOffStatus.REFUSED_PACKAGE_CHANGED
    assert outcome.package_name == package_name(other)
    assert used == set()
    assert log.entries[0].payload["terms_hash_seen"] == PACKAGE.terms_hash


def test_each_term_of_the_package_counts_as_a_change() -> None:
    scenario = make_scenario()
    request = view(scenario)
    for other in (
        make_package(gate_id="A2"),
        make_package(runway_id="28R"),
        make_package(time_min=101),
    ):
        outcome, _, _ = run(request, scenario, package=other)
        assert outcome.status is SignOffStatus.REFUSED_PACKAGE_CHANGED


def test_used_token_is_refused_and_does_not_re_record_an_approval() -> None:
    scenario = make_scenario()
    request = view(scenario)
    first, log, used = run(request, scenario)
    second, _, _ = run(request, scenario, log=log, used=used)
    assert first.status is SignOffStatus.APPROVED
    assert second.status is SignOffStatus.REFUSED_ALREADY_USED
    assert second.airline_decisions == () and second.requests == ()
    assert [e.payload["status"] for e in log.entries] == [
        "APPROVED",
        "REFUSED_ALREADY_USED",
    ]
    assert verify_entries(log.entries).valid


def test_a_different_view_gets_its_own_token() -> None:
    scenario = make_scenario()
    log, used = EvidenceLog(), set[str]()
    first, _, _ = run(view(scenario), scenario, log=log, used=used)
    changed = make_scenario(planned_gate="A1", ground_shift_end_min=310)
    second, _, _ = run(view(changed), changed, log=log, used=used)
    assert first.status is second.status is SignOffStatus.APPROVED
    assert len(used) == 2


def test_a_refusal_does_not_use_the_token() -> None:
    scenario = make_scenario()
    request = view(scenario)
    refused, log, used = run(request, make_scenario(planned_gate="A2"))
    assert refused.status is SignOffStatus.REFUSED_STATE_CHANGED
    approved, _, _ = run(request, scenario, log=log, used=used)
    assert approved.status is SignOffStatus.APPROVED


def test_rule_failing_at_current_state_is_refused_even_if_the_manager_saw_it() -> None:
    failing = make_scenario(
        runways=(
            Runway(runway_id="28L", closed=True),
            Runway(runway_id="28R", closed=False),
        )
    )
    request = view(failing)  # state and card both match what is current
    outcome, _, used = run(request, failing)
    assert outcome.status is SignOffStatus.REFUSED_RULES_FAILED
    assert outcome.violations == check_package(failing, PACKAGE)
    assert used == set()
    assert outcome.airline_decisions == () and outcome.requests == ()


@pytest.mark.parametrize(
    ("change", "rule_id"),
    [
        ({"fuel_on_board_kg": 5_000}, "PLT-FUEL-POLICY"),
        ({"taxi_in_min": 95}, "GND-TURNAROUND"),
        (
            {
                "gate_occupancies": (
                    GateOccupancy(
                        gate_id="A1", flight_id="X", start_min=100, end_min=150
                    ),
                )
            },
            "GND-GATE-OVERLAP",
        ),
        ({"aircraft_size": AircraftSize.WIDE_BODY}, "GND-GATE-SIZE"),
    ],
)
def test_all_rules_are_re_run_not_just_the_runway(
    change: dict[str, Any], rule_id: str
) -> None:
    now = make_scenario(**change)
    outcome, _, _ = run(view(now), now)
    assert outcome.status is SignOffStatus.REFUSED_RULES_FAILED
    assert rule_id in {v.rule_id for v in outcome.violations}
    assert outcome.violations == check_package(now, PACKAGE)


def test_missing_data_fails_closed() -> None:
    now = make_scenario(runways=None)
    outcome, _, _ = run(view(now), now)
    assert outcome.status is SignOffStatus.REFUSED_RULES_FAILED


def test_state_change_wins_over_package_and_token_wins_over_both() -> None:
    scenario = make_scenario()
    request = view(scenario)
    now = make_scenario(planned_gate="A2")
    other = make_package(time_min=105, action=FlightPlanAction.VECTOR)
    outcome, log, used = run(request, now, package=other)
    assert outcome.status is SignOffStatus.REFUSED_PACKAGE_CHANGED
    used.add(request.token)
    outcome, _, _ = run(request, now, package=other, log=log, used=used)
    assert outcome.status is SignOffStatus.REFUSED_ALREADY_USED


# ---------------------------------------------------------- card sign-off


def test_changed_card_is_refused_and_names_the_fields() -> None:
    scenario = make_scenario()
    cheap = view(scenario, HOLD)  # card the manager saw: default weights
    dearer = CostWeights(
        fuel_per_kg=9,
        per_passenger_at_risk=100,
        per_gate_move=50,
        overtime_per_min=20,
        turnaround_delay_per_min=30,
    )
    assert check_package(scenario, HOLD) == ()
    outcome, log, used = run(cheap, scenario, package=HOLD, weights=dearer)
    assert outcome.status is SignOffStatus.REFUSED_CARD_CHANGED
    assert outcome.violations == ()
    assert "costs" in outcome.changed_card_fields
    assert outcome.card_hash != cheap.card_hash_seen
    assert used == set()
    payload = log.entries[0].payload
    assert payload["card_hash_seen"] == cheap.card_hash_seen
    assert payload["card_hash"] == outcome.card_hash
    assert "Card fields changed: " in render_record(outcome)
    assert outcome.card_hash in render_record(outcome)


def test_a_card_hash_that_is_not_the_one_shown_is_refused() -> None:
    scenario = make_scenario()
    outcome, _, _ = run(view(scenario, card_hash_seen="0" * 64), scenario)
    assert outcome.status is SignOffStatus.REFUSED_CARD_CHANGED
    # The per-field detail does not add up to that hash, so nothing is named.
    assert outcome.changed_card_fields == (UNATTRIBUTED,)


def test_a_changed_card_without_field_detail_cannot_name_the_fields() -> None:
    scenario = make_scenario()
    outcome, _, _ = run(view(scenario, detail=False, card_hash_seen="1" * 64), scenario)
    assert outcome.status is SignOffStatus.REFUSED_CARD_CHANGED
    assert outcome.changed_card_fields == (UNATTRIBUTED,)


def test_unchanged_card_is_approved_with_the_same_hash() -> None:
    scenario = make_scenario()
    request = view(scenario, HOLD)
    outcome, _, _ = run(request, scenario, package=HOLD)
    assert outcome.status is SignOffStatus.APPROVED
    assert outcome.card_hash == request.card_hash_seen


# ------------------------------------------------- explanations don't block


def test_a_changed_explanation_changes_neither_terms_hash_nor_sign_off() -> None:
    one = Proposal(turn=1, author="atc", package=PACKAGE, reason="Because of wind.")  # type: ignore[arg-type]
    two = Proposal(turn=1, author="atc", package=PACKAGE, reason="Completely new text.")  # type: ignore[arg-type]
    assert one.package.terms_hash == two.package.terms_hash

    scenario = make_scenario()
    request = view(scenario)
    explained = decision_card(
        scenario,
        PACKAGE,
        compute_cost(scenario, PACKAGE),
        check_package(scenario, PACKAGE),
        reason_codes=["PREFER_PLANNED_GATE", "PREFER_LOW_FUEL_BURN"],
        state_version=state_version(scenario),
    )
    assert explained.card_hash == request.card_hash_seen
    assert explained.terms_hash == request.terms_hash
    outcome, _, _ = run(request, scenario)
    assert outcome.status is SignOffStatus.APPROVED


def test_a_changed_model_note_does_not_touch_the_card_hash_or_block_sign_off() -> None:
    scenario = make_scenario()
    card = decision_card(
        scenario,
        PACKAGE,
        compute_cost(scenario, PACKAGE),
        check_package(scenario, PACKAGE),
    )
    before = card.card_hash
    shown_a = render(card, model_note("Looks fine to me."))
    shown_b = render(card, model_note("I would not do this."))
    assert shown_a != shown_b
    assert card.card_hash == before
    request = view(scenario)
    assert request.card_hash_seen == before
    outcome, _, _ = run(request, scenario)
    assert outcome.status is SignOffStatus.APPROVED


def test_terms_hash_ignores_everything_but_the_terms() -> None:
    same = Package(
        slot=ArrivalSlot(runway_id="28L", time_min=100),
        gate_id="A1",
        action=FlightPlanAction.DIRECT,
    )
    assert same.terms_hash == PACKAGE.terms_hash


# ----------------------------------------------------------- failures


def test_if_the_log_cannot_record_there_is_no_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = make_scenario()
    log, used = EvidenceLog(), set[str]()

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(log, "append", boom)
    with pytest.raises(OSError):
        sign_off(view(scenario), PACKAGE, scenario, log, used)
    assert used == set()


def test_outcomes_are_immutable() -> None:
    scenario = make_scenario()
    outcome, _, _ = run(view(scenario), scenario)
    with pytest.raises(ValidationError):
        outcome.status = SignOffStatus.REFUSED_ALREADY_USED  # type: ignore[misc]


def test_sourced_scenarios_with_unknown_fields_still_have_a_version() -> None:
    scenario = make_scenario()
    unknown = scenario.model_copy(
        update={"planned_gate": Sourced(value=None, provenance=Provenance.SYNTHETIC)}
    )
    assert state_version(unknown) != state_version(scenario)
