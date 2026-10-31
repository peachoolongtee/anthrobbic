"""Crew duty and gate notice must be measured on one clock.

A DOT row's scheduled departure is on the origin airport's clock; the scenario,
its slots and its taxi-in are on the destination's. The crew report time and the
late-aircraft decision time come from that departure, so they have to be moved
across the zone difference before the rules subtract them from a slot.
"""

import shutil
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.negotiation import dot
from app.negotiation.contracts import (
    ArrivalSlot,
    FlightPlanAction,
    Package,
    Scenario,
    Sourced,
)
from app.negotiation.harm import HarmCheck, HarmVerdict, inspect_package
from app.negotiation.rules import ground, pilot
from app.negotiation.scenario import GeneratorParams, build_scenario

FIXTURE = Path(__file__).parent / "fixtures" / "flights_sample.csv"
LIMIT = 780  # 13 hours, in minutes
NOTICE = 20
TAXI = 7
# One fixed lead, so the report time is dep_dest - 60 and the answer is by hand.
FIXED = GeneratorParams(
    p_crew_late_in_duty=0.0,
    crew_report_lead_min=(60, 60),
    crew_report_late_lead_min=(60, 60),
)


@pytest.fixture
def csv_file(tmp_path: Path) -> Iterator[Path]:
    target = tmp_path / "flights.csv"
    shutil.copy(FIXTURE, target)
    yield target
    dot.clear_connections()


@pytest.fixture
def base_row(csv_file: Path) -> dot.DotRow:
    return next(r for r in dot.iter_eligible_rows(csv_file) if r.flight_id == "NK301")


def make_row(
    base: dot.DotRow, dep: int, arr: int, block: int, cause: str = "late_aircraft"
) -> dot.DotRow:
    return replace(
        base,
        scheduled_departure=dep,
        scheduled_arrival=arr,
        scheduled_time=block,
        late_aircraft_delay=30 if cause == "late_aircraft" else None,
        weather_delay=30 if cause == "weather" else None,
    )


def scenario_for(row: dot.DotRow, csv_file: Path) -> Scenario:
    built = build_scenario(row, 0, csv_file, FIXED)
    return built.model_copy(
        update={
            "taxi_in_min": Sourced(value=TAXI, provenance=built.taxi_in_min.provenance)
        }
    )


def pkg(slot: int, gate: str = "ELSEWHERE") -> Package:
    return Package(
        slot=ArrivalSlot(runway_id="R1", time_min=slot),
        gate_id=gate,
        action=FlightPlanAction.HOLD,
    )


def duty(scenario: Scenario, slot: int) -> bool:
    """True when the crew rule fires at this slot."""
    return bool(pilot.check_crew_duty(scenario, pkg(slot)))


def notice_fires(scenario: Scenario, slot: int) -> bool:
    return bool(ground.check_gate_notice(scenario, pkg(slot)))


# (name, departure HHMM, arrival HHMM, block, destination-clock departure,
#  slot at which duty is exactly 13 hours, slot at which notice is exactly 20).
# Worked by hand. Offset = arrival - departure - block, in minutes.
#   west:  935 -> 1117, 282 block: 677 - 575 - 282 = -180. Destination-clock
#          departure 575 - 180 = 395; report 395 - 60 = 335; duty = slot + 7 - 335
#          = 780 at slot 1108. Decision 395 + 30 = 425; notice = slot - 425 = 20
#          at slot 445.
#   east:  800 -> 1600, 300 block: 960 - 480 - 300 = +180. Departure 480 + 180 =
#          660; report 600; duty 780 at slot 1373. Decision 690; notice 20 at 710.
#   same:  900 -> 1100, 120 block: 660 - 540 - 120 = 0. Departure 540; report 480;
#          duty 780 at slot 1253. Decision 570; notice 20 at 590.
CASES = [
    ("westbound", 935, 1117, 282, 395, 1108, 445),
    ("eastbound", 800, 1600, 300, 660, 1373, 710),
    ("same zone", 900, 1100, 120, 540, 1253, 590),
]


