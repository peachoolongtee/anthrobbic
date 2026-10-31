"""Worked scenarios with expected packages and costs computed by hand.

Nothing here derives an expected value by calling the code under test. Each
case states its arithmetic. The numbers are pinned to the rule values and
weights below; `test_pinned_values` fails first, with a clear message, if a
table update moves them.

Pinned rule values (approach speed 130 kt, so a mile of separation costs
60/130 min and the gap is rounded up):
  3 NM -> ceil(180/130) = 2 min    5 NM -> ceil(300/130) = 3 min
  fuel: 30 min of holding fuel plus 5% of trip fuel (challenge workbook)
  gate buffer 15 min; slot step 5 min; gate change notice 20 min
  airport minimum turnaround 35 min (the baseline small hub); cap 36 arrivals/h
  flight crew maximum duty 13 h = 780 min from report time
  minimum connection 30 min
Pinned weights: 2 per kg of fuel, 100 per passenger at risk, 50 per gate move,
  30 per overtime minute (an ordinary crew minute of 20, times the workbook's
  1.5 after the 8-hour shift), 30 per minute of turnaround delay, 10 per minute
  of arrival delay after the earliest slot (charged to ATC).

Common base (see `worked`): airborne, IFR, own wake LARGE, narrow-body, earliest
arrival 100, latest 110, so slots 100, 105, 110. Taxi-in 10 min, so gate-in is
slot + 10. One open runway R1, gates G1 and G2 on open taxiway T1, planned gate
G1. Fuel on board 10000 kg, trip fuel 4000 kg, cruise burn 50 kg/min, hold burn
40 kg/min, alternate fuel 1000 kg. Forecast is good (ceiling 5000 ft, visibility
10 mi) for the whole period, so no alternate: required landing fuel is
30 x 40 = 1200 of holding fuel plus 5% of 4000 = 200 contingency, 1400 kg.
Next departure 300 (soft), shift end 500, no connections. Decision time 50 and
crew report time 0, so notice and duty bind nothing unless a case says so. The
stay at the gate is 110 to 145 (gate-in plus the 35 min minimum turnaround).

Packages considered with 1 runway and 2 gates: slot 100 has DIRECT only (2
packages); slots 105 and 110 each have HOLD and VECTOR (4 packages each); 10 in
all. Delay costs with the base: HOLD 5 min = 5 x 40 = 200 kg = 400; HOLD 10 min
= 400 kg = 800; VECTOR 5 min = 5 x 50 = 250 kg = 500. A gate other than G1 adds
a gate move of 50. Arrival delay adds 10 a minute: 5 min = 50, 10 min = 100.
A gate is held until the next departure when that is later than gate-in plus
the turnaround (no tow is modelled); the base departs at 300.
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
    NoGo,
    NoGoReason,
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
    assert rv.rule_value(rv.FUEL_RESERVE_MIN).value == 30
    assert rv.rule_value(rv.FUEL_CONTINGENCY_PCT).value == 5
    assert rv.rule_value(rv.GATE_CHANGE_NOTICE_MIN).value == 20
    assert rv.rule_value(rv.CREW_MAX_DUTY_MIN).value == 780
    assert rv.rule_value(rv.GROUND_OVERTIME_PCT).value == 150
    assert rv.rule_value(rv.GATE_BUFFER_MIN).value == 15
    assert rv.rule_value(rv.SLOT_STEP_MIN).value == 5
    assert rv.rule_value(rv.MIN_CONNECTION_MIN).value == 30
    assert rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value == 2000
    assert DEFAULT_WEIGHTS.fuel_per_kg == 2
    assert DEFAULT_WEIGHTS.per_passenger_at_risk == 100
    assert DEFAULT_WEIGHTS.per_gate_move == 50
    assert DEFAULT_WEIGHTS.overtime_per_min == 30
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
        "runways": (Runway(runway_id="R1", closed=False, parallel_group=None),),
        "taxiways": (Taxiway(taxiway_id="T1", closed=False),),
        "gates": (G1, G2),
        "other_arrivals": (),
        "gate_occupancies": (),
        "planned_gate": "G1",
        "next_departure_min": 300,
        "next_leg_turnaround_hard": False,
        "ground_shift_end_min": 500,
        "connections": (),
        "decision_time_min": 50,
        "crew_report_min": 0,
        "airport_ops_per_hour": 36,
        "min_turnaround_min": 35,
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


def many_gates(n: int) -> list[Gate]:
    return [
        Gate(gate_id=f"G{i}", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY)
        for i in range(1, n + 1)
    ]


def crowd(n: int) -> tuple[OtherArrival, ...]:
    """`n` large arrivals on R1, all at minute 50, far enough back to need no
    wake spacing at the slots under test."""
    return tuple(
        OtherArrival(
            flight_id=f"C{i}",
            wake_category=WakeCategory.LARGE,
            runway_id="R1",
            time_min=50,
        )
        for i in range(n)
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
    # HOLD 5 min on G1 = 200 kg x 2 = 400, plus 5 min of delay = 50, so 450;
    # VECTOR = 500 + 50; G2 adds 50; slot 110 HOLD = 800 + 100. Cheapest is
    # HOLD at 105 on G1 = 450. Legal: 10 - 2 = 8.
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
        450,
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
    # 4 >= 3, legal. Cheapest legal: HOLD at 105 on G1 = 400 + 50 = 450. Legal: 8.
    Deal_(
        "one minute inside the wake limit",
        worked(other_arrivals=heavy_at(101)),
        pk("R1", 105, "G1", HOLD),
        450,
        10,
        8,
    ),
    # W5. As W4, with fuel on board 5600. HOLD at 105 burns 200, landing fuel
    # 5600 - 4000 - 200 = 1400 = the 1400 required: exactly at the limit, legal.
    # VECTOR at 105 burns 250, landing 1350 < 1400, illegal. At 110 HOLD burns
    # 400, landing 1200, illegal; VECTOR 500, landing 1100, illegal. Only HOLD at
    # 105 survives (2 gates), so legal = 2; G1 costs 200 x 2 = 400, plus 50 for
    # 5 min of delay = 450.
    Deal_(
        "fuel exactly at the workbook limit",
        worked(other_arrivals=heavy_at(101), fuel_on_board_kg=5_600),
        pk("R1", 105, "G1", HOLD),
        450,
        10,
        2,
    ),
    # W6. G1 is occupied 95-140. Our stay at 100 is 110-300 (held until the next
    # departure): clear gap max(110 - 140, 95 - 300) = -30 < 15, illegal; at 105
    # (115-300) -25; at 110 (120-300) -20. G1 is out everywhere, G2 is free:
    # 1 + 2 + 2 = 5 legal.
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
    # W7. Wide-body. The minimum turnaround is the airport's 35 min whatever the
    # size, so the stay at 100 ends 110 + 35 = 145. G1 is narrow, so illegal; G2 is
    # wide. The shift ends at 135: 10 min of overtime x 30 (20 an ordinary minute
    # x 1.5) = 300; gate move 50; total 350. At 105 overtime is 15 x 30 = 450 + 50
    # + HOLD 400 + 50 of delay = 950. Legal: G2 only, 1 + 2 + 2 = 5.
    Deal_(
        "wide-body overtime",
        worked(
            aircraft_size=AircraftSize.WIDE_BODY,
            gates=(
                G1,
                Gate(gate_id="G2", taxiway_id="T1", max_size=AircraftSize.WIDE_BODY),
            ),
            ground_shift_end_min=135,
        ),
        pk("R1", 100, "G2", DIRECT),
        350,
        10,
        5,
    ),
    # W8. Soft next leg departs at 130. At 100 the aircraft is ready at
    # 110 + 35 = 145, 15 min late = 15 x 30 = 450. At 105 it is 20 min late = 600,
    # plus HOLD 400 and 50 of delay. DIRECT at 100 on G1 = 450.
    Deal_(
        "soft turnaround delay",
        worked(next_departure_min=130),
        pk("R1", 100, "G1", DIRECT),
        450,
        10,
        10,
    ),
    # W9. Hard next leg departs at 145. At 100: 145 - 110 = 35 min available,
    # exactly the 35 min turnaround, legal, no delay cost. At 105: 30 < 35 and at
    # 110: 25 < 35, illegal (8 packages). Legal: 2 (slot 100, two gates).
    Deal_(
        "hard turnaround exactly at the limit",
        worked(next_departure_min=145, next_leg_turnaround_hard=True),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        2,
    ),
    # W10. Before departure, HEAVY at 101 rules out 100. A ground delay burns no
    # airborne fuel, so with 5599 kg aboard (too little for an airborne hold)
    # landing fuel is 5599 - 4000 = 1599 >= 1400. Slot 105 costs 5 min of delay
    # = 50 (no fuel, G1, no overtime, no turnaround delay); slot 110 costs
    # 10 x 10 = 100. So 105 wins with 50. Packages: 2 + 2 + 2 = 6; legal 4.
    Deal_(
        "ground delay before departure",
        worked(
            decision_point=DecisionPoint.PRE_DEPARTURE,
            other_arrivals=heavy_at(101),
            fuel_on_board_kg=5_599,
        ),
        pk("R1", 105, "G1", GROUND),
        50,
        6,
        4,
    ),
    # W11. R1 is closed, R2 open; 2 runways x 10 = 20 packages, the 10 on R1
    # are illegal. DIRECT at 100 on G1 on R2 costs 0; R1 is out so R2 wins.
    Deal_(
        "one runway closed",
        worked(
            runways=(
                Runway(runway_id="R1", closed=True, parallel_group=None),
                Runway(runway_id="R2", closed=False, parallel_group=None),
            )
        ),
        pk("R2", 100, "G1", DIRECT),
        0,
        20,
        10,
    ),
    # W12. Ceiling 1999 ft (< 2000) forces an alternate: required = 1400 + 1000 =
    # 2400. Fuel 6400: DIRECT at 100 lands with 6400 - 4000 = 2400, exactly at the
    # limit, legal on both gates (2). HOLD at 105 lands with 2200, illegal, and
    # every later package is worse. DIRECT at 100 on G1 = 0.
    Deal_(
        "alternate fuel exactly at the limit",
        worked(
            fuel_on_board_kg=6_400,
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
    # W13. R1 and R2 are parallel runways in one group, and a LARGE lands on R2
    # at 100. They count as one runway, so our LARGE needs 2 min behind it on
    # either. At 100 all 4 packages (2 runways x 2 gates, DIRECT) are illegal.
    # At 105 the gap is 5, legal: 2 runways x 2 gates x 2 actions x 2 slots = 16
    # legal of 20. Cheapest: HOLD at 105 on R1 (first by the tie-break), G1 =
    # 400 + 50 = 450.
    Deal_(
        "parallel runways are one runway",
        worked(
            runways=(
                Runway(runway_id="R1", closed=False, parallel_group="P"),
                Runway(runway_id="R2", closed=False, parallel_group="P"),
            ),
            other_arrivals=(
                OtherArrival(
                    flight_id="LRG",
                    wake_category=WakeCategory.LARGE,
                    runway_id="R2",
                    time_min=100,
                ),
            ),
        ),
        pk("R1", 105, "G1", HOLD),
        450,
        20,
        16,
    ),
    # W14. The same traffic with no parallel group: R1 is independent of R2, so
    # DIRECT at 100 on R1 is legal and costs 0. Only the 2 packages at 100 on R2
    # itself (gap 0) are illegal, so 18 of 20 are legal.
    Deal_(
        "independent runways",
        worked(
            runways=(
                Runway(runway_id="R1", closed=False, parallel_group=None),
                Runway(runway_id="R2", closed=False, parallel_group=None),
            ),
            other_arrivals=(
                OtherArrival(
                    flight_id="LRG",
                    wake_category=WakeCategory.LARGE,
                    runway_id="R2",
                    time_min=100,
                ),
            ),
        ),
        pk("R1", 100, "G1", DIRECT),
        0,
        20,
        18,
    ),
    # W15. Another flight holds G1 from 150 to 170, and ours departs at 200. With
    # no tow the aircraft keeps G1 until 200, so every stay on G1 (110 to 200
    # at 100; 115 to 200 at 105; 120 to 200 at 110) overlaps 150 to 170 by far
    # more than the buffer. G1 is out. G2 is free: DIRECT at 100 on G2 costs a
    # gate move, 50. Legal: G2 only, 1 + 2 + 2 = 5 of 10.
    Deal_(
        "gate held until the next departure",
        worked(
            next_departure_min=200,
            gate_occupancies=(
                GateOccupancy(
                    gate_id="G1", flight_id="OTHER", start_min=150, end_min=170
                ),
            ),
        ),
        pk("R1", 100, "G2", DIRECT),
        50,
        10,
        5,
    ),
    # W16. The scenario's own flight appears in the traffic list and in the gate
    # occupancies. Neither counts against it: DIRECT at 100 on G1 costs 0 and
    # all 10 packages are legal.
    Deal_(
        "own flight is not its own traffic",
        worked(
            other_arrivals=(
                OtherArrival(
                    flight_id="AB123",
                    wake_category=WakeCategory.LARGE,
                    runway_id="R1",
                    time_min=100,
                ),
            ),
            gate_occupancies=(
                GateOccupancy(
                    gate_id="G1", flight_id="AB123", start_min=110, end_min=135
                ),
            ),
        ),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        10,
    ),
    # W17. Pre-departure, window 100 to 300 (41 slots). G1 is occupied 90 to 205.
    # Moving to G2 now costs a gate move, 50. Waiting for G1 needs gate-in at
    # 205 + 15 = 220, so slot 210 or later: 110 min of ground delay = 110 x 10 =
    # 1100. 50 < 1100, so DIRECT at 100 on G2 wins. A long wait must not beat a
    # gate move. Packages: 2 gates x (1 + 40) = 82. Legal: all 41 on G2, plus G1
    # at slots 210 to 300 (19 slots; 210 is exactly 15 clear) = 60.
    Deal_(
        "a long ground delay does not beat a gate move",
        worked(
            decision_point=DecisionPoint.PRE_DEPARTURE,
            latest_arrival_min=300,
            gate_occupancies=(
                GateOccupancy(gate_id="G1", flight_id="OLD", start_min=90, end_min=205),
            ),
        ),
        pk("R1", 100, "G2", DIRECT),
        50,
        82,
        60,
    ),
    # W18. Exactly 2000 packages (one runway, 400 gates x 5) is allowed. All are
    # legal on identical terms, so the cost is 0 and the tie-break picks the
    # smallest gate ID as text, "G1", at 100.
    Deal_(
        "exactly at the package bound",
        worked(gates=tuple(many_gates(400))),
        pk("R1", 100, "G1", DIRECT),
        0,
        2000,
        2000,
    ),
    # W19. G1 is occupied 95-140 (so G1 is out, as in W6) and the gate change is
    # only decided at 90. The notice before arrival is slot - 90: 10 at 100, 15 at
    # 105, 20 at 110. A change needs 20, so G2 at 100 and 105 are illegal and G2 at
    # 110 is exactly at the limit. Only the two G2 packages at 110 are legal: HOLD
    # 10 min = 400 kg x 2 = 800, plus 10 min of delay = 100, plus the gate move 50
    # = 950; VECTOR is 500 kg x 2 = 1000 + 100 + 50 = 1150. HOLD wins at 950.
    Deal_(
        "gate change decided exactly 20 minutes before arrival",
        worked(
            decision_time_min=90,
            gate_occupancies=(
                GateOccupancy(gate_id="G1", flight_id="OLD", start_min=95, end_min=140),
            ),
        ),
        pk("R1", 110, "G2", HOLD),
        950,
        10,
        2,
    ),
    # W20. The crew reported at -670, so gate-in at 110 is 780 min on duty: exactly
    # the 13 hours. At 105 it is 785 and at 110 it is 790, past the limit. Only
    # DIRECT at 100 on either gate is legal; G1 costs 0.
    Deal_(
        "crew exactly at the maximum duty",
        worked(crew_report_min=-670),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        2,
    ),
    # W21. 35 other arrivals at minute 50 plus ours make 36 in the hour, exactly the
    # small hub's cap, at 100 and 105 (the hour from 46 to 105 holds minute 50). At
    # 110 the hour from 51 no longer holds them. So everything is legal: cost 0.
    Deal_(
        "airport exactly at its hourly cap",
        worked(other_arrivals=crowd(35)),
        pk("R1", 100, "G1", DIRECT),
        0,
        10,
        10,
    ),
    # W22. One more arrival makes 37 in the hour at 100 and 105: those four
    # packages are illegal (the 2 at 100 and the 4 at 105). At 110 the 36 at minute
    # 50 are outside the hour from 51 to 110, so the 4 packages at 110 are legal.
    # Cheapest: HOLD at 110 on G1, 800 + 100 = 900.
    Deal_(
        "airport one over its hourly cap",
        worked(other_arrivals=crowd(36)),
        pk("R1", 110, "G1", HOLD),
        900,
        10,
        4,
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
    # W7: gate move 50 plus overtime 10 min x 30 = 300.
    # W8: only turnaround delay 15 min x 30 = 450.
    w6, w7, w8 = DEALS[5], DEALS[6], DEALS[7]
    c6, c7, c8 = (decide(c.scenario).cost for c in (w6, w7, w8))  # type: ignore[union-attr]
    assert (c6.gate_moves, c6.overtime, c6.turnaround_delay, c6.fuel_burn) == (
        50,
        0,
        0,
        0,
    )
    assert (c7.gate_moves, c7.overtime, c7.turnaround_delay) == (50, 300, 0)
    assert (c8.gate_moves, c8.overtime, c8.turnaround_delay) == (0, 0, 450)
    # By domain: ground carries gate moves, overtime and turnaround delay.
    assert (c7.by_domain.ground, c7.by_domain.pilot, c7.by_domain.atc) == (350, 0, 0)
    w4 = decide(DEALS[3].scenario).cost  # type: ignore[union-attr]
    # W4: fuel 400 to the pilot, arrival delay 5 min x 10 = 50 to ATC.
    assert (w4.fuel_burn, w4.by_domain.pilot, w4.total) == (400, 400, 450)
    assert (w4.arrival_delay, w4.by_domain.atc) == (50, 50)


def test_connections_at_risk_are_charged_to_atc() -> None:
    # Ten passengers connect at 140. Sliding the only legal slot to 105 puts
    # them at risk: gate-in 115 + 30 = 145 > 140, 10 x 100 = 1000.
    scenario = worked(
        other_arrivals=heavy_at(101),
        connections=(Connection(passengers=10, departure_min=140),),
    )
    result = decide(scenario)
    assert isinstance(result, Deal)
    # HOLD at 105 on G1: fuel 400 + connections 1000 + arrival delay 50 = 1450.
    assert result.package == pk("R1", 105, "G1", HOLD)
    assert (result.cost.fuel_burn, result.cost.connections_at_risk) == (400, 1000)
    assert result.cost.by_domain.atc == 1050
    assert result.cost.total == 1450


def no_go(scenario: Any) -> NoGo:
    result = decide(scenario)
    assert isinstance(result, NoGo)
    return result


def test_no_go_when_fuel_is_one_kg_short() -> None:
    # W5 with 5599 kg: HOLD at 105 lands with 1399 < 1400, illegal. All 8
    # packages at 105 and 110 break the fuel policy (VECTOR and the later HOLD
    # are worse still); the 2 DIRECT packages at 100 break wake separation only
    # (gap 1 < 2) because 5599 - 4000 = 1599 >= 1400.
    result = no_go(worked(other_arrivals=heavy_at(101), fuel_on_board_kg=5_599))
    assert result.reason_type is NoGoReason.NOTHING_LEGAL
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


def test_no_go_when_hard_turnaround_and_wake_conflict() -> None:
    # Next leg departs at 145 and is hard; HEAVY at 101 rules out 100 (gap 1 < 2).
    # At 105 available time is 145 - 115 = 30 < 35 and at 110 it is 25 < 35, so
    # all 8 later packages break the turnaround rule.
    result = no_go(
        worked(
            other_arrivals=heavy_at(101),
            next_departure_min=145,
            next_leg_turnaround_hard=True,
        )
    )
    assert result.binding_rule_ids == ("GND-TURNAROUND",)
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("GND-TURNAROUND", 8),
        ("ATC-WAKE-SEP", 2),
    ]
    assert result.reason_type is NoGoReason.NOTHING_LEGAL


def test_no_go_when_the_only_runway_is_closed() -> None:
    result = no_go(
        worked(runways=(Runway(runway_id="R1", closed=True, parallel_group=None),))
    )
    assert result.reason_type is NoGoReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("ATC-RWY-CLOSED",)
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("ATC-RWY-CLOSED", 10)
    ]
    assert result.nearest_package == pk("R1", 100, "G1", DIRECT)
    assert [(v.observed, v.limit) for v in result.nearest_violations] == [(1, 0)]


def test_missing_data_blocking_every_package_is_a_system_fault() -> None:
    result = no_go(worked(fuel_on_board_kg=None))
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)
    assert result.nearest_violations[0].observed is None


def test_unknown_runways_leave_nothing_to_enumerate() -> None:
    result = no_go(worked(runways=None))
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.packages_considered == 0
    assert result.nearest_package is None
    assert "runways" in result.reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"latest_arrival_min": 99},
        {"runways": ()},
        {"gates": ()},
    ],
    ids=["latest before earliest", "no runways", "no gates"],
)
def test_an_empty_or_inconsistent_input_is_a_fault(overrides: dict[str, Any]) -> None:
    result = no_go(worked(**overrides))
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.packages_considered == 0
    assert result.nearest_package is None


def test_a_package_blocked_only_by_missing_data_makes_it_a_fault() -> None:
    # HEAVY at 101 and 6449 kg, as in the one-kg-short case, but the hold rate is
    # unknown. HOLD packages fail only because of the missing hold rate, so
    # supplying it might make one legal: that is a fault, not a verdict. VECTOR
    # packages fail the fuel limit for real and DIRECT at 100 fails wake
    # separation.
    result = no_go(
        worked(
            other_arrivals=heavy_at(101),
            fuel_on_board_kg=5_599,
            hold_burn_kg_per_min=None,
        )
    )
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)


def test_missing_data_alongside_a_real_violation_is_still_nothing_legal() -> None:
    # R1 is closed (a real limit, on all 10 packages) and fuel on board is
    # unknown (missing data, on all 10). No package is blocked only by missing
    # data, because every one also hits the closed runway. Both rules eliminate
    # 10 packages, so both bind, in ID order.
    result = no_go(
        worked(
            runways=(Runway(runway_id="R1", closed=True, parallel_group=None),),
            fuel_on_board_kg=None,
        )
    )
    assert result.reason_type is NoGoReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("ATC-RWY-CLOSED", "PLT-FUEL-POLICY")
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("ATC-RWY-CLOSED", 10),
        ("PLT-FUEL-POLICY", 10),
    ]


def test_eliminations_count_packages_not_violations() -> None:
    # One package (window 100 to 100, one runway, one gate) with two wake
    # conflicts: LARGE at 100 (gap 0) and at 101 (gap 1), both under 2 min.
    # Two violations, but one package eliminated.
    arrivals = tuple(
        OtherArrival(
            flight_id=f"L{t}",
            wake_category=WakeCategory.LARGE,
            runway_id="R1",
            time_min=t,
        )
        for t in (100, 101)
    )
    result = no_go(worked(latest_arrival_min=100, gates=(G1,), other_arrivals=arrivals))
    assert result.packages_considered == 1
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("ATC-WAKE-SEP", 1)
    ]
    assert len(result.nearest_violations) == 2


def test_nearest_package_prefers_fewer_violations_when_rule_counts_tie() -> None:
    # One gate. LARGE at 100 and HEAVY at 101 give DIRECT at 100 two wake
    # violations (gaps 0 and 1 against 2). At 105 and 110 wake is fine (gaps
    # 5 and 4 against 3) but 6449 kg fails fuel once each. One rule each, so
    # fewer violations decides: the first HOLD at 105 (1 violation) beats
    # DIRECT at 100 (2) even though DIRECT sorts first.
    arrivals = (
        *heavy_at(101),
        OtherArrival(
            flight_id="LRG",
            wake_category=WakeCategory.LARGE,
            runway_id="R1",
            time_min=100,
        ),
    )
    result = no_go(worked(gates=(G1,), other_arrivals=arrivals, fuel_on_board_kg=5_599))
    assert result.nearest_package == pk("R1", 105, "G1", HOLD)
    assert [(v.rule_id, v.observed, v.limit) for v in result.nearest_violations] == [
        ("PLT-FUEL-POLICY", 1399, 1400)
    ]


def test_nearest_package_prefers_fewer_rules_over_fewer_violations() -> None:
    # One gate, fuel 6449. Three LARGE arrivals at 99, 100 and 101 give DIRECT
    # at 100 three wake violations and nothing else: 1 rule, 3 violations.
    # LARGE at 106 and 111 give each HOLD and VECTOR at 105 and 110 one wake
    # violation (gap 1) plus a fuel violation: 2 rules, 2 violations. Fewer
    # rules wins, so DIRECT at 100 is nearest despite having the most
    # violations.
    arrivals = tuple(
        OtherArrival(
            flight_id=f"L{t}",
            wake_category=WakeCategory.LARGE,
            runway_id="R1",
            time_min=t,
        )
        for t in (99, 100, 101, 106, 111)
    )
    result = no_go(worked(gates=(G1,), other_arrivals=arrivals, fuel_on_board_kg=5_599))
    assert result.packages_considered == 5
    assert result.nearest_package == pk("R1", 100, "G1", DIRECT)
    # Gaps 1, 0, 1 against the 2 min needed, in arrival order.
    assert [(v.observed, v.limit) for v in result.nearest_violations] == [
        (1, 2),
        (0, 2),
        (1, 2),
    ]
    # Wake eliminates all 5 packages, fuel the 4 delayed ones.
    assert [(e.rule_id, e.packages_eliminated) for e in result.eliminations] == [
        ("ATC-WAKE-SEP", 5),
        ("PLT-FUEL-POLICY", 4),
    ]
    assert result.binding_rule_ids == ("ATC-WAKE-SEP",)


def test_nearest_package_is_not_just_the_first_package() -> None:
    # G1 is occupied 95-140, so every G1 package breaks the overlap rule, and
    # HEAVY at 101 breaks wake separation at 100 on both gates. With 6449 kg
    # every delayed package breaks fuel. G1 packages break two rules. On G2,
    # DIRECT at 100 breaks only wake and the delayed ones only fuel, so G2
    # DIRECT at 100 is the first of the one-rule packages.
    result = no_go(
        worked(
            other_arrivals=heavy_at(101),
            fuel_on_board_kg=5_599,
            gate_occupancies=(
                GateOccupancy(gate_id="G1", flight_id="OLD", start_min=95, end_min=140),
            ),
        )
    )
    assert result.nearest_package == pk("R1", 100, "G2", DIRECT)
    assert [v.rule_id for v in result.nearest_violations] == ["ATC-WAKE-SEP"]


def test_binding_violations_carry_observed_value_and_limit() -> None:
    # One kg short: the first package to break the fuel policy, in package
    # order, is HOLD at 105 on G1, landing with 5599 - 4000 - 200 = 1399 against
    # 1400.
    result = no_go(worked(other_arrivals=heavy_at(101), fuel_on_board_kg=5_599))
    assert [
        (v.rule_id, v.observed, v.limit, v.unit) for v in result.binding_violations
    ] == [("PLT-FUEL-POLICY", 1399, 1400, "kg")]
    # Hard turnaround: HOLD at 105 has 145 - 115 = 30 min against 35.
    turnaround = no_go(
        worked(
            other_arrivals=heavy_at(101),
            next_departure_min=145,
            next_leg_turnaround_hard=True,
        )
    )
    assert [
        (v.rule_id, v.observed, v.limit, v.unit) for v in turnaround.binding_violations
    ] == [("GND-TURNAROUND", 30, 35, "min")]
    closed = no_go(
        worked(runways=(Runway(runway_id="R1", closed=True, parallel_group=None),))
    )
    assert [(v.rule_id, v.observed, v.limit) for v in closed.binding_violations] == [
        ("ATC-RWY-CLOSED", 1, 0)
    ]


def test_binding_violation_falls_back_to_missing_data_when_that_is_all_there_is() -> (
    None
):
    result = no_go(worked(fuel_on_board_kg=None))
    assert [(v.rule_id, v.observed) for v in result.binding_violations] == [
        ("PLT-FUEL-POLICY", None)
    ]


def test_binding_violation_prefers_a_real_limit_over_missing_data() -> None:
    # G1 hangs off a taxiway the scenario does not list, so every G1 package
    # fails the taxiway rule for missing data, and it comes first in package
    # order. G2's taxiway T1 is closed, a real limit with numbers (1 closed
    # against 0 allowed), which the card can show, so it is the one reported.
    result = no_go(
        worked(
            gates=(
                Gate(gate_id="G1", taxiway_id="T9", max_size=AircraftSize.NARROW_BODY),
                G2,
            ),
            taxiways=(Taxiway(taxiway_id="T1", closed=True),),
        )
    )
    assert result.binding_rule_ids == ("ATC-TWY-CLOSED",)
    assert [(v.rule_id, v.observed, v.limit) for v in result.binding_violations] == [
        ("ATC-TWY-CLOSED", 1, 0)
    ]


def test_every_binding_rule_gets_one_violation() -> None:
    result = no_go(
        worked(
            runways=(Runway(runway_id="R1", closed=True, parallel_group=None),),
            fuel_on_board_kg=None,
        )
    )
    # The closed runway has a real limit; the fuel rule only missing data.
    assert [v.rule_id for v in result.binding_violations] == [
        "ATC-RWY-CLOSED",
        "PLT-FUEL-POLICY",
    ]


def test_unknown_decision_point_is_a_fault_named_by_the_fuel_rule() -> None:
    # With no decision point every absorbing action is enumerated: 2 DIRECT at
    # 100, then HOLD, VECTOR and GROUND_DELAY on 2 gates at 105 and 110 = 12;
    # 14 in all. Each fails closed on the decision point.
    result = no_go(worked(decision_point=None))
    assert result.packages_considered == 14
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.binding_rule_ids == ("PLT-FUEL-POLICY",)


def test_one_package_over_the_bound_is_a_fault_not_an_exception() -> None:
    # 401 gates x 5 packages = 2005 > 2000.
    result = no_go(worked(gates=tuple(many_gates(401))))
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.packages_considered == 0
    assert result.nearest_package is None
    assert "too many" in result.reason


def test_crew_past_the_maximum_duty_is_the_binding_rule() -> None:
    # Report at -670 and HEAVY at 101 (which rules out slot 100): every later slot
    # is past 780 min on duty. HOLD at 105 is the first: 115 + 670 = 785 > 780.
    result = no_go(worked(crew_report_min=-670, other_arrivals=heavy_at(101)))
    assert result.reason_type is NoGoReason.NOTHING_LEGAL
    assert result.binding_rule_ids == ("PLT-CREW-DUTY",)
    assert [(v.rule_id, v.observed, v.limit) for v in result.binding_violations] == [
        ("PLT-CREW-DUTY", 785, 780)
    ]


def test_a_missing_airport_is_a_visible_system_fault() -> None:
    # No workbook row: the airport fields are unknown, so nothing is enumerated and
    # nothing is defaulted.
    result = no_go(worked(runways=None, gates=None, airport_ops_per_hour=None))
    assert result.reason_type is NoGoReason.SYSTEM_FAULT
    assert result.packages_considered == 0
