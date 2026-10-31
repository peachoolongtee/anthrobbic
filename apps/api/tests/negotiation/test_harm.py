"""The harm check, at and past each limit, and its disagreements with the rules."""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.negotiation import harm
from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    AircraftSize,
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
from app.negotiation.harm import (
    RULES_COVERED,
    DisagreementKind,
    HarmCheck,
    HarmVerdict,
    compare_with_rules,
    inspect_package,
)
from app.negotiation.options import PackageBoundError, enumerate_packages
from app.negotiation.rules import check_package, rule_ids
from tests.negotiation.factories import make_package, make_scenario, random_scenario


def _arrival(minute: int, wake: WakeCategory = WakeCategory.LARGE) -> OtherArrival:
    return OtherArrival(
        flight_id="X", wake_category=wake, runway_id="28L", time_min=minute
    )


def _verdict(
    check: HarmCheck, package: Package | None = None, **overrides: Any
) -> HarmVerdict:
    report = inspect_package(make_scenario(**overrides), package or make_package())
    return report.verdict_of(check)


def test_baseline_package_is_clear() -> None:
    scenario = make_scenario()
    report = inspect_package(scenario, make_package())
    assert not report.harmful
    assert not report.unknown
    assert not compare_with_rules(report, check_package(scenario, make_package()))