@pytest.mark.parametrize(
    ("name", "dep", "arr", "block", "dep_dest", "duty_slot", "notice_slot"),
    CASES,
    ids=[c[0] for c in CASES],
)
def test_clocks_by_hand(
    base_row: dot.DotRow,
    csv_file: Path,
    name: str,
    dep: int,
    arr: int,
    block: int,
    dep_dest: int,
    duty_slot: int,
    notice_slot: int,
) -> None:
    row = make_row(base_row, dep, arr, block)
    assert dot.scheduled_departure_min(row) == dep_dest
    scenario = scenario_for(row, csv_file)
    assert scenario.crew_report_min.value == dep_dest - 60
    assert scenario.decision_time_min.value == dep_dest + 30
    # Crew duty: exactly 13 hours is allowed, a minute more is not.
    assert not duty(scenario, duty_slot)
    assert duty(scenario, duty_slot + 1)
    violation = pilot.check_crew_duty(scenario, pkg(duty_slot + 1))[0]
    assert (violation.observed, violation.limit) == (LIMIT + 1, LIMIT)
    # Gate notice: exactly 20 minutes is allowed, 19 is not.
    assert not notice_fires(scenario, notice_slot)
    assert notice_fires(scenario, notice_slot - 1)
    short = ground.check_gate_notice(scenario, pkg(notice_slot - 1))[0]
    assert (short.observed, short.limit) == (NOTICE - 1, NOTICE)


def test_the_example_that_the_old_clock_mix_got_wrong(
    base_row: dot.DotRow, csv_file: Path
) -> None:
    """CVG to SEA, 0935 ET to 1117 PT, block 282. The crew report is on the
    destination clock, 335, so a slot at 1109 is 781 minutes of duty, over the
    limit. With the origin-clock report (515) it read 601 and passed."""
    scenario = scenario_for(make_row(base_row, 935, 1117, 282), csv_file)
    assert duty(scenario, 1109)
    assert 1109 + TAXI - 515 == 601  # what the mixed clock would have said


def test_weather_decision_time_is_already_on_the_destination_clock(
    base_row: dot.DotRow, csv_file: Path
) -> None:
    for _, dep, arr, block, dep_dest, _, _ in CASES:
        row = make_row(base_row, dep, arr, block, cause="weather")
        scenario = scenario_for(row, csv_file)
        # One hour before the scheduled arrival: dep_dest + block - 60.
        assert scenario.decision_time_min.value == dep_dest + block - 60
        assert scenario.decision_time_min.value == dot.scheduled_arrival_min(row) - 60


def test_a_row_with_no_block_time_has_no_offset_to_apply(base_row: dot.DotRow) -> None:
    """`scheduled_arrival_rel` falls back to the arrival clock reading when there
    is no block time, so there is no zone difference to add here either."""
    row = replace(base_row, scheduled_time=None)
    assert (
        dot.clock_offset_min(row.scheduled_departure, row.scheduled_arrival, None) == 0
    )
    assert dot.scheduled_departure_min(row) == dot.hhmm_to_min(row.scheduled_departure)


def test_midnight_and_date_line_style_rows_use_the_arrival_arithmetic(
    base_row: dot.DotRow,
) -> None:
    # Arrives after midnight: 2300 -> 0130 (+1 day), block 150, same zone.
    late = make_row(base_row, 2300, 130, 150)
    assert dot.clock_offset_min(2300, 130, 150) == 0
    assert dot.scheduled_departure_min(late) == 23 * 60
    assert dot.scheduled_arrival_min(late) == 23 * 60 + 150
    # Eastbound across midnight: 2000 PT, 300 min, lands 0400 ET the next day. The
    # arrival less departure less block is -1260, which folds to +180.
    east = make_row(base_row, 2000, 400, 300)
    assert dot.clock_offset_min(2000, 400, 300) == 180
    assert dot.scheduled_departure_min(east) == 20 * 60 + 180
    assert dot.scheduled_arrival_min(east) == 20 * 60 + 180 + 300
    # Westbound across midnight: 2330 ET, 300 min, lands 0130 PT the next day.
    # 90 - 1410 - 300 = -1620, which folds to -180.
    west = make_row(base_row, 2330, 130, 300)
    assert dot.clock_offset_min(2330, 130, 300) == -180
    assert dot.scheduled_departure_min(west) == 23 * 60 + 30 - 180
    # Whatever the row, departure plus block is the arrival, on one clock.
    for row, block in ((late, 150), (east, 300), (west, 300)):
        assert dot.scheduled_departure_min(row) + block == dot.scheduled_arrival_min(
            row
        )


