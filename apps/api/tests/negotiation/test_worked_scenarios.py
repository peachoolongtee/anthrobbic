"""Worked scenarios with expected packages and costs computed by hand.

Nothing here derives an expected value by calling the code under test. Each
case states its arithmetic. The numbers are pinned to the rule values and
weights below; `test_pinned_values` fails first, with a clear message, if a
table update moves them.

Pinned rule values (approach speed 130 kt, so a mile of separation costs
60/130 min and the gap is rounded up):
  3 NM -> ceil(180/130) = 2 min    5 NM -> ceil(300/130) = 3 min
  fuel policy reserve 45 min at cruise; gate buffer 15 min; slot step 5 min
  turnaround: narrow-body 25 min, wide-body 60 min
  minimum connection 30 min
Pinned weights: 2 per kg of fuel, 100 per passenger at risk, 50 per gate move,
  20 per overtime minute, 30 per minute of turnaround delay.

Common base (see `worked`): airborne, IFR, own wake LARGE, narrow-body, earliest
arrival 100, latest 110, so slots 100, 105, 110. Taxi-in 10 min, so gate-in is
slot + 10. One open runway R1, gates G1 and G2 on open taxiway T1, planned gate
G1. Fuel on board 10000 kg, trip fuel 4000 kg, cruise burn 50 kg/min, hold burn
40 kg/min, alternate fuel 1000 kg. Forecast is good (ceiling 5000 ft, visibility
10 mi) for the whole period, so no alternate: required landing fuel is
45 x 50 = 2250 kg. Next departure 300 (soft), shift end 500, no connections.

Packages considered with 1 runway and 2 gates: slot 100 has DIRECT only (2
packages); slots 105 and 110 each have HOLD and VECTOR (4 packages each); 10 in
all. Delay costs with the base: HOLD 5 min = 5 x 40 = 200 kg = 400; HOLD 10 min
= 400 kg = 800; VECTOR 5 min = 5 x 50 = 250 kg = 500. A gate other than G1 adds
a gate move of 50.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    AircraftSize,
    Connection,
    Deal,
    DecisionPoint,
    FlightPlanAction,
    Gate,
    GateOccupancy,
    NoDeal,
    NoDealReason,
    OtherArrival,
    Package,
    Runway,
    Taxiway,
    WakeCategory,
    WeatherPeriod,
)
from app.negotiation.fallback import decide
from app.negotiation.utility import DEFAULT_WEIGHTS
from tests.negotiation.factories import make_package, make_scenario

HOLD, VECTOR = FlightPlanAction.HOLD, FlightPlanAction.VECTOR
DIRECT, GROUND = FlightPlanAction.DIRECT, FlightPlanAction.GROUND_DELAY


def test_pinned_values() -> None:
    assert rv.rule_value(rv.APPROACH_GROUND_SPEED_KT).value == 130
    assert rv.rule_value(rv.FUEL_RESERVE_MIN).value == 45
    assert rv.rule_value(rv.GATE_BUFFER_MIN).value == 15
    assert rv.rule_value(rv.SLOT_STEP_MIN).value == 5
    assert rv.rule_value(rv.MIN_CONNECTION_MIN).value == 30
    assert rv.turnaround(AircraftSize.NARROW_BODY).value == 25
    assert rv.turnaround(AircraftSize.WIDE_BODY).value == 60
    assert rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value == 2000
    assert DEFAULT_WEIGHTS.fuel_per_kg == 2
    assert DEFAULT_WEIGHTS.per_passenger_at_risk == 100
    assert DEFAULT_WEIGHTS.per_gate_move == 50
    assert DEFAULT_WEIGHTS.overtime_per_min == 20
    assert DEFAULT_WEIGHTS.turnaround_delay_per_min == 30


GOOD_WEATHER = (
    WeatherPeriod(start_min=0, end_min=1000, ceiling_ft=5000, visibility_tenth_mi=100),
)
G1 = Gate(gate_id="G1", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY)
G2 = Gate(gate_id="G2", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY)


def worked(**overrides: Any):  # noqa: ANN201
    base: dict[str, Any] = {
        "decision_point": DecisionPoint.AIRBORNE,
        "wake_category": WakeCategory.LARGE,
        "aircraft_size": AircraftSize.NARROW_BODY,
        "earliest_arrival_min": 100,
        "latest_arrival_min": 110,
        "taxi_in_min": 10,
        "fuel_on_board_kg": 10_000,
        "trip_fuel_kg": 4_000,
        "cruise_burn_kg_per_min": 50,
        "hold_burn_kg_per_min": 40,
        "alternate_fuel_kg": 1_000,
        "destination_forecast": GOOD_WEATHER,
        "runways": (Runway(runway_id="R1", closed=False),),
        "taxiways": (Taxiway(taxiway_id="T1", closed=False),),
        "gates": (G1, G2),
        "other_arrivals": (),
        "gate_occupancies": (),
        "planned_gate": "G1",
        "next_departure_min": 300,
        "next_leg_turnaround_hard": False,
        "ground_shift_end_min": 500,
        "connections": (),
    }
    return make_scenario(**{**base, **overrides})


def heavy_at(time_min: int) -> tuple[OtherArrival, ...]:
    return (
        OtherArrival(
            flight_id="HVY",
            wake_category=WakeCategory.HEAVY,
            runway_id="R1",
            time_min=time_min,
        ),
    )


def pk(runway: str, time_min: int, gate: str, action: FlightPlanAction) -> Package:
    return make_package(time_min, runway, gate, action)


@dataclass(frozen=True)
class Deal_:
    name: str
    scenario: Any
    package: Package
    cost: int
    considered: int
    legal: int


DEALS = [
    # W1. Nothing in the way: DIRECT at 100 on the planned gate costs 0.
    Deal_("free", worked(), pk("R1", 100, "G1", DIRECT), 0, 10, 10),
    # W2. Another LARGE lands at 100, so our LARGE needs 2 min behind it.
    # 100: gap 0 < 2, illegal (2 packages). 105: gap 5, legal.
    # HOLD 5 min on G1 = 200 kg x 2 = 400; VECTOR = 500; G2 adds 50; slot 110
    # HOLD = 800. Cheapest is HOLD at 105 on G1 = 400. Legal: 10 - 2 = 8.
    Deal_(
        "follows a large",
        worked(
            other_arrivals=(
                OtherArrival(
                    flight_id="LRG",
                    wake_category=WakeCategory.LARGE,
                    runway_id="R1",
                    time_min=100,
                ),
            )
        ),
        pk("R1", 105, "G1", HOLD),
        400,
        10,
        8,
    ),
    # W3. A HEAVY lands at 102. At 100 we lead it: LARGE then HEAVY is the
    # default 3 NM = 2 min, and the gap is 102 - 100 = 2, exactly at the limit.
    # At 105 we follow: HEAVY then LARGE is 5 NM = 3 min, gap 105 - 102 = 3,
    # again exactly at the limit. So all 10 packages are legal and DIRECT at 100
    # on G1 costs 0.
    Deal_(
        "exactly at both wake limits",
        worked(other_arrivals=heavy_at(102)),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        10,
    ),
    # W4. HEAVY at 101. At 100 the gap is 1 < 2, illegal. At 105 the gap is
    # 4 >= 3, legal. Cheapest legal: HOLD at 105 on G1 = 400. Legal: 8.
    Deal_(
        "one minute inside the wake limit",
        worked(other_arrivals=heavy_at(101)),
        pk("R1", 105, "G1", HOLD),
        400,
        10,
        8,
    ),
    # W5. As W4, with fuel on board 6450. HOLD at 105 burns 200, landing fuel
    # 6450 - 4000 - 200 = 2250 = the 2250 required: exactly at the limit, legal.
    # VECTOR at 105 burns 250, landing 2200 < 2250, illegal. At 110 HOLD burns
    # 400, landing 2050, illegal; VECTOR 500, landing 1950, illegal. Only HOLD at
    # 105 survives (2 gates), so legal = 2; G1 costs 200 x 2 = 400.
    Deal_(
        "fuel exactly at the policy limit",
        worked(other_arrivals=heavy_at(101), fuel_on_board_kg=6_450),
        pk("R1", 105, "G1", HOLD),
        400,
        10,
        2,
    ),
    # W6. G1 is occupied 95-140. Our stay at 100 is 110-135: clear gap
    # max(110 - 140, 95 - 135) = -30 < 15, illegal; at 105 (115-140) -25; at 110
    # (120-145) -20. G1 is out everywhere, G2 is free: 1 + 2 + 2 = 5 legal.
    # Ten passengers connect at 140: at 100 gate-in 110 + 30 = 140 is not later
    # than 140, so none at risk; at 105 gate-in 115 + 30 = 145 > 140, 10 x 100 =
    # 1000 at risk. DIRECT at 100 on G2 = gate move 50.
    Deal_(
        "gate blocked, connection decides slot",
        worked(
            gate_occupancies=(
                GateOccupancy(gate_id="G1", flight_id="OLD", start_min=95, end_min=140),
            ),
            connections=(Connection(passengers=10, departure_min=140),),
        ),
        pk("R1", 100, "G2", DIRECT),
        50,
        10,
        5,
    ),
    # W7. Wide-body: stay 60 min. G1 is narrow, so illegal; G2 is wide. At 100
    # gate-in 110, stay ends 170; shift ends 160, overtime 10 x 20 = 200; gate move
    # 50; total 250. At 105 overtime 15 x 20 = 300 + 50 + HOLD 400 = 750.
    # Legal: G2 only, 1 + 2 + 2 = 5.
    Deal_(
        "wide-body overtime",
        worked(
            aircraft_size=AircraftSize.WIDE_BODY,
            gates=(
                G1,
                Gate(gate_id="G2", taxiway_id="T1", max_size=AircraftSize.WIDE_BODY),
            ),
            ground_shift_end_min=160,
        ),
        pk("R1", 100, "G2", DIRECT),
        250,
        10,
        5,
    ),
    # W8. Soft next leg departs at 130. At 100 the aircraft is ready at
    # 110 + 25 = 135, 5 min late = 5 x 30 = 150. At 105 it is 10 min late = 300,
    # plus HOLD 400. DIRECT at 100 on G1 = 150.
    Deal_(
        "soft turnaround delay",
        worked(next_departure_min=130),
        pk("R1", 100, "G1", DIRECT),
        150,
        10,
        10,
    ),
    # W9. Hard next leg departs at 135. At 100: 135 - 110 = 25 min available,
    # exactly the 25 min turnaround, legal, no delay cost. At 105: 20 < 25 and at
    # 110: 15 < 25, illegal (8 packages). Legal: 2 (slot 100, two gates).
    Deal_(
        "hard turnaround exactly at the limit",
        worked(next_departure_min=135, next_leg_turnaround_hard=True),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        2,
    ),
    # W10. Before departure, HEAVY at 101 rules out 100. A ground delay burns no
    # airborne fuel, so with 6449 kg aboard (too little for an airborne hold)
    # landing fuel is 6449 - 4000 = 2449 >= 2250. Slots 105 and 110 each cost 0
    # (no fuel, G1, no overtime, no turnaround delay); the earlier one wins the
    # tie. Packages: 2 + 2 + 2 = 6; legal 4.
    Deal_(
        "ground delay before departure",
        worked(
            decision_point=DecisionPoint.PRE_DEPARTURE,
            other_arrivals=heavy_at(101),
            fuel_on_board_kg=6_449,
        ),
        pk("R1", 105, "G1", GROUND),
        0,
        6,
        4,
    ),
    # W11. R1 is closed, R2 open; 2 runways x 10 = 20 packages, the 10 on R1
    # are illegal. DIRECT at 100 on G1 on R2 costs 0; R1 is out so R2 wins.
    Deal_(
        "one runway closed",
        worked(
            runways=(
                Runway(runway_id="R1", closed=True),
                Runway(runway_id="R2", closed=False),
            )
        ),
        pk("R2", 100, "G1", DIRECT),
        0,
        20,
        10,
    ),
    # W12. Ceiling 1999 ft (< 2000) forces an alternate: required = 2250 + 1000 =
    # 3250. Fuel 7250: DIRECT at 100 lands with 7250 - 4000 = 3250, exactly at the
    # limit, legal on both gates (2). HOLD at 105 lands with 3050, illegal, and
    # every later package is worse. DIRECT at 100 on G1 = 0.
    Deal_(
        "alternate fuel exactly at the limit",
        worked(
            fuel_on_board_kg=7_250,
            destination_forecast=(
                WeatherPeriod(
                    start_min=0, end_min=1000, ceiling_ft=1999, visibility_tenth_mi=100
                ),
            ),
        ),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        2,
    ),
]


@pytest.mark.parametrize("case", DEALS, ids=[c.name for c in DEALS])
def test_worked_deal(case: Deal_) -> None:
    result = decide(case.scenario)
    assert isinstance(result, Deal)
    assert result.package == case.package
    assert result.cost.total == case.cost
    assert result.packages_considered == case.considered
    assert result.packages_legal == case.legal
    assert result.cost.unknown_inputs == ()


def test_worked_cost_components() -> None:
    # W6: only a gate move.
    # W7: gate move 50 plus overtime 200.
    # W8: only turnaround delay 150.
    w6, w7, w8 = DEALS[5], DEALS[6], DEALS[7]
    c6, c7, c8 = (decide(c.scenario).cost for c in (w6, w7, w8))  # type: ignore[union-attr]
    assert (c6.gate_moves, c6.overtime, c6.turnaround_delay, c6.fuel_burn) == (
        50,
        0,
        0,
        0,
    )
    assert (c7.gate_moves, c7.overtime, c7.turnaround_delay) == (50, 200, 0)
    assert (c8.gate_moves, c8.overtime, c8.turnaround_delay) == (0, 0, 150)
    # By domain: ground carries gate moves, overtime and turnaround delay.
    assert (c7.by_domain.ground, c7.by_domain.pilot, c7.by_domain.atc) == (250, 0, 0)
    w4 = decide(DEALS[3].scenario).cost  # type: ignore[union-attr]
    assert (w4.fuel_burn, w4.by_domain.pilot, w4.total) == (400, 400, 400)


def test_connections_at_risk_are_charged_to_atc() -> None:
    # Ten passengers connect at 140. Sliding the only legal slot to 105 puts
    # them at risk: gate-in 115 + 30 = 145 > 140, 10 x 100 = 1000.
    scenario = worked(
        other_arrivals=heavy_at(101),
        connections=(Connection(passengers=10, departure_min=140),),
    )
    result = decide(scenario)
    assert isinstance(result, Deal)
    # HOLD at 105 on G1: fuel 400 + connections 1000 = 1400.
    assert result.package == pk("R1", 105, "G1", HOLD)
    assert (result.cost.fuel_burn, result.cost.connections_at_risk) == (400, 1000)
    assert result.cost.by_domain.atc == 1000
    assert result.cost.total == 1400


def no_deal(scenario: Any) -> NoDeal:
    result = decide(scenario)
    assert isinstance(result, NoDeal)
    return result


def test_no_deal_when_fuel_is_one_kg_short() -> None:
    # W5 with 6449 kg: HOLD at 105 lands with 2249 < 2250, illegal. All 8
    # packages at 105 and 110 break the fuel policy (VECTOR and the later HOLD
    # are worse still); the 2 DIRECT packages at 100 break wake separation only
    # (gap 1 < 2) because 6449 - 4000 = 2449 >= 2250.
    result = no_deal(worked(other_arrivals=heavy_at(101), fuel_on_board_kg=6_449))
    assert result.reason_type is NoDealReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("PLT-FUEL-POLICY", 8),
        ("ATC-WAKE-SEP", 2),
    ]
    assert result.packages_considered == 10
    # Every package breaks exactly one rule, so the earliest by the code
    # tie-break is nearest: DIRECT at 100 on G1, one minute short of separation.
    assert result.nearest_package == pk("R1", 100, "G1", DIRECT)
    assert len(result.nearest_violations) == 1
    near = result.nearest_violations[0]
    assert (near.rule_id, near.observed, near.limit, near.unit) == (
        "ATC-WAKE-SEP",
        1,
        2,
        "min",
    )


def test_no_deal_when_hard_turnaround_and_wake_conflict() -> None:
    # Next leg departs at 135 and is hard; HEAVY at 101 rules out 100 (gap 1 < 2).
    # At 105 available time is 135 - 115 = 20 < 25 and at 110 it is 15 < 25, so
    # all 8 later packages break the turnaround rule.
    result = no_deal(
        worked(
            other_arrivals=heavy_at(101),
            next_departure_min=135,
            next_leg_turnaround_hard=True,
        )
    )
    assert result.binding_rule_ids == ("GND-TURNAROUND",)
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("GND-TURNAROUND", 8),
        ("ATC-WAKE-SEP", 2),
    ]
    assert result.reason_type is NoDealReason.NOTHING_LEGAL


def test_no_deal_when_the_only_runway_is_closed() -> None:
    result = no_deal(worked(runways=(Runway(runway_id="R1", closed=True),)))
    assert result.reason_type is NoDealReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("ATC-RWY-CLOSED",)
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("ATC-RWY-CLOSED", 10)
    ]
    assert result.nearest_package == pk("R1", 100, "G1", DIRECT)
    assert [(v.observed, v.limit) for v in result.nearest_violations] == [(1, 0)]


def test_missing_data_blocking_every_package_is_a_system_fault() -> None:
    result = no_deal(worked(fuel_on_board_kg=None))
    assert result.reason_type is NoDealReason.SYSTEM_FAULT
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)
    assert result.nearest_violations[0].observed is None


def test_unknown_runways_leave_nothing_to_enumerate() -> None:
    result = no_deal(worked(runways=None))
    assert result.reason_type is NoDealReason.SYSTEM_FAULT
    assert result.packages_considered == 0
    assert result.nearest_package is None
    assert "runways" in result.reason


def test_an_empty_window_is_not_a_fault() -> None:
    result = no_deal(worked(latest_arrival_min=99))
    assert result.reason_type is NoDealReason.NOTHING_LEGAL
    assert result.packages_considered == 0


def test_missing_data_on_some_packages_only_is_still_nothing_legal() -> None:
    # HEAVY at 101 and 6449 kg, as in the one-kg-short case, but the hold rate is
    # unknown. HOLD packages now fail for missing data; VECTOR packages fail the
    # fuel limit for real, and DIRECT at 100 fails wake separation with no missing
    # data at all. Missing data does not block every package.
    result = no_deal(
        worked(
            other_arrivals=heavy_at(101),
            fuel_on_board_kg=6_449,
            hold_burn_kg_per_min=None,
        )
    )
    assert result.reason_type is NoDealReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)


def test_unknown_decision_point_is_a_fault_named_by_the_fuel_rule() -> None:
    # With no decision point every absorbing action is enumerated: 2 DIRECT at
    # 100, then HOLD, VECTOR and GROUND_DELAY on 2 gates at 105 and 110 = 12;
    # 14 in all. Each fails closed on the decision point.
    result = no_deal(worked(decision_point=None))
    assert result.packages_considered == 14
    assert result.reason_type is NoDealReason.SYSTEM_FAULT
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)