def test_harm_imports_nothing_from_rules_by_source() -> None:
    tree = ast.parse(Path(harm.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    banned = ("rules", "options", "utility", "fallback")
    assert not [
        name
        for name in imported
        if any(name.startswith(f"app.negotiation.{b}") for b in banned)
    ]


def test_harm_does_not_load_rules_at_runtime() -> None:
    code = (
        "import sys; import app.negotiation.harm; "
        "print(any(m.startswith('app.negotiation.rules') for m in sys.modules))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(harm.__file__).parents[2],
    )
    assert done.stdout.strip() == "False"


def test_covered_rule_ids_exist_in_the_registry() -> None:
    covered = {rule for rules in RULES_COVERED.values() for rule in rules}
    assert covered <= set(rule_ids())


# 3 nm at 130 kt is 83 s: 1 minute short, 2 minutes enough.
@pytest.mark.parametrize(
    ("other_minute", "expected"),
    [
        (98, HarmVerdict.CLEAR),
        (99, HarmVerdict.HARM),
        (100, HarmVerdict.HARM),
        (101, HarmVerdict.HARM),
        (102, HarmVerdict.CLEAR),
    ],
)
def test_wake_spacing_at_and_past_the_limit(
    other_minute: int, expected: HarmVerdict
) -> None:
    verdict = _verdict(HarmCheck.WAKE_SPACING, other_arrivals=(_arrival(other_minute),))
    assert verdict is expected


def test_wake_uses_the_heavier_leader_when_we_follow() -> None:
    # Heavy then large is 5 nm: 139 s, so 2 minutes is short and 3 is enough.
    heavy = WakeCategory.HEAVY
    short = _verdict(HarmCheck.WAKE_SPACING, other_arrivals=(_arrival(98, heavy),))
    enough = _verdict(HarmCheck.WAKE_SPACING, other_arrivals=(_arrival(97, heavy),))
    assert short is HarmVerdict.HARM
    assert enough is HarmVerdict.CLEAR


def test_wake_ignores_another_runway() -> None:
    other = OtherArrival(
        flight_id="X", wake_category=WakeCategory.SUPER, runway_id="28R", time_min=100
    )
    independent = (
        Runway(runway_id="28L", closed=False, parallel_group=None),
        Runway(runway_id="28R", closed=False, parallel_group=None),
    )
    verdict = _verdict(
        HarmCheck.WAKE_SPACING, other_arrivals=(other,), runways=independent
    )
    assert verdict is HarmVerdict.CLEAR


# Required, worked by hand: 30 min x 40 kg/min of holding fuel = 1,200, plus 5% of
# the 4,000 kg trip = 200, plus the 1,000 kg alternate = 2,400 kg left after the
# trip. So 4,000 + 2,400 = 6,400 kg on board is exactly enough.
@pytest.mark.parametrize(
    ("on_board", "expected"),
    [(6_400, HarmVerdict.CLEAR), (6_399, HarmVerdict.HARM)],
)
def test_fuel_at_and_past_the_limit(on_board: int, expected: HarmVerdict) -> None:
    assert _verdict(HarmCheck.FUEL_MARGIN, fuel_on_board_kg=on_board) is expected


def test_fuel_counts_a_hold_at_the_hold_rate() -> None:
    hold = make_package(time_min=105, action=FlightPlanAction.HOLD)  # 5 x 40 = 200
    enough = _verdict(HarmCheck.FUEL_MARGIN, hold, fuel_on_board_kg=6_600)
    short = _verdict(HarmCheck.FUEL_MARGIN, hold, fuel_on_board_kg=6_599)
    assert enough is HarmVerdict.CLEAR
    assert short is HarmVerdict.HARM


def test_fuel_drops_the_alternate_only_on_clear_covered_weather() -> None:
    good = (
        WeatherPeriod(
            start_min=0, end_min=1_000, ceiling_ft=2_000, visibility_tenth_mi=30
        ),
    )
    # With no alternate the need is 1,200 + 200 = 1,400 kg after the 4,000 trip.
    verdict = _verdict(
        HarmCheck.FUEL_MARGIN, fuel_on_board_kg=5_400, destination_forecast=good
    )
    assert verdict is HarmVerdict.CLEAR
    # The minute between two closed periods is uncovered, so an alternate is needed.
    split = (
        WeatherPeriod(
            start_min=0, end_min=100, ceiling_ft=2_000, visibility_tenth_mi=30
        ),
        WeatherPeriod(
            start_min=101, end_min=1_000, ceiling_ft=2_000, visibility_tenth_mi=30
        ),
    )
    scenario = make_scenario(fuel_on_board_kg=5_400, destination_forecast=split)
    report = inspect_package(scenario, make_package())
    assert report.verdict_of(HarmCheck.FUEL_MARGIN) is HarmVerdict.HARM
    assert check_package(scenario, make_package())  # and the rules agree


@pytest.mark.parametrize(
    "field",
    ["fuel_on_board_kg", "trip_fuel_kg", "hold_burn_kg_per_min"],
)
def test_fuel_unknown_input_is_unknown_not_clear(field: str) -> None:
    assert _verdict(HarmCheck.FUEL_MARGIN, **{field: None}) is HarmVerdict.UNKNOWN


# No next departure, so the stay is 110-145 (35 min, the airport's minimum
# turnaround); buffer 15. Clear at 160, not at 159.
@pytest.mark.parametrize(
    ("start", "expected"), [(160, HarmVerdict.CLEAR), (159, HarmVerdict.HARM)]
)
def test_gate_after_us_at_and_past_the_buffer(
    start: int, expected: HarmVerdict
) -> None:
    occupancy = GateOccupancy(
        gate_id="A1", flight_id="N", start_min=start, end_min=start + 30
    )
    verdict = _verdict(
        HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,), next_departure_min=None
    )
    assert verdict is expected


@pytest.mark.parametrize(
    ("end", "expected"), [(95, HarmVerdict.CLEAR), (96, HarmVerdict.HARM)]
)
def test_gate_before_us_at_and_past_the_buffer(end: int, expected: HarmVerdict) -> None:
    occupancy = GateOccupancy(gate_id="A1", flight_id="P", start_min=20, end_min=end)
    assert _verdict(HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,)) is expected


def test_gate_ignores_other_gates() -> None:
    occupancy = GateOccupancy(gate_id="Z9", flight_id="P", start_min=100, end_min=130)
    verdict = _verdict(HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,))
    assert verdict is HarmVerdict.CLEAR


def test_closed_runway_and_taxiway_are_harm() -> None:
    closed_runway = (Runway(runway_id="28L", closed=True, parallel_group=None),)
    closed_taxiway = (
        Taxiway(taxiway_id="T1", closed=True),
        Taxiway(taxiway_id="T2", closed=False),
    )
    runway = _verdict(HarmCheck.CLOSED_RESOURCE, runways=closed_runway)
    taxiway = _verdict(HarmCheck.CLOSED_RESOURCE, taxiways=closed_taxiway)
    assert runway is HarmVerdict.HARM
    assert taxiway is HarmVerdict.HARM


@pytest.mark.parametrize(
    "package",
    [make_package(runway_id="NOPE"), make_package(gate_id="NOPE")],
)
def test_unlisted_resources_are_unknown(package: Package) -> None:
    assert _verdict(HarmCheck.CLOSED_RESOURCE, package) is HarmVerdict.UNKNOWN


