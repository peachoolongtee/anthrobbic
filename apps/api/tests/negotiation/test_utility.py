from app.negotiation.contracts import (
    AircraftSize,
    Connection,
    FlightPlanAction,
    GateOccupancy,
    NoGo,
)
from app.negotiation.fallback import decide
from app.negotiation.utility import DEFAULT_WEIGHTS, compute_cost, weight_sensitivity
from tests.negotiation.factories import (
    BASELINE_PACKAGE,
    make_package,
    make_scenario,
)


def test_unknown_soft_inputs_are_listed_not_hidden() -> None:
    scenario = make_scenario(
        connections=None, ground_shift_end_min=None, next_departure_min=None
    )
    cost = compute_cost(scenario, BASELINE_PACKAGE)
    assert cost.unknown_inputs == (
        "connections",
        "ground_shift_end_min",
        "next_departure_min",
    )
    assert (cost.connections_at_risk, cost.overtime, cost.turnaround_delay) == (0, 0, 0)


def test_unknown_planned_gate_counts_as_a_gate_move() -> None:
    cost = compute_cost(make_scenario(planned_gate=None), BASELINE_PACKAGE)
    assert cost.gate_moves == DEFAULT_WEIGHTS.per_gate_move
    assert "planned_gate" in cost.unknown_inputs


def test_weights_scale_the_components() -> None:
    scenario = make_scenario()
    hold = make_package(120, action=FlightPlanAction.HOLD)
    base = compute_cost(scenario, hold)
    doubled = compute_cost(
        scenario,
        hold,
        DEFAULT_WEIGHTS.model_copy(
            update={"fuel_per_kg": DEFAULT_WEIGHTS.fuel_per_kg * 2}
        ),
    )
    assert base.fuel_burn > 0
    assert doubled.fuel_burn == 2 * base.fuel_burn


def test_costs_never_override_a_rule() -> None:
    # Make every soft cost free and a rule violation very attractive: a package
    # that breaks a rule is still not chosen.
    free = DEFAULT_WEIGHTS.model_copy(
        update={name: 0 for name in type(DEFAULT_WEIGHTS).model_fields}
    )
    scenario = make_scenario(
        aircraft_size=AircraftSize.WIDE_BODY,
        gate_occupancies=(),
    )
    result = decide(scenario, free)
    assert not isinstance(result, NoGo)
    assert result.package.gate_id == "B1"  # the only wide-body gate
    # And a rule-breaking package keeps its cost without gaining legality.
    assert compute_cost(scenario, make_package(gate_id="A2"), free).total == 0


def blocked_g1_scenario():  # noqa: ANN201
    # Gate A1 is occupied until 105, and the buffer is 15 min after that, so a
    # stay starting at gate-in 110 or 115 is too close (5 and 10 min clear) and
    # only slot 110 (gate-in 120, exactly 15 clear) or later can use A1. Gate B1
    # is free at any time but is a gate move from the planned A1.
    return make_scenario(
        latest_arrival_min=120,
        gate_occupancies=(
            GateOccupancy(gate_id="A1", flight_id="OLD", start_min=80, end_min=105),
        ),
        connections=(Connection(passengers=0, departure_min=0),),
    )


def test_sensitivity_reports_a_changed_choice() -> None:
    scenario = blocked_g1_scenario()
    default_choice = decide(scenario)
    assert not isinstance(default_choice, NoGo)
    # Default: moving to B1 (50) beats holding on A1 (400 or more).
    assert default_choice.package.gate_id == "B1"
    expensive_moves = DEFAULT_WEIGHTS.model_copy(update={"per_gate_move": 5000})
    report = weight_sensitivity(scenario, expensive_moves)
    assert report.changed
    assert report.default_package == default_choice.package
    assert report.alternate_package is not None
    assert report.alternate_package.gate_id == "A1"


def test_sensitivity_reports_no_change_when_the_choice_is_robust() -> None:
    scenario = make_scenario()
    report = weight_sensitivity(
        scenario, DEFAULT_WEIGHTS.model_copy(update={"per_gate_move": 1})
    )
    assert not report.changed
    assert report.default_package == report.alternate_package


def test_sensitivity_of_a_no_go_is_none_and_unchanged() -> None:
    scenario = make_scenario(fuel_on_board_kg=None)
    report = weight_sensitivity(scenario, DEFAULT_WEIGHTS)
    assert report.default_package is None
    assert report.alternate_package is None
    assert not report.changed