def utc_offset_from_schedule(row: dot.DotRow) -> int | None:
    """Independent of the code under test: destination clock minus origin clock,
    from the row's own schedule, folded to within plus or minus twelve hours."""
    if row.scheduled_time is None:
        return None
    dep = (row.scheduled_departure // 100) * 60 + row.scheduled_departure % 100
    arr = (row.scheduled_arrival // 100) * 60 + row.scheduled_arrival % 100
    diff = (arr - dep - row.scheduled_time) % 1440
    if diff > 720:
        diff -= 1440
    return diff if abs(diff) <= 420 else None


def test_duty_and_notice_agree_with_a_utc_calculation_on_every_fixture_row(
    csv_file: Path,
) -> None:
    checked = 0
    for row in dot.iter_eligible_rows(csv_file):
        zone = utc_offset_from_schedule(row)
        if zone is None:
            continue
        dep_utc = (row.scheduled_departure // 100) * 60 + row.scheduled_departure % 100
        scenario = scenario_for(row, csv_file)
        late = dot.cause_of(row) == "late_aircraft"
        # Decision instant in UTC: the departure plus the inbound margin, or one
        # hour before the scheduled arrival (departure plus block, in UTC).
        decision_utc = (
            dep_utc + 30 if late else dep_utc + (row.scheduled_time or 0) - 60
        )
        for slot in (700, 1000, 1500):  # slots on the destination clock
            slot_utc = slot - zone
            true_duty = slot_utc + TAXI - (dep_utc - 60)
            true_notice = slot_utc - decision_utc
            crew = pilot.check_crew_duty(scenario, pkg(slot))
            assert bool(crew) == (true_duty > LIMIT), (row.flight_id, slot)
            if crew:
                assert crew[0].observed == true_duty
            gate = ground.check_gate_notice(scenario, pkg(slot))
            assert bool(gate) == (true_notice < NOTICE), (row.flight_id, slot)
            if gate:
                assert gate[0].observed == true_notice
            checked += 1
    assert checked >= 6


@pytest.mark.parametrize(
    ("name", "dep", "arr", "block", "dep_dest", "duty_slot", "notice_slot"),
    CASES,
    ids=[c[0] for c in CASES],
)
def test_the_harm_check_agrees_at_the_true_limit(
    base_row: dot.DotRow,
    csv_file: Path,
    name: str,
    dep: int,
    arr: int,
    block: int,
    dep_dest: int,
    duty_slot: int,
    notice_slot: int,
) -> None:
    """harm.py cannot see the origin clock (the scenario holds only destination
    times), so it cannot catch a mixed clock on its own. This holds its verdict
    to the true UTC limit on rows that cross zones in both directions."""
    scenario = scenario_for(make_row(base_row, dep, arr, block), csv_file)
    at = inspect_package(scenario, pkg(duty_slot))
    past = inspect_package(scenario, pkg(duty_slot + 1))
    assert at.verdict_of(HarmCheck.CREW_DUTY) is HarmVerdict.CLEAR
    assert past.verdict_of(HarmCheck.CREW_DUTY) is HarmVerdict.HARM
    assert (
        inspect_package(scenario, pkg(notice_slot)).verdict_of(HarmCheck.GATE_NOTICE)
        is HarmVerdict.CLEAR
    )
    assert (
        inspect_package(scenario, pkg(notice_slot - 1)).verdict_of(
            HarmCheck.GATE_NOTICE
        )
        is HarmVerdict.HARM
    )