def test_gate_is_held_until_a_known_next_departure() -> None:
    # Turnaround alone frees the gate at 135, but the aircraft is due out at 200.
    occupancy = GateOccupancy(gate_id="A1", flight_id="N", start_min=160, end_min=170)
    held = _verdict(HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,))
    assert held is HarmVerdict.HARM
    gone = _verdict(
        HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,), next_departure_min=None
    )
    assert gone is HarmVerdict.CLEAR


# Held to 200, buffer 15: a stay starting at 215 is clear and at 214 is not.
@pytest.mark.parametrize(
    ("start", "expected"), [(215, HarmVerdict.CLEAR), (214, HarmVerdict.HARM)]
)
def test_gate_after_departure_at_and_past_the_buffer(
    start: int, expected: HarmVerdict
) -> None:
    occupancy = GateOccupancy(
        gate_id="A1", flight_id="N", start_min=start, end_min=start + 30
    )
    verdict = _verdict(HarmCheck.GATE_OVERLAP, gate_occupancies=(occupancy,))
    assert verdict is expected


def _grouped_scenario(traffic: tuple[OtherArrival, ...], group: str | None) -> Scenario:
    runways = (
        Runway(runway_id="28L", closed=False, parallel_group=group),
        Runway(runway_id="28R", closed=False, parallel_group=group),
    )
    return make_scenario(other_arrivals=traffic, runways=runways)


def test_parallel_runways_in_a_group_share_wake_spacing() -> None:
    other = OtherArrival(
        flight_id="X", wake_category=WakeCategory.LARGE, runway_id="28R", time_min=99
    )
    package = make_package()
    alone = inspect_package(_grouped_scenario((other,), None), package)
    grouped = inspect_package(_grouped_scenario((other,), "P1"), package)
    assert alone.verdict_of(HarmCheck.WAKE_SPACING) is HarmVerdict.CLEAR
    assert grouped.verdict_of(HarmCheck.WAKE_SPACING) is HarmVerdict.HARM


def _on(runway_id: str, minutes: range) -> tuple[OtherArrival, ...]:
    return tuple(
        OtherArrival(
            flight_id=f"Q{m}",
            wake_category=WakeCategory.LARGE,
            runway_id=runway_id,
            time_min=m,
        )
        for m in minutes
    )


def test_throughput_is_an_airport_total_whatever_the_parallel_groups() -> None:
    traffic = _on("28R", range(62, 98))  # 36 others, so we are the 37th of 36
    package = make_package()
    alone = inspect_package(_grouped_scenario(traffic, None), package)
    grouped = inspect_package(_grouped_scenario(traffic, "P1"), package)
    assert alone.verdict_of(HarmCheck.THROUGHPUT) is HarmVerdict.HARM
    assert grouped.verdict_of(HarmCheck.THROUGHPUT) is HarmVerdict.HARM


GOOD_WEATHER = WeatherPeriod(
    start_min=0, end_min=1_000, ceiling_ft=5_000, visibility_tenth_mi=100
)


# The cap is the airport's workbook figure: 36 for the baseline small hub, so 35
# others fit and 36 do not; 90 at a large hub, so 89 fit and 90 do not. Weather and
# flight rules do not move it.
@pytest.mark.parametrize(
    ("others", "cap", "forecast", "expected"),
    [
        (35, 36, None, HarmVerdict.CLEAR),
        (36, 36, None, HarmVerdict.HARM),
        (35, 36, (GOOD_WEATHER,), HarmVerdict.CLEAR),
        (36, 36, (GOOD_WEATHER,), HarmVerdict.HARM),
        (89, 90, None, HarmVerdict.CLEAR),
        (90, 90, None, HarmVerdict.HARM),
    ],
)
def test_throughput_cap_is_the_airports_workbook_figure(
    others: int,
    cap: int,
    forecast: tuple[WeatherPeriod, ...] | None,
    expected: HarmVerdict,
) -> None:
    verdict = _verdict(
        HarmCheck.THROUGHPUT,
        # Many land in the same minute so that they all fit in one hour.
        other_arrivals=tuple(_arrival(60 + i % 38) for i in range(others)),
        airport_ops_per_hour=cap,
        destination_forecast=forecast,
        flight_rules=FlightRules.IFR,  # must not decide the cap
    )
    assert verdict is expected


