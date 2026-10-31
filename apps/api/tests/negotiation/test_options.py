from typing import Any

import pytest

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    AircraftSize,
    DecisionPoint,
    FlightPlanAction,
    Gate,
    Package,
    Runway,
)
from app.negotiation.options import (
    PackageBoundError,
    enumerate_packages,
    enumeration_gaps,
    slot_times,
)
from tests.negotiation.factories import make_package, make_scenario

D, H, V, G = (
    FlightPlanAction.DIRECT,
    FlightPlanAction.HOLD,
    FlightPlanAction.VECTOR,
    FlightPlanAction.GROUND_DELAY,
)

# Runways and gates are given out of order on purpose.
SMALL: dict[str, Any] = {
    "earliest_arrival_min": 100,
    "latest_arrival_min": 105,
    "runways": (
        Runway(runway_id="R2", closed=False),
        Runway(runway_id="R1", closed=True),
    ),
    "gates": (
        Gate(gate_id="G2", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY),
        Gate(gate_id="G1", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY),
    ),
}


def p(time_min: int, runway: str, gate: str, action: FlightPlanAction) -> Package:
    return make_package(time_min, runway, gate, action)


def test_step_is_five_minutes() -> None:
    assert rv.rule_value(rv.SLOT_STEP_MIN).value == 5


def test_airborne_packages_are_exactly_these_in_this_order() -> None:
    # Slot 100 has no delay, so only DIRECT. Slot 105 has 5 min of delay, so HOLD
    # and VECTOR. Order: time, runway, gate, action. The closed runway R1 is
    # enumerated; the rules, not the enumerator, reject it.
    expected = (
        p(100, "R1", "G1", D),
        p(100, "R1", "G2", D),
        p(100, "R2", "G1", D),
        p(100, "R2", "G2", D),
        p(105, "R1", "G1", H),
        p(105, "R1", "G1", V),
        p(105, "R1", "G2", H),
        p(105, "R1", "G2", V),
        p(105, "R2", "G1", H),
        p(105, "R2", "G1", V),
        p(105, "R2", "G2", H),
        p(105, "R2", "G2", V),
    )
    scenario = make_scenario(decision_point=DecisionPoint.AIRBORNE, **SMALL)
    assert enumerate_packages(scenario) == expected


def test_pre_departure_packages_are_exactly_these() -> None:
    expected = (
        p(100, "R1", "G1", D),
        p(100, "R1", "G2", D),
        p(100, "R2", "G1", D),
        p(100, "R2", "G2", D),
        p(105, "R1", "G1", G),
        p(105, "R1", "G2", G),
        p(105, "R2", "G1", G),
        p(105, "R2", "G2", G),
    )
    scenario = make_scenario(decision_point=DecisionPoint.PRE_DEPARTURE, **SMALL)
    assert enumerate_packages(scenario) == expected


def test_unknown_decision_point_enumerates_every_absorbing_action() -> None:
    scenario = make_scenario(decision_point=None, **SMALL)
    at_105 = [x for x in enumerate_packages(scenario) if x.slot.time_min == 105]
    assert [x.action for x in at_105[:3]] == [H, V, G]
    assert len(at_105) == 12  # 3 actions x 2 runways x 2 gates
    assert len(enumerate_packages(scenario)) == 16


def test_enumeration_is_repeatable_and_ignores_input_order() -> None:
    scenario = make_scenario(**SMALL)
    reordered = make_scenario(
        **{**SMALL, "runways": SMALL["runways"][::-1], "gates": SMALL["gates"][::-1]}
    )
    assert enumerate_packages(scenario) == enumerate_packages(scenario)
    assert enumerate_packages(scenario) == enumerate_packages(reordered)


def test_packages_are_unique() -> None:
    packages = enumerate_packages(make_scenario(**SMALL))
    assert len({x.terms_hash for x in packages}) == len(packages)


def test_slot_grid_includes_both_ends_and_stays_on_the_step() -> None:
    assert slot_times(make_scenario(latest_arrival_min=120)) == (
        100,
        105,
        110,
        115,
        120,
    )
    assert slot_times(make_scenario(latest_arrival_min=122)) == (
        100,
        105,
        110,
        115,
        120,
    )
    assert slot_times(make_scenario(latest_arrival_min=100)) == (100,)
    assert slot_times(make_scenario(latest_arrival_min=99)) == ()


def test_gaps_and_empty_enumeration() -> None:
    assert enumeration_gaps(make_scenario()) == ()
    broken = make_scenario(earliest_arrival_min=None, gates=None)
    assert enumeration_gaps(broken) == ("earliest_arrival_min", "gates")
    assert enumerate_packages(broken) == ()
    assert enumerate_packages(make_scenario(runways=())) == ()


def test_package_bound_is_enforced_exactly() -> None:
    limit = rv.rule_value(rv.MAX_PACKAGES).value
    # One runway and one gate: 1 DIRECT plus 2 per later slot.
    # n slots give 1 + 2 (n - 1) = 2n - 1 packages.
    runways = (Runway(runway_id="R1", closed=False),)
    gates = (Gate(gate_id="G1", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY),)
    step = rv.rule_value(rv.SLOT_STEP_MIN).value

    def with_slots(n: int):  # noqa: ANN202
        return make_scenario(
            runways=runways,
            gates=gates,
            earliest_arrival_min=0,
            latest_arrival_min=step * (n - 1),
        )

    at_limit = (limit + 1) // 2  # 2n - 1 == limit when limit is odd
    n_ok = at_limit if (2 * at_limit - 1) <= limit else at_limit - 1
    assert len(enumerate_packages(with_slots(n_ok))) <= limit
    with pytest.raises(PackageBoundError):
        enumerate_packages(with_slots(n_ok + 1))


def test_bound_raises_instead_of_truncating() -> None:
    many = tuple(
        Gate(gate_id=f"G{i:03}", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY)
        for i in range(rv.rule_value(rv.MAX_PACKAGES).value)
    )
    with pytest.raises(PackageBoundError):
        enumerate_packages(make_scenario(gates=many))
