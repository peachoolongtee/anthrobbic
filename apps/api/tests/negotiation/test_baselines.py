"""The baselines do what they claim, and report the rules they break."""

import pytest

from app.negotiation.baselines import (
    NATURAL_UNITS,
    BaselineName,
    first_come_first_served,
    human_heuristic,
    package_metrics,
    run_baselines,
)
from app.negotiation.contracts import (
    DecisionPoint,
    FlightPlanAction,
    GateOccupancy,
    Runway,
)
from app.negotiation.rules import check_package
from app.negotiation.utility import CostWeights
from tests.negotiation.factories import make_package, make_scenario, random_scenario

CLOSED_28L = (
    Runway(runway_id="28L", closed=True, parallel_group=None),
    Runway(runway_id="28R", closed=False, parallel_group=None),
)
# Gate-in at 110 is 10 min after this ends, so A1 needs the slot at 105.
A1_BUSY = GateOccupancy(gate_id="A1", flight_id="O", start_min=20, end_min=100)
B1_BUSY = GateOccupancy(gate_id="B1", flight_id="O2", start_min=0, end_min=400)


def test_natural_units_cover_every_weight() -> None:
    assert set(NATURAL_UNITS.model_dump()) == set(CostWeights.model_fields)
    assert set(NATURAL_UNITS.model_dump().values()) == {1}


def test_fcfs_takes_earliest_first_runway_lowest_gate() -> None:
    assert first_come_first_served(make_scenario()) == make_package()


def test_fcfs_ignores_a_closed_runway_and_the_outcome_says_so() -> None:
    fcfs, _ = run_baselines(make_scenario(runways=CLOSED_28L))
    assert fcfs.name is BaselineName.FIRST_COME_FIRST_SERVED
    assert fcfs.package == make_package()
    assert fcfs.broke_a_rule
    assert fcfs.violated_rule_ids == ("ATC-RWY-CLOSED",)
    assert fcfs.harm is not None and fcfs.harm.harmful


@pytest.mark.parametrize("field", ["earliest_arrival_min", "runways", "gates"])
def test_fcfs_with_nothing_to_name_has_no_package(field: str) -> None:
    fcfs, _ = run_baselines(make_scenario(**{field: None}))
    assert fcfs.package is None
    assert fcfs.metrics is None
    assert not fcfs.broke_a_rule


def test_human_keeps_the_planned_gate_when_legal() -> None:
    assert human_heuristic(make_scenario()) == make_package()


def test_human_avoids_a_closed_runway() -> None:
    package = human_heuristic(make_scenario(runways=CLOSED_28L))
    assert package == make_package(runway_id="28R")


def test_human_takes_the_next_slot_with_ground_delay_before_departure() -> None:
    package = human_heuristic(
        make_scenario(
            gate_occupancies=(A1_BUSY, B1_BUSY),
            decision_point=DecisionPoint.PRE_DEPARTURE,
        )
    )
    assert package == make_package(time_min=105, action=FlightPlanAction.GROUND_DELAY)


def test_human_holds_before_vectoring_in_the_air() -> None:
    package = human_heuristic(make_scenario(gate_occupancies=(A1_BUSY, B1_BUSY)))
    assert package == make_package(time_min=105, action=FlightPlanAction.HOLD)


def test_human_moves_gate_rather_than_wait() -> None:
    package = human_heuristic(make_scenario(gate_occupancies=(A1_BUSY,)))
    assert package == make_package(gate_id="B1")  # B1 is free in this scenario


def test_human_escalates_when_nothing_is_legal() -> None:
    all_closed = (
        Runway(runway_id="28L", closed=True, parallel_group=None),
        Runway(runway_id="28R", closed=True, parallel_group=None),
    )
    _, human = run_baselines(make_scenario(runways=all_closed))
    assert human.name is BaselineName.HUMAN_HEURISTIC
    assert human.package is None
    assert not human.broke_a_rule


def test_human_package_is_legal_on_random_scenarios_and_fcfs_breaks_rules() -> None:
    fcfs_breaks = 0
    for seed in range(300):
        scenario = random_scenario(seed)
        package = human_heuristic(scenario)
        if package is not None:
            assert not check_package(scenario, package), seed
        fcfs, human = run_baselines(scenario)
        assert not human.broke_a_rule
        fcfs_breaks += fcfs.broke_a_rule
    assert fcfs_breaks > 0  # the comparison would be empty otherwise


def test_metrics_read_in_natural_units() -> None:
    # Gate-in 125; the connection leaves at 150, and 125 + 30 > 150, so 20 pax.
    package = make_package(
        time_min=115, runway_id="28R", gate_id="B1", action=FlightPlanAction.HOLD
    )
    scenario = make_scenario(
        gate_occupancies=(),
        ground_shift_end_min=140,
        next_departure_min=145,
    )
    metrics = package_metrics(scenario, package)
    assert metrics.delay_min == 15
    assert metrics.fuel_burn_kg == 15 * 40
    # 10,000 - 4,000 - 600 = 5,400 landing. Required: 30 min x 40 kg = 1,200 of
    # holding fuel, 5% of 4,000 trip = 200 contingency, 1,000 alternate: 2,400.
    assert metrics.fuel_margin_kg == 3_000
    assert metrics.connection_passengers_at_risk == 20
    # Stay ends 125 + 35 = 160 (the airport's minimum turnaround): 20 min past
    # the shift end at 140, 15 past the next departure at 145.
    assert metrics.overtime_min == 20
    assert metrics.turnaround_delay_min == 15
    assert metrics.gate_moves == 1


def test_metrics_with_unknown_fuel_are_none_not_zero() -> None:
    metrics = package_metrics(make_scenario(fuel_on_board_kg=None), make_package())
    assert metrics.fuel_margin_kg is None