def test_throughput_counts_every_runway_toward_the_airport_total() -> None:
    both = (*_on("28L", range(80, 98)), *_on("28R", range(60, 78)))  # 36 in all
    assert _verdict(HarmCheck.THROUGHPUT, other_arrivals=both) is HarmVerdict.HARM
    fewer = both[:-1]
    assert _verdict(HarmCheck.THROUGHPUT, other_arrivals=fewer) is HarmVerdict.CLEAR


def test_unknown_airport_cap_cannot_clear_throughput() -> None:
    verdict = _verdict(HarmCheck.THROUGHPUT, airport_ops_per_hour=None)
    assert verdict is HarmVerdict.UNKNOWN


# Gate change notice: decided at least 20 minutes before the 100 arrival.
@pytest.mark.parametrize(
    ("decided", "expected"), [(80, HarmVerdict.CLEAR), (81, HarmVerdict.HARM)]
)
def test_gate_notice_at_and_past_the_limit(decided: int, expected: HarmVerdict) -> None:
    verdict = _verdict(
        HarmCheck.GATE_NOTICE, make_package(gate_id="B1"), decision_time_min=decided
    )
    assert verdict is expected


def test_gate_notice_is_not_needed_for_the_planned_gate() -> None:
    verdict = _verdict(HarmCheck.GATE_NOTICE, decision_time_min=500)
    assert verdict is HarmVerdict.CLEAR


@pytest.mark.parametrize("field", ["decision_time_min", "planned_gate"])
def test_gate_notice_unknown_input_is_unknown(field: str) -> None:
    verdict = _verdict(
        HarmCheck.GATE_NOTICE, make_package(gate_id="B1"), **{field: None}
    )
    assert verdict is HarmVerdict.UNKNOWN


# Crew duty: 13 hours = 780 min from report; gate-in is 110, so report -670 is
# exactly at the limit.
@pytest.mark.parametrize(
    ("report", "expected"), [(-670, HarmVerdict.CLEAR), (-671, HarmVerdict.HARM)]
)
def test_crew_duty_at_and_past_the_limit(report: int, expected: HarmVerdict) -> None:
    assert _verdict(HarmCheck.CREW_DUTY, crew_report_min=report) is expected


@pytest.mark.parametrize("field", ["crew_report_min", "taxi_in_min"])
def test_crew_duty_unknown_input_is_unknown(field: str) -> None:
    assert _verdict(HarmCheck.CREW_DUTY, **{field: None}) is HarmVerdict.UNKNOWN


def test_harms_own_copy_of_the_workbook_values_matches_the_table() -> None:
    """The copy in harm.py stays independent of the rules, so this is the alarm
    for drift between it and `rule_values`."""
    assert harm._FINAL_RESERVE_HOLD_MIN == rv.rule_value(rv.FUEL_RESERVE_MIN).value
    assert (
        harm._CONTINGENCY_PERCENT_OF_TRIP
        == rv.rule_value(rv.FUEL_CONTINGENCY_PCT).value
    )
    assert (
        harm._GATE_CHANGE_NOTICE_MIN == rv.rule_value(rv.GATE_CHANGE_NOTICE_MIN).value
    )
    assert harm._CREW_MAX_DUTY_MIN == rv.rule_value(rv.CREW_MAX_DUTY_MIN).value
    assert harm._MINUTES_IN_HOUR == rv.rule_value(rv.MINUTES_PER_HOUR).value


def test_throughput_counts_only_the_hour_around_the_arrival() -> None:
    far = _on("28L", range(0, 40))  # all over an hour before the arrival at 100
    verdict = _verdict(HarmCheck.THROUGHPUT, other_arrivals=far)
    assert verdict is HarmVerdict.CLEAR


def test_small_follower_uses_its_own_approach_speed() -> None:
    # Small behind large is 4 nm. At 100 kt 2 minutes is 3.3 nm and 3 minutes is 5 nm.
    # At the other classes' 130 kt, 2 minutes would have been 4.3 nm, and clear.
    assert rv.approach_speed(WakeCategory.SMALL).value == 100
    short = _verdict(
        HarmCheck.WAKE_SPACING,
        wake_category=WakeCategory.SMALL,
        other_arrivals=(_arrival(98),),
    )
    enough = _verdict(
        HarmCheck.WAKE_SPACING,
        wake_category=WakeCategory.SMALL,
        other_arrivals=(_arrival(97),),
    )
    assert short is HarmVerdict.HARM
    assert enough is HarmVerdict.CLEAR


