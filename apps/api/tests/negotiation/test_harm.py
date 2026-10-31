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
    Provenance,
    Runway,
    Sourced,
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

# True once the safety-core fixes are on this branch. Until then the rules are
# expected to disagree with this check, and the strict xfail below proves they do.
CORE_FIXES_LANDED = "parallel_group" in Runway.model_fields


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
    verdict = _verdict(HarmCheck.WAKE_SPACING, other_arrivals=(other,))
    assert verdict is HarmVerdict.CLEAR


# Required: 45 x 50 + 1,000 alternate = 3,250 kg after a 4,000 kg trip.
@pytest.mark.parametrize(
    ("on_board", "expected"),
    [(7_250, HarmVerdict.CLEAR), (7_249, HarmVerdict.HARM)],
)
def test_fuel_at_and_past_the_limit(on_board: int, expected: HarmVerdict) -> None:
    assert _verdict(HarmCheck.FUEL_MARGIN, fuel_on_board_kg=on_board) is expected


def test_fuel_counts_a_hold_at_the_hold_rate() -> None:
    hold = make_package(time_min=105, action=FlightPlanAction.HOLD)  # 5 x 40 = 200
    enough = _verdict(HarmCheck.FUEL_MARGIN, hold, fuel_on_board_kg=7_450)
    short = _verdict(HarmCheck.FUEL_MARGIN, hold, fuel_on_board_kg=7_449)
    assert enough is HarmVerdict.CLEAR
    assert short is HarmVerdict.HARM


def test_fuel_drops_the_alternate_only_on_clear_covered_weather() -> None:
    good = (
        WeatherPeriod(
            start_min=0, end_min=1_000, ceiling_ft=2_000, visibility_tenth_mi=30
        ),
    )
    verdict = _verdict(
        HarmCheck.FUEL_MARGIN, fuel_on_board_kg=6_250, destination_forecast=good
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
    scenario = make_scenario(fuel_on_board_kg=6_250, destination_forecast=split)
    report = inspect_package(scenario, make_package())
    assert report.verdict_of(HarmCheck.FUEL_MARGIN) is HarmVerdict.HARM
    assert check_package(scenario, make_package())  # and the rules agree


@pytest.mark.parametrize(
    "field",
    ["fuel_on_board_kg", "trip_fuel_kg", "cruise_burn_kg_per_min"],
)
def test_fuel_unknown_input_is_unknown_not_clear(field: str) -> None:
    assert _verdict(HarmCheck.FUEL_MARGIN, **{field: None}) is HarmVerdict.UNKNOWN


# No next departure, so the stay is 110-135; buffer 15. Clear at 150, not at 149.
@pytest.mark.parametrize(
    ("start", "expected"), [(150, HarmVerdict.CLEAR), (149, HarmVerdict.HARM)]
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
    closed_runway = (Runway(runway_id="28L", closed=True),)
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


class _Grouped:
    """A runway with a group, for any core whose contract lacks the field."""

    def __init__(self, runway_id: str, group: str | None) -> None:
        self.runway_id = runway_id
        self.closed = False
        self.parallel_group = group


def _grouped_scenario(traffic: tuple[OtherArrival, ...], group: str | None) -> Any:
    base = make_scenario(other_arrivals=traffic)
    runways = (_Grouped("28L", group), _Grouped("28R", group))
    return base.model_copy(
        update={"runways": Sourced(value=runways, provenance=Provenance.SYNTHETIC)}
    )


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


def test_parallel_runways_in_a_group_share_throughput() -> None:
    traffic = _on("28R", range(68, 98))  # 30 others, so we are the 31st
    package = make_package()
    alone = inspect_package(_grouped_scenario(traffic, None), package)
    grouped = inspect_package(_grouped_scenario(traffic, "P1"), package)
    assert alone.verdict_of(HarmCheck.THROUGHPUT) is HarmVerdict.CLEAR
    assert grouped.verdict_of(HarmCheck.THROUGHPUT) is HarmVerdict.HARM


GOOD_WEATHER = WeatherPeriod(
    start_min=0, end_min=1_000, ceiling_ft=5_000, visibility_tenth_mi=100
)


# IFR cap 30: 29 others fit and 30 do not. VFR cap 40: 39 fit and 40 do not.
@pytest.mark.parametrize(
    ("others", "forecast", "expected"),
    [
        (29, None, HarmVerdict.CLEAR),
        (30, None, HarmVerdict.HARM),
        (39, (GOOD_WEATHER,), HarmVerdict.CLEAR),
        (40, (GOOD_WEATHER,), HarmVerdict.HARM),
    ],
)
def test_throughput_cap_follows_the_forecast_at_eta(
    others: int, forecast: tuple[WeatherPeriod, ...] | None, expected: HarmVerdict
) -> None:
    verdict = _verdict(
        HarmCheck.THROUGHPUT,
        other_arrivals=_on("28L", range(98 - others, 98)),
        destination_forecast=forecast,
        flight_rules=FlightRules.IFR,  # must not decide the cap
    )
    assert verdict is expected


def test_throughput_counts_only_the_hour_around_the_arrival() -> None:
    far = _on("28L", range(0, 40))  # all over an hour before the arrival at 100
    verdict = _verdict(HarmCheck.THROUGHPUT, other_arrivals=far)
    assert verdict is HarmVerdict.CLEAR


def test_small_follower_uses_its_own_approach_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    general = rv.RULE_VALUES[rv.APPROACH_GROUND_SPEED_KT]
    table = {
        **rv.RULE_VALUES,
        "approach_ground_speed_kt.small": general.model_copy(update={"value": 100}),
    }
    monkeypatch.setattr(rv, "RULE_VALUES", table)
    # Small behind large is 4 nm. At 100 kt 2 minutes is 3.3 nm, 3 minutes is 5 nm.
    # At 130 kt 2 minutes would have been 4.3 nm, and clear.
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


@pytest.mark.xfail(
    not CORE_FIXES_LANDED,
    reason="harm.py already applies the safety-core fixes that have not reached this "
    "branch: gate held to next departure, cap from the forecast at ETA",
    strict=True,
)
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
