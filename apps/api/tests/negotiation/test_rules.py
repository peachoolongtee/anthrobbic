"""Every rule ID needs passing, failing and (for numeric rules) boundary cases.

Cases live in `RULE_CASES`, keyed by rule ID. `test_rule_has_coverage` is
parametrised over the rule registry, so a rule added without cases fails.
"""

import math
from dataclasses import dataclass
from fractions import Fraction

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
    WakeCategory,
    WeatherPeriod,
)
from app.negotiation.rules import ALL_RULES, check_package, rule_ids
from app.negotiation.rules import atc, ground, pilot
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


def ok(name: str, scenario: Scenario, package: Package, **kw: bool) -> Case:
    return Case(name, scenario, package, fails=False, **kw)


def bad(name: str, scenario: Scenario, package: Package, **kw: object) -> Case:
    return Case(name, scenario, package, fails=True, **kw)  # type: ignore[arg-type]


def sep_min(leader: WakeCategory, follower: WakeCategory) -> int:
    """Independent restatement of nm -> minutes, rounded up."""
    nm = rv.wake_separation(leader, follower).value
    speed = rv.rule_value(rv.APPROACH_GROUND_SPEED_KT).value
    return math.ceil(Fraction(nm * 60, speed))


def arrival(
    wake: WakeCategory, time_min: int, runway_id: str = "28L", name: str = "XY9"
) -> OtherArrival:
    return OtherArrival(
        flight_id=name, wake_category=wake, runway_id=runway_id, time_min=time_min
    )


def with_arrivals(*arrivals: OtherArrival, **overrides: object) -> Scenario:
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
    vfr_cap = rv.runway_hourly_arrivals(FlightRules.VFR).value
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
        bad(
            "flight rules unknown",
            make_scenario(flight_rules=None),
            make_package(mine),
        ),
        ok(
            "VFR allows its higher cap",
            make_scenario(
                flight_rules=FlightRules.VFR,
                other_arrivals=others(vfr_cap - 1, mine - 1),
            ),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "VFR one over its cap",
            make_scenario(
                flight_rules=FlightRules.VFR, other_arrivals=others(vfr_cap, mine - 1)
            ),
            make_package(mine),
            boundary=True,
        ),
        bad(
            "IFR cap still binds with the VFR count of aircraft",
            make_scenario(
                flight_rules=FlightRules.IFR,
                other_arrivals=others(vfr_cap - 1, mine - 1),
            ),
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
        return make_scenario(gate_occupancies=occ)

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


RULE_CASES: dict[str, list[Case]] = {
    atc.WAKE_SEPARATION: wake_cases(),
    atc.RUNWAY_CLOSED: runway_closed_cases(),
    atc.TAXIWAY_CLOSED: taxiway_closed_cases(),
    atc.RUNWAY_THROUGHPUT: throughput_cases(),
    pilot.FUEL_POLICY: fuel_cases(),
    ground.GATE_OVERLAP: overlap_cases(),
    ground.GATE_SIZE: size_cases(),
    ground.TURNAROUND: turnaround_cases(),
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
    # The aggregate check sees exactly the same violations from this rule.
    aggregate = [
        v for v in check_package(case.scenario, case.package) if v.rule_id == rule_id
    ]
    assert tuple(aggregate) == found


def test_wake_table_matches_the_stated_values() -> None:
    nm = {
        (WakeCategory.HEAVY, WakeCategory.HEAVY): 4,
        (WakeCategory.HEAVY, WakeCategory.LARGE): 5,
        (WakeCategory.HEAVY, WakeCategory.SMALL): 6,
        (WakeCategory.LARGE, WakeCategory.SMALL): 4,
        (WakeCategory.SUPER, WakeCategory.SUPER): 5,
        (WakeCategory.SUPER, WakeCategory.HEAVY): 6,
        (WakeCategory.SUPER, WakeCategory.LARGE): 7,
        (WakeCategory.SUPER, WakeCategory.SMALL): 8,
        (WakeCategory.LARGE, WakeCategory.LARGE): 3,
        (WakeCategory.SMALL, WakeCategory.HEAVY): 3,
    }
    for (leader, follower), expected in nm.items():
        assert rv.wake_separation(leader, follower).value == expected


def test_required_separation_rounds_up() -> None:
    speed = rv.rule_value(rv.APPROACH_GROUND_SPEED_KT).value
    assert atc.required_separation_min(speed) == 60
    assert atc.required_separation_min(speed + 1) == 61