@pytest.mark.parametrize(
    ("time_min", "expected"),
    [
        (100, HarmVerdict.CLEAR),
        (105, HarmVerdict.CLEAR),
        (120, HarmVerdict.CLEAR),
        (95, HarmVerdict.HARM),  # before the window
        (125, HarmVerdict.HARM),  # after it
        (103, HarmVerdict.HARM),  # off the grid
    ],
)
def test_slot_must_be_in_the_window_and_on_the_grid(
    time_min: int, expected: HarmVerdict
) -> None:
    package = make_package(time_min=time_min, action=FlightPlanAction.HOLD)
    assert _verdict(HarmCheck.SLOT_VALIDITY, package) is expected


def test_unknown_window_cannot_clear_a_slot() -> None:
    verdict = _verdict(HarmCheck.SLOT_VALIDITY, latest_arrival_min=None)
    assert verdict is HarmVerdict.UNKNOWN


def test_a_slot_the_rules_passed_outright_is_harm_only() -> None:
    package = make_package(time_min=103, action=FlightPlanAction.HOLD)
    report = inspect_package(make_scenario(), package)
    found = compare_with_rules(report, [])
    assert [(d.check, d.kind) for d in found] == [
        (HarmCheck.SLOT_VALIDITY, DisagreementKind.HARM_ONLY)
    ]


def test_a_rule_that_misses_harm_is_reported_as_harm_only() -> None:
    """Every record for a gate counts here. Before the core's fix, the taxiway rule
    read only the first record, and this check caught that on hand-built data."""
    gates = (
        Gate(gate_id="A1", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY),
        Gate(gate_id="A1", taxiway_id="T2", max_size=AircraftSize.NARROW_BODY),
    )
    taxiways = (
        Taxiway(taxiway_id="T1", closed=False),
        Taxiway(taxiway_id="T2", closed=True),
    )
    scenario = make_scenario(gates=gates, taxiways=taxiways)
    found = compare_with_rules(inspect_package(scenario, make_package()), [])
    assert [(d.check, d.kind) for d in found] == [
        (HarmCheck.CLOSED_RESOURCE, DisagreementKind.HARM_ONLY)
    ]


def test_rules_that_fire_when_harm_is_clear_are_reported() -> None:
    occupancy = GateOccupancy(gate_id="A1", flight_id="N", start_min=120, end_min=170)
    scenario = make_scenario(gate_occupancies=(occupancy,))
    violations = check_package(scenario, make_package())
    assert violations
    clear = inspect_package(make_scenario(), make_package())
    kinds = {d.kind for d in compare_with_rules(clear, violations)}
    assert kinds == {DisagreementKind.RULES_ONLY}


def test_rules_failing_closed_on_data_harm_did_not_need_is_labelled() -> None:
    scenario = make_scenario(decision_point=None)
    report = inspect_package(scenario, make_package())
    found = compare_with_rules(report, check_package(scenario, make_package()))
    assert [d.kind for d in found] == [DisagreementKind.RULES_FAIL_CLOSED_ONLY]


def test_fuel_coherence_violations_are_not_fuel_disagreements() -> None:
    package = make_package(time_min=105)  # direct cannot absorb a delay
    violations = check_package(make_scenario(), package)
    assert violations
    report = inspect_package(make_scenario(), package)
    assert not compare_with_rules(report, violations)


def test_rules_and_harm_agree_on_every_package_of_random_scenarios() -> None:
    """Over all enumerated packages, the four shared checks never disagree on a
    real limit. Missing-data differences are allowed and labelled above."""
    serious = {
        DisagreementKind.HARM_ONLY,
        DisagreementKind.RULES_ONLY,
        DisagreementKind.HARM_UNKNOWN,
    }
    compared = 0
    for seed in range(400):
        scenario = random_scenario(seed)
        try:
            packages = enumerate_packages(scenario)
        except PackageBoundError:
            continue
        for package in packages:
            compared += 1
            found = compare_with_rules(
                inspect_package(scenario, package), check_package(scenario, package)
            )
            bad = [d for d in found if d.kind in serious]
            assert not bad, (seed, package, bad)
    assert compared > 5_000
