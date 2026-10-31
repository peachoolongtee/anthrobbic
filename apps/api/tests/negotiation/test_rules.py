"""Every rule ID needs passing, failing and (for numeric rules) boundary cases.

Cases live in `RULE_CASES`, keyed by rule ID. `test_rule_has_coverage` is
parametrised over the rule registry, so a rule added without cases fails.
"""

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import pytest

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    AircraftSize,
    DecisionPoint,
    FlightPlanAction,
    FlightRules,
    Gate,
    GateOccupancy,
    OtherArrival,
    Package,
    Runway,
    Scenario,
    Taxiway,
    ViolationCause,
    WakeCategory,
    WeatherPeriod,
)
from app.negotiation.rules import ALL_RULES, atc, check_package, ground, pilot, rule_ids
from tests.negotiation.factories import (
    BASELINE,
    BASELINE_PACKAGE,
    EARLIEST,
    GATE_IN,
    TAXI_IN,
    make_package,
    make_scenario,
)


@dataclass(frozen=True)
class Case:
    name: str
    scenario: Scenario
    package: Package
    fails: bool
    boundary: bool = False
    violations: int | None = None  # expected count, when it matters
    expect: tuple[int, int] | None = None  # (observed, limit) of the one violation


def ok(name: str, scenario: Scenario, package: Package, **kw: Any) -> Case:
    return Case(name, scenario, package, fails=False, **kw)


def bad(name: str, scenario: Scenario, package: Package, **kw: Any) -> Case:
    return Case(name, scenario, package, fails=True, **kw)


def sep_min(leader: WakeCategory, follower: WakeCategory) -> int:
    """Independent restatement of nm -> minutes, rounded up."""
    nm = rv.wake_separation(leader, follower).value
    speed = rv.approach_speed(follower).value
    return math.ceil(Fraction(nm * 60, speed))


def arrival(
    wake: WakeCategory, time_min: int, runway_id: str = "28L", name: str = "XY9"
) -> OtherArrival:
    return OtherArrival(
        flight_id=name, wake_category=wake, runway_id=runway_id, time_min=time_min
    )


def with_arrivals(*arrivals: OtherArrival, **overrides: Any) -> Scenario:
    return make_scenario(other_arrivals=tuple(arrivals), **overrides)


def wake_cases() -> list[Case]:
    cases: list[Case] = []
    L, H, S = WakeCategory.LARGE, WakeCategory.HEAVY, WakeCategory.SMALL
    # (leader, follower) pairs, own aircraft following then leading.
    for leader, follower in [
        (L, L),
        (H, H),
        (H, L),
        (H, S),
        (L, S),
        (WakeCategory.SUPER, WakeCategory.SUPER),
        (WakeCategory.SUPER, H),
        (WakeCategory.SUPER, L),
        (WakeCategory.SUPER, S),
        (S, H),  # unlisted: default
    ]:
        need = sep_min(leader, follower)
        tag = f"{leader.value}>{follower.value}"
        # Own flight follows the other.
        sc = with_arrivals(arrival(leader, 90), wake_category=follower)
        cases.append(
            ok(f"follow {tag} at limit", sc, make_package(90 + need), boundary=True)
        )
        cases.append(
            bad(
                f"follow {tag} one under",
                sc,
                make_package(90 + need - 1),
                boundary=True,
                violations=1,
                expect=(need - 1, need),
            )
        )
        # Own flight leads the other.
        sc = with_arrivals(arrival(follower, 200), wake_category=leader)
        cases.append(
            ok(f"lead {tag} at limit", sc, make_package(200 - need), boundary=True)
        )
        cases.append(
            bad(
                f"lead {tag} one under",
                sc,
                make_package(200 - need + 1),
                boundary=True,
                violations=1,
                expect=(need - 1, need),
            )
        )
    cases += [
        bad("same minute", with_arrivals(arrival(L, 100)), make_package(100)),
        ok(
            "other runway is ignored",
            with_arrivals(arrival(L, 100, runway_id="28R")),
            make_package(100),
        ),
        ok("no other arrivals", with_arrivals(), make_package(100)),
        bad(
            "every conflict is reported",
            with_arrivals(
                arrival(L, 100, name="A"),
                arrival(L, 101, name="B"),
                arrival(L, 300, name="C"),
            ),
            make_package(100),
            violations=2,
        ),
        bad("own wake unknown", make_scenario(wake_category=None), make_package(100)),
        bad(
            "other arrivals unknown",
            make_scenario(other_arrivals=None),
            make_package(100),
        ),
    ]
    return cases


def runway_closed_cases() -> list[Case]:
    open_28l = Runway(runway_id="28L", closed=False)
    return [
        ok("open runway", make_scenario(), make_package(runway_id="28L")),
        bad(
            "closed runway",
            make_scenario(
                runways=(
                    Runway(runway_id="28L", closed=True),
                    open_28l.model_copy(update={"runway_id": "28R"}),
                )
            ),
            make_package(runway_id="28L"),
        ),
        ok(
            "other runway closed",
            make_scenario(runways=(open_28l, Runway(runway_id="28R", closed=True))),
            make_package(runway_id="28L"),
        ),
        bad("runway not in scenario", make_scenario(), make_package(runway_id="09")),
        bad("runway status unknown", make_scenario(runways=None), make_package()),
    ]


def taxiway_closed_cases() -> list[Case]:
    t1_closed = (
        Taxiway(taxiway_id="T1", closed=True),
        Taxiway(taxiway_id="T2", closed=False),
    )
    return [
        ok("open taxiway", make_scenario(), make_package(gate_id="A1")),
        bad(
            "closed taxiway",
            make_scenario(taxiways=t1_closed),
            make_package(gate_id="A1"),
        ),
        ok(
            "gate on the other taxiway",
            make_scenario(taxiways=t1_closed),
            make_package(gate_id="B1"),
        ),
        bad("gate not in scenario", make_scenario(), make_package(gate_id="Z9")),
        bad(
            "gate taxiway not in scenario",
            make_scenario(taxiways=(Taxiway(taxiway_id="T2", closed=False),)),
            make_package(gate_id="A1"),
        ),
        bad("taxiways unknown", make_scenario(taxiways=None), make_package()),
        bad("gates unknown", make_scenario(gates=None), make_package()),
    ]


def throughput_cases() -> list[Case]:
    cap = rv.runway_hourly_arrivals(FlightRules.IFR).value
    hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    mine = 500

    def others(n: int, at: int, runway_id: str = "28L") -> tuple[OtherArrival, ...]:
        return tuple(
            arrival(WakeCategory.LARGE, at, runway_id, f"F{i}") for i in range(n)
        )

    return [
        ok(
            "cap including this arrival",
            make_scenario(other_arrivals=others(cap - 1, mine - 1)),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "one over the cap",
            make_scenario(other_arrivals=others(cap, mine - 1)),
            make_package(mine),
            boundary=True,
            violations=1,
            expect=(cap + 1, cap),
        ),
        ok(
            "cap arrivals exactly an hour earlier are outside the window",
            make_scenario(other_arrivals=others(cap, mine - hour)),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "cap arrivals just inside the hour",
            make_scenario(other_arrivals=others(cap, mine - hour + 1)),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "cap arrivals just after, inside the hour",
            make_scenario(other_arrivals=others(cap, mine + hour - 1)),
            make_package(mine),
            boundary=True,
        ),
        ok(
            "other runway traffic does not count",
            make_scenario(other_arrivals=others(cap + 5, mine - 1, "28R")),
            make_package(mine),
        ),
        bad(
            "other arrivals unknown",
            make_scenario(other_arrivals=None),
            make_package(mine),
        ),
    ]


def fuel_cases() -> list[Case]:
    trip = BASELINE["trip_fuel_kg"]
    cruise = BASELINE["cruise_burn_kg_per_min"]
    hold = BASELINE["hold_burn_kg_per_min"]
    alternate = BASELINE["alternate_fuel_kg"]
    reserve = rv.rule_value(rv.FUEL_RESERVE_MIN).value * cruise + alternate
    delay = 20
    late = EARLIEST + delay
    hold_pkg = make_package(late, action=FlightPlanAction.HOLD)
    vector_pkg = make_package(late, action=FlightPlanAction.VECTOR)
    return [
        ok(
            "direct, landing fuel exactly at reserve",
            make_scenario(fuel_on_board_kg=trip + reserve),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "direct, one kg under reserve",
            make_scenario(fuel_on_board_kg=trip + reserve - 1),
            BASELINE_PACKAGE,
            boundary=True,
            violations=1,
            expect=(reserve - 1, reserve),
        ),
        ok(
            "hold, exactly at reserve",
            make_scenario(fuel_on_board_kg=trip + delay * hold + reserve),
            hold_pkg,
            boundary=True,
        ),
        bad(
            "hold, one kg under reserve",
            make_scenario(fuel_on_board_kg=trip + delay * hold + reserve - 1),
            hold_pkg,
            boundary=True,
        ),
        ok(
            "vector burns at the cruise rate, exactly at reserve",
            make_scenario(fuel_on_board_kg=trip + delay * cruise + reserve),
            vector_pkg,
            boundary=True,
        ),
        bad(
            "vector, one kg under reserve",
            make_scenario(fuel_on_board_kg=trip + delay * cruise + reserve - 1),
            vector_pkg,
            boundary=True,
        ),
        bad(
            "alternate fuel counts toward the requirement",
            make_scenario(
                fuel_on_board_kg=trip + reserve - 1, alternate_fuel_kg=alternate
            ),
            BASELINE_PACKAGE,
        ),
        ok(
            "no alternate required lowers the requirement",
            make_scenario(
                fuel_on_board_kg=trip + reserve - alternate, alternate_fuel_kg=0
            ),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "slot before the earliest arrival",
            make_scenario(),
            make_package(EARLIEST - 1),
        ),
        bad("direct cannot absorb a delay", make_scenario(), make_package(late)),
        bad(
            "fuel on board unknown",
            make_scenario(fuel_on_board_kg=None),
            BASELINE_PACKAGE,
        ),
        bad("trip fuel unknown", make_scenario(trip_fuel_kg=None), BASELINE_PACKAGE),
        bad(
            "cruise burn unknown",
            make_scenario(cruise_burn_kg_per_min=None),
            BASELINE_PACKAGE,
        ),
        bad(
            "alternate unknown", make_scenario(alternate_fuel_kg=None), BASELINE_PACKAGE
        ),
        bad(
            "earliest arrival unknown",
            make_scenario(earliest_arrival_min=None),
            BASELINE_PACKAGE,
        ),
        bad(
            "hold rate unknown for a hold",
            make_scenario(hold_burn_kg_per_min=None),
            hold_pkg,
        ),
        ok(
            "hold rate unknown is irrelevant to vector",
            make_scenario(hold_burn_kg_per_min=None),
            vector_pkg,
        ),
        *weather_cases(trip, cruise, alternate),
        *decision_point_cases(trip, reserve, delay),
    ]


def forecast(
    start: int, end: int, ceiling: int = 5_000, vis: int = 100
) -> WeatherPeriod:
    return WeatherPeriod(
        start_min=start, end_min=end, ceiling_ft=ceiling, visibility_tenth_mi=vis
    )


def weather_cases(trip: int, cruise: int, alternate: int) -> list[Case]:
    """14 CFR 121.619(a): alternate fuel counts unless weather is good for the
    hour either side of the ETA. ETA is the baseline 100."""
    margin = rv.rule_value(rv.ALTERNATE_WINDOW_MIN).value
    ceiling = rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value
    vis = rv.rule_value(rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI).value
    base = trip + rv.rule_value(rv.FUEL_RESERVE_MIN).value * cruise
    start, end = EARLIEST - margin, EARLIEST + margin

    def sc(fuel: int, *periods: WeatherPeriod) -> Scenario:
        return make_scenario(fuel_on_board_kg=fuel, destination_forecast=periods)

    no_alt = base  # fuel with no alternate required
    with_alt = base + alternate
    return [
        ok(
            "weather exactly at both minimums needs no alternate",
            sc(no_alt, forecast(start, end, ceiling, vis)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "ceiling one foot under the minimum needs an alternate",
            sc(no_alt, forecast(start, end, ceiling - 1, vis)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "visibility one tenth under the minimum needs an alternate",
            sc(no_alt, forecast(start, end, ceiling, vis - 1)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "alternate required and its fuel is aboard",
            sc(with_alt, forecast(start, end, ceiling - 1)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "alternate required, one kg short",
            sc(with_alt - 1, forecast(start, end, ceiling - 1)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "forecast covers exactly the window",
            sc(no_alt, forecast(start, end)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "forecast ends a minute before the window",
            sc(no_alt, forecast(start, end - 1)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "forecast starts a minute after the window",
            sc(no_alt, forecast(start + 1, end)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "adjacent good periods cover the window",
            sc(no_alt, forecast(start, EARLIEST), forecast(EARLIEST, end)),
            BASELINE_PACKAGE,
        ),
        bad(
            "gap between periods",
            sc(no_alt, forecast(start, EARLIEST - 1), forecast(EARLIEST + 1, end)),
            BASELINE_PACKAGE,
        ),
        bad(
            "poor weather late in the window",
            sc(no_alt, forecast(start, EARLIEST), forecast(EARLIEST, end, ceiling - 1)),
            BASELINE_PACKAGE,
        ),
        ok(
            "poor weather only after the window",
            sc(no_alt, forecast(start, end), forecast(end + 1, end + 60, ceiling - 1)),
            BASELINE_PACKAGE,
        ),
        bad(
            "no forecast means an alternate is required",
            make_scenario(fuel_on_board_kg=no_alt, destination_forecast=None),
            BASELINE_PACKAGE,
        ),
        bad(
            "empty forecast means an alternate is required",
            sc(no_alt),
            BASELINE_PACKAGE,
        ),
        ok(
            "missing forecast with alternate fuel aboard",
            make_scenario(fuel_on_board_kg=with_alt, destination_forecast=None),
            BASELINE_PACKAGE,
        ),
        ok(
            "alternate fuel unknown is irrelevant in good weather",
            make_scenario(
                fuel_on_board_kg=no_alt,
                alternate_fuel_kg=None,
                destination_forecast=(forecast(start, end),),
            ),
            BASELINE_PACKAGE,
        ),
        bad(
            "alternate fuel unknown when an alternate is required",
            make_scenario(alternate_fuel_kg=None),
            BASELINE_PACKAGE,
        ),
        ok(
            "good weather over a later ETA window",
            sc(
                no_alt + 20 * BASELINE["hold_burn_kg_per_min"],
                forecast(start + 20, end + 20),
            ),
            make_package(EARLIEST + 20, action=FlightPlanAction.HOLD),
        ),
    ]


def decision_point_cases(trip: int, reserve: int, delay: int) -> list[Case]:
    late = EARLIEST + delay
    pre = DecisionPoint.PRE_DEPARTURE
    return [
        ok(
            "pre-departure, direct at zero delay",
            make_scenario(decision_point=pre),
            BASELINE_PACKAGE,
        ),
        ok(
            "pre-departure ground delay burns no fuel, exactly at reserve",
            make_scenario(decision_point=pre, fuel_on_board_kg=trip + reserve),
            make_package(late, action=FlightPlanAction.GROUND_DELAY),
            boundary=True,
        ),
        bad(
            "pre-departure ground delay, one kg under reserve",
            make_scenario(decision_point=pre, fuel_on_board_kg=trip + reserve - 1),
            make_package(late, action=FlightPlanAction.GROUND_DELAY),
            boundary=True,
        ),
        bad(
            "cannot hold before departure",
            make_scenario(decision_point=pre),
            make_package(late, action=FlightPlanAction.HOLD),
            violations=1,
        ),
        bad(
            "cannot vector before departure",
            make_scenario(decision_point=pre),
            make_package(late, action=FlightPlanAction.VECTOR),
            violations=1,
        ),
        bad(
            "cannot ground-delay once airborne",
            make_scenario(),
            make_package(late, action=FlightPlanAction.GROUND_DELAY),
            violations=1,
        ),
        bad(
            "decision point unknown",
            make_scenario(decision_point=None),
            BASELINE_PACKAGE,
        ),
    ]


def occupancy(start: int, end: int, gate_id: str = "A1") -> GateOccupancy:
    return GateOccupancy(gate_id=gate_id, flight_id="OTH", start_min=start, end_min=end)


def overlap_cases() -> list[Case]:
    buf = rv.rule_value(rv.GATE_BUFFER_MIN).value
    stay = rv.turnaround(AircraftSize.NARROW_BODY).value
    start, end = GATE_IN, GATE_IN + stay

    def sc(*occ: GateOccupancy) -> Scenario:
        # Next departure at the end of the minimum turnaround, so the stay is
        # exactly the turnaround; the departure cases are in extra_overlap_cases.
        return make_scenario(gate_occupancies=occ, next_departure_min=end)

    return [
        ok(
            "previous flight leaves exactly buffer before",
            sc(occupancy(0, start - buf)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "previous flight leaves one minute inside buffer",
            sc(occupancy(0, start - buf + 1)),
            BASELINE_PACKAGE,
            boundary=True,
            violations=1,
            expect=(buf - 1, buf),
        ),
        ok(
            "next flight arrives exactly buffer after",
            sc(occupancy(end + buf, end + buf + 30)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "next flight arrives one minute inside buffer",
            sc(occupancy(end + buf - 1, end + buf + 30)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad("fully overlapping", sc(occupancy(start - 5, end + 5)), BASELINE_PACKAGE),
        ok("other gate is ignored", sc(occupancy(start, end, "B1")), BASELINE_PACKAGE),
        ok("no occupancies", sc(), BASELINE_PACKAGE),
        bad(
            "every conflict is reported",
            sc(occupancy(start - 20, start + 1), occupancy(end - 1, end + 20)),
            BASELINE_PACKAGE,
            violations=2,
        ),
        bad(
            "occupancies unknown",
            make_scenario(gate_occupancies=None),
            BASELINE_PACKAGE,
        ),
        bad("taxi-in unknown", make_scenario(taxi_in_min=None), BASELINE_PACKAGE),
        bad(
            "aircraft size unknown", make_scenario(aircraft_size=None), BASELINE_PACKAGE
        ),
    ]


def size_cases() -> list[Case]:
    return [
        ok(
            "aircraft equals gate maximum",
            make_scenario(),
            make_package(gate_id="A1"),
            boundary=True,
        ),
        bad(
            "aircraft one class above gate maximum",
            make_scenario(),
            make_package(gate_id="A2"),
            boundary=True,
            violations=1,
            expect=(2, 1),
        ),
        ok("aircraft below gate maximum", make_scenario(), make_package(gate_id="B1")),
        bad("gate not in scenario", make_scenario(), make_package(gate_id="Z9")),
        bad(
            "aircraft size unknown", make_scenario(aircraft_size=None), BASELINE_PACKAGE
        ),
        bad("gates unknown", make_scenario(gates=None), BASELINE_PACKAGE),
    ]


def turnaround_cases() -> list[Case]:
    stay = rv.turnaround(AircraftSize.NARROW_BODY).value
    exact = GATE_IN + stay
    return [
        ok(
            "exactly the minimum turnaround",
            make_scenario(next_departure_min=exact),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "one minute short",
            make_scenario(next_departure_min=exact - 1),
            BASELINE_PACKAGE,
            boundary=True,
            violations=1,
            expect=(stay - 1, stay),
        ),
        ok(
            "short but not a hard constraint",
            make_scenario(next_departure_min=exact - 1, next_leg_turnaround_hard=False),
            BASELINE_PACKAGE,
        ),
        bad(
            "unknown hardness is treated as hard",
            make_scenario(next_departure_min=exact - 1, next_leg_turnaround_hard=None),
            BASELINE_PACKAGE,
        ),
        ok(
            "later arrival with later departure",
            make_scenario(next_departure_min=exact + 20),
            make_package(EARLIEST + 20, action=FlightPlanAction.HOLD),
        ),
        bad(
            "later arrival eats the turnaround",
            make_scenario(next_departure_min=exact),
            make_package(EARLIEST + 1, action=FlightPlanAction.HOLD),
        ),
        bad(
            "next departure unknown",
            make_scenario(next_departure_min=None),
            BASELINE_PACKAGE,
        ),
        bad("taxi-in unknown", make_scenario(taxi_in_min=None), BASELINE_PACKAGE),
        bad(
            "aircraft size unknown", make_scenario(aircraft_size=None), BASELINE_PACKAGE
        ),
    ]


GOOD_FORECAST = (
    WeatherPeriod(start_min=0, end_min=1000, ceiling_ft=5000, visibility_tenth_mi=100),
)
PARALLEL = (
    Runway(runway_id="28L", closed=False, parallel_group="P"),
    Runway(runway_id="28R", closed=False, parallel_group="P"),
)
APART = (
    Runway(runway_id="28L", closed=False, parallel_group="P"),
    Runway(runway_id="28R", closed=False, parallel_group="Q"),
)
LARGE = WakeCategory.LARGE
HEAVY = WakeCategory.HEAVY
SMALL = WakeCategory.SMALL
OWN = BASELINE["flight_id"]


def extra_wake_cases() -> list[Case]:
    need_large = sep_min(LARGE, LARGE)
    return [
        # D1: runways in one parallel group count as one runway.
        bad(
            "parallel runways are one runway",
            with_arrivals(arrival(LARGE, 100, "28R"), runways=PARALLEL),
            make_package(100, runway_id="28L"),
            violations=1,
            expect=(0, need_large),
        ),
        ok(
            "parallel runways at the limit",
            with_arrivals(arrival(LARGE, 100, "28R"), runways=PARALLEL),
            make_package(100 + need_large, runway_id="28L"),
            boundary=True,
        ),
        ok(
            "runways in different groups are independent",
            with_arrivals(arrival(LARGE, 100, "28R"), runways=APART),
            make_package(100, runway_id="28L"),
        ),
        ok(
            "runways with no group are independent",
            with_arrivals(arrival(LARGE, 100, "28R")),
            make_package(100, runway_id="28L"),
        ),
        # D4: an arrival on a runway the scenario does not list is not dropped.
        bad(
            "arrival names an unknown runway",
            with_arrivals(arrival(LARGE, 100, "99")),
            make_package(100),
            violations=1,
        ),
        bad("runway list unknown", make_scenario(runways=None), make_package(100)),
        # D5: the scenario's own flight is not its own traffic.
        ok(
            "own flight in the traffic list is skipped",
            with_arrivals(arrival(LARGE, 100, name=OWN)),
            make_package(100),
        ),
        bad(
            "another flight at the same time is not skipped",
            with_arrivals(arrival(LARGE, 100, name="OTHER")),
            make_package(100),
        ),
        # D9: a small follower is slower on final, so a mile takes longer.
        # Heavy then small is 6 NM; at 100 kt that is 3.6 min, so 4.
        ok(
            "small behind heavy needs 4 min",
            with_arrivals(arrival(HEAVY, 100), wake_category=SMALL),
            make_package(104),
            boundary=True,
        ),
        bad(
            "small behind heavy at 3 min",
            with_arrivals(arrival(HEAVY, 100), wake_category=SMALL),
            make_package(103),
            boundary=True,
            violations=1,
            expect=(3, 4),
        ),
        # At the same minute the other flight counts as the leader, so the limit
        # is for its class ahead of ours: heavy then small is 6 NM at 100 kt = 4.
        bad(
            "same minute, other heavy ahead of own small",
            with_arrivals(arrival(HEAVY, 100), wake_category=SMALL),
            make_package(100),
            violations=1,
            expect=(0, 4),
        ),
        # Small then heavy is the default 3 NM at 130 kt = 2.
        bad(
            "same minute, other small ahead of own heavy",
            with_arrivals(arrival(SMALL, 100), wake_category=HEAVY),
            make_package(100),
            violations=1,
            expect=(0, 2),
        ),
        # Heavy then large is 5 NM; at 130 kt that is 2.3 min, so 3.
        bad(
            "large behind heavy at 2 min",
            with_arrivals(arrival(HEAVY, 100)),
            make_package(102),
            violations=1,
            expect=(2, 3),
        ),
    ]


def extra_runway_cases() -> list[Case]:
    return [
        bad(
            "duplicate runway, first open then closed",
            make_scenario(
                runways=(
                    Runway(runway_id="28L", closed=False),
                    Runway(runway_id="28L", closed=True),
                )
            ),
            make_package(runway_id="28L"),
        ),
        bad(
            "duplicate runway, first closed then open",
            make_scenario(
                runways=(
                    Runway(runway_id="28L", closed=True),
                    Runway(runway_id="28L", closed=False),
                )
            ),
            make_package(runway_id="28L"),
        ),
    ]


def extra_taxiway_cases() -> list[Case]:
    return [
        bad(
            "duplicate taxiway, first open then closed",
            make_scenario(
                taxiways=(
                    Taxiway(taxiway_id="T1", closed=False),
                    Taxiway(taxiway_id="T1", closed=True),
                )
            ),
            make_package(gate_id="A1"),
        ),
        bad(
            "duplicate taxiway, first closed then open",
            make_scenario(
                taxiways=(
                    Taxiway(taxiway_id="T1", closed=True),
                    Taxiway(taxiway_id="T1", closed=False),
                )
            ),
            make_package(gate_id="A1"),
        ),
        # D14: a gate listed twice is ambiguous, whichever entry is first.
        bad(
            "gate listed twice, small then large",
            make_scenario(gates=DUP_GATES),
            make_package(gate_id="A1"),
        ),
        bad(
            "gate listed twice, large then small",
            make_scenario(gates=DUP_GATES[::-1]),
            make_package(gate_id="A1"),
        ),
    ]


def extra_size_cases() -> list[Case]:
    return [
        bad(
            "gate listed twice, small then large",
            make_scenario(gates=DUP_GATES),
            make_package(gate_id="A1"),
        ),
        bad(
            "gate listed twice, large then small",
            make_scenario(gates=DUP_GATES[::-1]),
            make_package(gate_id="A1"),
        ),
    ]


DUP_GATES = (
    Gate(gate_id="A1", taxiway_id="T1", max_size=AircraftSize.REGIONAL),
    Gate(gate_id="A1", taxiway_id="T2", max_size=AircraftSize.WIDE_BODY),
)


def extra_throughput_cases() -> list[Case]:
    cap = rv.runway_hourly_arrivals(FlightRules.IFR).value
    vfr_cap = rv.runway_hourly_arrivals(FlightRules.VFR).value
    hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    mine = 500

    def others(
        n: int, at: int, runway_id: str = "28L", prefix: str = "F"
    ) -> tuple[OtherArrival, ...]:
        return tuple(arrival(LARGE, at, runway_id, f"{prefix}{i}") for i in range(n))

    def good(*arrivals: OtherArrival, **kw: Any) -> Scenario:
        kw.setdefault("destination_forecast", GOOD_FORECAST)
        return make_scenario(other_arrivals=arrivals, **kw)

    def poor(*arrivals: OtherArrival, **kw: Any) -> Scenario:
        return make_scenario(other_arrivals=arrivals, **kw)

    return [
        # D10: the cap follows the airport's conditions at the ETA.
        ok(
            "flight rules are not used",
            make_scenario(flight_rules=None),
            make_package(mine),
        ),
        ok(
            "good weather at the ETA allows the VFR cap",
            good(*others(vfr_cap - 1, mine - 1)),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "good weather, one over the VFR cap",
            good(*others(vfr_cap, mine - 1)),
            make_package(mine),
            boundary=True,
            violations=1,
            expect=(vfr_cap + 1, vfr_cap),
        ),
        bad(
            "poor weather at the ETA uses the IFR cap even if the flight is VFR",
            poor(*others(cap, mine - 1), flight_rules=FlightRules.VFR),
            make_package(mine),
            expect=(cap + 1, cap),
        ),
        ok(
            "poor weather, exactly the IFR cap",
            poor(*others(cap - 1, mine - 1), flight_rules=FlightRules.VFR),
            make_package(mine),
        ),
        bad(
            "unknown forecast uses the IFR cap",
            make_scenario(
                destination_forecast=None, other_arrivals=others(cap, mine - 1)
            ),
            make_package(mine),
        ),
        bad(
            "forecast that does not cover the ETA uses the IFR cap",
            good(*others(cap, mine - 1), destination_forecast=(forecast(0, mine - 1),)),
            make_package(mine),
        ),
        ok(
            "forecast period ending exactly at the ETA covers it",
            good(
                *others(cap, mine - 1),
                destination_forecast=(forecast(0, mine),),
            ),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "forecast period ending a minute before the ETA does not cover it",
            good(
                *others(cap, mine - 1),
                destination_forecast=(forecast(0, mine - 1),),
            ),
            make_package(mine),
            boundary=True,
        ),
        ok(
            "forecast period starting exactly at the ETA covers it",
            good(
                *others(cap, mine - 1),
                destination_forecast=(forecast(mine, mine + 10),),
            ),
            make_package(mine),
        ),
        bad(
            "a poor period covering the ETA outranks a good one",
            good(
                *others(cap, mine - 1),
                destination_forecast=(
                    forecast(0, 1000),
                    forecast(mine, mine, 500),
                ),
            ),
            make_package(mine),
        ),
        ok(
            "a poor period elsewhere does not matter",
            good(
                *others(cap, mine - 1),
                destination_forecast=(
                    forecast(0, 1000),
                    forecast(0, mine - 1, 500),
                ),
            ),
            make_package(mine),
        ),
        # Window edges. The cap applies to any hour that contains this arrival.
        ok(
            "cap arrivals exactly an hour later are outside the window",
            poor(*others(cap, mine + hour)),
            make_package(mine),
            boundary=True,
        ),
        ok(
            "a busy hour that does not contain this arrival is not counted",
            poor(*others(cap + 10, mine - 2 * hour)),
            make_package(mine),
        ),
        bad(
            "an hour that spans before and after this arrival is counted",
            poor(*others(15, mine - 40), *others(15, mine + 19, prefix="G")),
            make_package(mine),
            boundary=True,
            violations=1,
            expect=(cap + 1, cap),
        ),
        ok(
            "the same spread an hour wide is not one hour",
            poor(*others(15, mine - 40), *others(15, mine + 20, prefix="G")),
            make_package(mine),
            boundary=True,
        ),
        # D1: parallels share one cap.
        bad(
            "parallel runways share the cap",
            poor(
                *others(15, mine - 1, "28L"),
                *others(15, mine - 1, "28R", "G"),
                runways=PARALLEL,
            ),
            make_package(mine),
            expect=(cap + 1, cap),
        ),
        ok(
            "independent runways do not share the cap",
            poor(*others(15, mine - 1, "28L"), *others(15, mine - 1, "28R", "G")),
            make_package(mine),
        ),
        # D4 and D5.
        bad(
            "arrival names an unknown runway",
            poor(arrival(LARGE, mine - 1, "99")),
            make_package(mine),
        ),
        bad("runway list unknown", make_scenario(runways=None), make_package(mine)),
        ok(
            "own flight is not counted",
            poor(*others(cap - 1, mine - 1), arrival(LARGE, mine - 1, name=OWN)),
            make_package(mine),
            boundary=True,
        ),
    ]


def extra_fuel_cases() -> list[Case]:
    trip = BASELINE["trip_fuel_kg"]
    cruise = BASELINE["cruise_burn_kg_per_min"]
    alternate = BASELINE["alternate_fuel_kg"]
    reserve = rv.rule_value(rv.FUEL_RESERVE_MIN).value * cruise + alternate
    early = EARLIEST - 5
    margin = rv.rule_value(rv.ALTERNATE_WINDOW_MIN).value
    start, end = EARLIEST - margin, EARLIEST + margin
    no_alt = trip + rv.rule_value(rv.FUEL_RESERVE_MIN).value * cruise
    pre = DecisionPoint.PRE_DEPARTURE

    def sc(*periods: WeatherPeriod) -> Scenario:
        return make_scenario(fuel_on_board_kg=no_alt, destination_forecast=periods)

    return [
        # A slot before the earliest arrival is its own violation, not only a
        # side effect of a DIRECT action.
        bad(
            "hold slot before the earliest arrival",
            make_scenario(),
            make_package(early, action=FlightPlanAction.HOLD),
            boundary=True,
            violations=1,
            expect=(-5, 0),
        ),
        bad(
            "ground delay slot before the earliest arrival",
            make_scenario(decision_point=pre),
            make_package(early, action=FlightPlanAction.GROUND_DELAY),
            violations=1,
            expect=(-5, 0),
        ),
        # 121.619(a) window edges.
        bad(
            "a poor period ending exactly at ETA minus 60 counts",
            sc(forecast(start - 100, start, 1999), forecast(start, end)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "a poor period ending a minute before ETA minus 60 does not count",
            sc(forecast(start - 100, start - 1, 1999), forecast(start - 1, end)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "a poor period starting exactly at ETA plus 60 counts",
            sc(forecast(start, end), forecast(end, end + 100, 1999)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "a poor period starting a minute after ETA plus 60 does not count",
            sc(forecast(start, end + 1), forecast(end + 1, end + 100, 1999)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "a poor period inside a good one counts",
            sc(forecast(start, end), forecast(EARLIEST, EARLIEST + 5, 1999)),
            BASELINE_PACKAGE,
        ),
        ok(
            "periods given out of order are sorted before the gap scan",
            sc(forecast(EARLIEST, end), forecast(start, EARLIEST)),
            BASELINE_PACKAGE,
        ),
        ok(
            "a short period nested in a long one does not shrink the coverage",
            sc(forecast(start, end + 50), forecast(start + 10, start + 20)),
            BASELINE_PACKAGE,
        ),
        # D3: impossible values fail closed, they are not just unusual.
        bad(
            "cruise burn of zero",
            make_scenario(cruise_burn_kg_per_min=0),
            BASELINE_PACKAGE,
        ),
        bad(
            "negative cruise burn",
            make_scenario(cruise_burn_kg_per_min=-50),
            BASELINE_PACKAGE,
        ),
        ok(
            "cruise burn of one is the smallest valid rate",
            make_scenario(cruise_burn_kg_per_min=1),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "hold burn of zero on a hold",
            make_scenario(hold_burn_kg_per_min=0),
            make_package(EARLIEST + 5, action=FlightPlanAction.HOLD),
        ),
        ok(
            "invalid hold burn does not matter for a vector",
            make_scenario(hold_burn_kg_per_min=-1),
            make_package(EARLIEST + 5, action=FlightPlanAction.VECTOR),
        ),
        bad(
            "negative fuel on board",
            make_scenario(fuel_on_board_kg=-1),
            BASELINE_PACKAGE,
        ),
        bad(
            "negative trip fuel",
            make_scenario(trip_fuel_kg=-1, fuel_on_board_kg=trip + reserve),
            BASELINE_PACKAGE,
        ),
        ok(
            "trip fuel of exactly zero is valid",
            make_scenario(trip_fuel_kg=0, fuel_on_board_kg=reserve),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "negative alternate fuel when an alternate is required",
            make_scenario(alternate_fuel_kg=-1, fuel_on_board_kg=trip + reserve),
            BASELINE_PACKAGE,
        ),
        ok(
            "negative alternate fuel is ignored when none is required",
            make_scenario(
                alternate_fuel_kg=-1,
                fuel_on_board_kg=no_alt,
                destination_forecast=GOOD_FORECAST,
            ),
            BASELINE_PACKAGE,
        ),
    ]


def extra_overlap_cases() -> list[Case]:
    buf = rv.rule_value(rv.GATE_BUFFER_MIN).value
    stay = rv.turnaround(AircraftSize.NARROW_BODY).value
    start, end = GATE_IN, GATE_IN + stay
    late_departure = end + 60  # D2: the aircraft holds its gate until then

    def sc(depart: int | None, *occ: GateOccupancy) -> Scenario:
        return make_scenario(gate_occupancies=occ, next_departure_min=depart)

    return [
        ok(
            "gate held until the next departure, other flight after buffer",
            sc(late_departure, occupancy(late_departure + buf, late_departure + 90)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        bad(
            "gate held until the next departure, one minute inside buffer",
            sc(
                late_departure,
                occupancy(late_departure + buf - 1, late_departure + 90),
            ),
            BASELINE_PACKAGE,
            boundary=True,
            violations=1,
            expect=(buf - 1, buf),
        ),
        bad(
            "other flight lands while this one waits for its departure",
            sc(late_departure, occupancy(end + 5, end + 30)),
            BASELINE_PACKAGE,
            violations=1,
        ),
        bad(
            "a departure earlier than the turnaround does not shorten the stay",
            sc(end - 10, occupancy(end + buf - 1, end + 90)),
            BASELINE_PACKAGE,
            violations=1,
            expect=(buf - 1, buf),
        ),
        ok(
            "a departure exactly at the end of the turnaround",
            sc(end, occupancy(end + buf, end + 90)),
            BASELINE_PACKAGE,
            boundary=True,
        ),
        ok(
            "unknown departure falls back to the turnaround",
            sc(None, occupancy(end + buf, end + 90)),
            BASELINE_PACKAGE,
        ),
        # D4 and D5.
        bad(
            "occupancy names an unknown gate",
            sc(end, occupancy(0, 10, "A01")),
            BASELINE_PACKAGE,
            violations=1,
        ),
        bad(
            "gate map unknown",
            make_scenario(gates=None),
            BASELINE_PACKAGE,
        ),
        ok(
            "own flight's occupancy is skipped",
            sc(
                end,
                GateOccupancy(
                    gate_id="A1", flight_id=OWN, start_min=start, end_min=end
                ),
            ),
            BASELINE_PACKAGE,
        ),
        # D3.
        bad("negative taxi-in", make_scenario(taxi_in_min=-1), BASELINE_PACKAGE),
        ok(
            "taxi-in of exactly zero is valid",
            make_scenario(taxi_in_min=0),
            BASELINE_PACKAGE,
            boundary=True,
        ),
    ]


def extra_turnaround_cases() -> list[Case]:
    return [
        bad("negative taxi-in", make_scenario(taxi_in_min=-1), BASELINE_PACKAGE),
    ]


def slot_window_cases() -> list[Case]:
    latest = BASELINE["latest_arrival_min"]
    step = rv.rule_value(rv.SLOT_STEP_MIN).value
    return [
        ok(
            "earliest slot",
            make_scenario(),
            make_package(EARLIEST),
            boundary=True,
        ),
        ok(
            "latest slot",
            make_scenario(),
            make_package(latest, action=FlightPlanAction.HOLD),
            boundary=True,
        ),
        ok(
            "a slot on the grid inside the window",
            make_scenario(),
            make_package(EARLIEST + step, action=FlightPlanAction.HOLD),
        ),
        bad(
            "one step before the window",
            make_scenario(),
            make_package(EARLIEST - step, action=FlightPlanAction.HOLD),
            boundary=True,
            violations=1,
            expect=(EARLIEST - step, EARLIEST),
        ),
        bad(
            "one step after the window",
            make_scenario(),
            make_package(latest + step, action=FlightPlanAction.HOLD),
            boundary=True,
            violations=1,
            expect=(latest + step, latest),
        ),
        bad(
            "a minute off the grid",
            make_scenario(),
            make_package(EARLIEST + 1, action=FlightPlanAction.HOLD),
            boundary=True,
            violations=1,
            expect=(1, 0),
        ),
        bad(
            "just short of the next grid point",
            make_scenario(),
            make_package(EARLIEST + step - 1, action=FlightPlanAction.HOLD),
            violations=1,
            expect=(step - 1, 0),
        ),
        bad(
            "outside the window and off the grid is two violations",
            make_scenario(),
            make_package(EARLIEST - 1, action=FlightPlanAction.HOLD),
            violations=2,
        ),
        bad("a far-off slot", make_scenario(), make_package(9999)),
        bad(
            "earliest arrival unknown",
            make_scenario(earliest_arrival_min=None),
            BASELINE_PACKAGE,
        ),
        bad(
            "latest arrival unknown",
            make_scenario(latest_arrival_min=None),
            BASELINE_PACKAGE,
        ),
    ]


RULE_CASES: dict[str, list[Case]] = {
    atc.WAKE_SEPARATION: wake_cases() + extra_wake_cases(),
    atc.RUNWAY_CLOSED: runway_closed_cases() + extra_runway_cases(),
    atc.TAXIWAY_CLOSED: taxiway_closed_cases() + extra_taxiway_cases(),
    atc.RUNWAY_THROUGHPUT: throughput_cases() + extra_throughput_cases(),
    atc.SLOT_WINDOW: slot_window_cases(),
    pilot.FUEL_POLICY: fuel_cases() + extra_fuel_cases(),
    ground.GATE_OVERLAP: overlap_cases() + extra_overlap_cases(),
    ground.GATE_SIZE: size_cases() + extra_size_cases(),
    ground.TURNAROUND: turnaround_cases() + extra_turnaround_cases(),
}

# Rules whose limit is a yes/no fact in the scenario, so there is no value to
# sit exactly on. Anything else must have boundary cases.
NO_BOUNDARY = {atc.RUNWAY_CLOSED, atc.TAXIWAY_CLOSED}


def test_baseline_is_legal() -> None:
    assert check_package(make_scenario(), BASELINE_PACKAGE) == ()
    assert TAXI_IN == GATE_IN - EARLIEST


@pytest.mark.parametrize("rule_id", rule_ids())
def test_rule_has_coverage(rule_id: str) -> None:
    cases = RULE_CASES.get(rule_id, [])
    assert any(not c.fails for c in cases), f"{rule_id} has no passing test"
    assert any(c.fails for c in cases), f"{rule_id} has no failing test"
    if rule_id not in NO_BOUNDARY:
        assert any(c.boundary and not c.fails for c in cases), (
            f"{rule_id} has no passing test exactly at its limit"
        )
        assert any(c.boundary and c.fails for c in cases), (
            f"{rule_id} has no failing test just past its limit"
        )


def test_no_cases_for_unknown_rules() -> None:
    assert set(RULE_CASES) <= set(rule_ids())


def test_rule_ids_are_unique_and_prefixed_by_domain() -> None:
    prefix = {"atc": "ATC-", "pilot": "PLT-", "ground": "GND-"}
    ids = rule_ids()
    assert len(set(ids)) == len(ids)
    for rule in ALL_RULES:
        assert rule.rule_id.startswith(prefix[rule.domain.value])
        assert rule.source and rule.description


def _all_cases() -> list[tuple[str, Case]]:
    return [(rid, c) for rid, cases in RULE_CASES.items() for c in cases]


@pytest.mark.parametrize(
    ("rule_id", "case"),
    _all_cases(),
    ids=[f"{rid}:{c.name}" for rid, c in _all_cases()],
)
def test_rule_case(rule_id: str, case: Case) -> None:
    rule = next(r for r in ALL_RULES if r.rule_id == rule_id)
    found = rule.check(case.scenario, case.package)
    assert all(v.rule_id == rule_id and v.domain == rule.domain for v in found)
    assert all(v.message and v.source for v in found)
    assert bool(found) == case.fails, [v.message for v in found]
    if case.violations is not None:
        assert len(found) == case.violations
    if case.expect is not None:
        assert (found[0].observed, found[0].limit) == case.expect
    for v in found:
        if v.cause is ViolationCause.MISSING_DATA:
            assert v.observed is None
        else:
            assert v.observed is not None and v.limit is not None and v.unit
    # The aggregate check sees exactly the same violations from this rule.
    aggregate = [
        v for v in check_package(case.scenario, case.package) if v.rule_id == rule_id
    ]
    assert tuple(aggregate) == found


def test_wake_table_has_every_one_of_the_sixteen_pairs() -> None:
    """Written out by hand from the order, not read back from the table."""
    L, H, S, X = LARGE, HEAVY, SMALL, WakeCategory.SUPER
    expected = {
        (X, X): 5, (X, H): 6, (X, L): 7, (X, S): 8,
        (H, X): 3, (H, H): 4, (H, L): 5, (H, S): 6,
        (L, X): 3, (L, H): 3, (L, L): 3, (L, S): 4,
        (S, X): 3, (S, H): 3, (S, L): 3, (S, S): 3,
    }  # fmt: skip
    assert len(expected) == len(WakeCategory) ** 2
    for (leader, follower), nm in expected.items():
        entry = rv.wake_separation(leader, follower)
        assert entry.value == nm, (leader, follower)
        assert entry.unit == "nautical miles"
        # Nothing is below the radar minimum of 3 NM.
        assert entry.value >= 3


def test_approach_speed_depends_on_the_follower_only() -> None:
    for follower in WakeCategory:
        expected = 100 if follower is WakeCategory.SMALL else 130
        assert rv.approach_speed(follower).value == expected


def test_required_separation_rounds_up() -> None:
    for follower in (LARGE, SMALL):
        speed = rv.approach_speed(follower).value
        assert atc.required_separation_min(speed, follower) == 60
        assert atc.required_separation_min(speed + 1, follower) == 61
    # 6 NM: 3.6 min at 100 kt is 4; 2.77 min at 130 kt is 3.
    assert atc.required_separation_min(6, SMALL) == 4
    assert atc.required_separation_min(6, LARGE) == 3
