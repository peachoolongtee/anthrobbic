"""Scenario building: provenance, determinism, no hindsight and a usable mix."""

import shutil
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.negotiation import dot
from app.negotiation.contracts import (
    Deal,
    DecisionPoint,
    NoDeal,
    Provenance,
    Scenario,
    WakeCategory,
)
from app.negotiation.dot import DotRow
from app.negotiation.fallback import decide
from app.negotiation.scenario import (
    FIELD_NOTES,
    AsFlownOutcome,
    build_scenario,
    next_leg_of,
    outcome_of,
)

FIXTURE = Path(__file__).parent / "fixtures" / "flights_sample.csv"
REAL_CSV = dot.csv_path(None)

REAL = Provenance.REAL
DERIVED = Provenance.DERIVED
SYNTHETIC = Provenance.SYNTHETIC

EXPECTED_PROVENANCE = {
    "scenario_id": DERIVED,
    "flight_id": REAL,
    "decision_point": DERIVED,
    "flight_rules": SYNTHETIC,
    "wake_category": SYNTHETIC,
    "aircraft_size": SYNTHETIC,
    "earliest_arrival_min": DERIVED,
    "latest_arrival_min": DERIVED,
    "taxi_in_min": DERIVED,
    "fuel_on_board_kg": SYNTHETIC,
    "trip_fuel_kg": SYNTHETIC,
    "cruise_burn_kg_per_min": SYNTHETIC,
    "hold_burn_kg_per_min": SYNTHETIC,
    "alternate_fuel_kg": SYNTHETIC,
    "destination_forecast": SYNTHETIC,
    "runways": SYNTHETIC,
    "taxiways": SYNTHETIC,
    "gates": SYNTHETIC,
    "other_arrivals": SYNTHETIC,  # real flights, synthetic wake and runway
    "gate_occupancies": SYNTHETIC,
    "planned_gate": SYNTHETIC,
    "next_departure_min": DERIVED,
    "next_leg_turnaround_hard": SYNTHETIC,
    "ground_shift_end_min": SYNTHETIC,
    "connections": SYNTHETIC,
}


@pytest.fixture
def csv_file(tmp_path: Path) -> Iterator[Path]:
    target = tmp_path / "flights.csv"
    shutil.copy(FIXTURE, target)
    yield target
    dot.clear_connections()


@pytest.fixture
def rows(csv_file: Path) -> dict[str, DotRow]:
    return {r.flight_id: r for r in dot.iter_eligible_rows(csv_file)}


def build(row: DotRow, csv_file: Path, seed: int = 0) -> Scenario:
    return build_scenario(row, seed, csv_file)


def test_every_eligible_fixture_row_builds_a_valid_scenario(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    assert len(rows) == 6
    for row in rows.values():
        for seed in range(3):
            scenario = build(row, csv_file, seed)
            # Round trip through JSON proves the model is valid and complete.
            assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_the_fallback_decides_every_fixture_scenario(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    for row in rows.values():
        for seed in range(5):
            assert isinstance(decide(build(row, csv_file, seed)), Deal | NoDeal)


def test_provenance_labels_are_exact_and_documented(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    scenario = build(rows["NK301"], csv_file)
    labels = {
        name: getattr(scenario, name).provenance for name in Scenario.model_fields
    }
    assert labels == EXPECTED_PROVENANCE
    assert set(FIELD_NOTES) == set(Scenario.model_fields)
    assert scenario.flight_id.value == "NK301"


def test_a_missing_next_leg_is_derived_unknown_and_not_hard(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    scenario = build(rows["EV901"], csv_file)
    assert scenario.next_departure_min.value is None
    assert scenario.next_departure_min.provenance is DERIVED
    assert scenario.next_leg_turnaround_hard.value is False
    assert scenario.next_leg_turnaround_hard.provenance is DERIVED


def test_same_row_and_seed_give_identical_bytes(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    for row in rows.values():
        first = build(row, csv_file, 4).model_dump_json()
        assert build(row, csv_file, 4).model_dump_json() == first


def test_a_new_seed_changes_synthetic_fields_but_never_real_or_derived(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    row = rows["NK301"]
    one = build(row, csv_file, 1)
    two = build(row, csv_file, 2)
    assert one != two
    for name, provenance in EXPECTED_PROVENANCE.items():
        if name == "scenario_id":
            continue  # carries the seed
        if provenance is not SYNTHETIC:
            assert getattr(one, name) == getattr(two, name), name
    assert any(
        getattr(one, name) != getattr(two, name)
        for name, p in EXPECTED_PROVENANCE.items()
        if p is SYNTHETIC
    )


def test_decision_point_follows_the_cause(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    assert build(rows["NK301"], csv_file).decision_point.value is (
        DecisionPoint.PRE_DEPARTURE
    )
    assert build(rows["DL401"], csv_file).decision_point.value is (
        DecisionPoint.AIRBORNE
    )
    # Over both thresholds counts as weather.
    assert build(rows["F9951"], csv_file).decision_point.value is (
        DecisionPoint.AIRBORNE
    )


def test_earliest_arrival_is_schedule_plus_a_floor_not_the_outcome(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    late = build(rows["NK301"], csv_file)
    assert late.earliest_arrival_min.value == 8 * 60 + 30 + 20
    assert late.latest_arrival_min.value == 8 * 60 + 30 + 20 + 60
    weather = build(rows["DL401"], csv_file)
    # Crosses midnight: 06:50 the next day is minute 1850, plus a floor of 15.
    assert weather.earliest_arrival_min.value == 1850 + 15
    # The row's real arrival delay (70 and 71 min) is nowhere in the window.
    assert rows["NK301"].arrival_delay == 70
    assert rows["DL401"].arrival_delay == 71


def test_next_departure_comes_from_the_tails_next_leg(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    scenario = build(rows["NK301"], csv_file)
    assert scenario.next_departure_min.value == 10 * 60 + 30
    leg = next_leg_of(rows["NK301"], csv_file)
    assert leg is not None
    assert leg.flight_id == "NK302"


def test_other_arrivals_are_real_scheduled_flights_with_labelled_synthetic_parts(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    scenario = build(rows["NK301"], csv_file)
    arrivals = scenario.other_arrivals.value
    assert arrivals is not None
    by_id = {a.flight_id: a for a in arrivals}
    assert "NK301" not in by_id
    assert by_id["DL1003"].time_min == 510  # scheduled, not the 10:10 flown
    assert by_id["WN1005"].time_min == 540
    assert "DL1010" not in by_id and "AA1011" not in by_id
    runways = scenario.runways.value
    assert runways is not None
    open_ids = {r.runway_id for r in runways if not r.closed}
    assert {a.runway_id for a in arrivals} <= open_ids
    assert all(isinstance(a.wake_category, WakeCategory) for a in arrivals)
    assert scenario.other_arrivals.provenance is SYNTHETIC
    assert "wake category" in FIELD_NOTES["other_arrivals"]


def test_synthetic_airport_state_is_internally_coherent(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    for row in rows.values():
        for seed in range(20):
            s = build(row, csv_file, seed)
            runways, taxiways, gates = s.runways.value, s.taxiways.value, s.gates.value
            assert runways and taxiways and gates
            assert any(not r.closed for r in runways)
            assert any(not t.closed for t in taxiways)
            size = s.aircraft_size.value
            assert size is not None
            assert sum(g.max_size >= size for g in gates) >= 2
            assert s.planned_gate.value in {g.gate_id for g in gates}
            assert {g.taxiway_id for g in gates} <= {t.taxiway_id for t in taxiways}
            assert s.trip_fuel_kg.value
            assert s.fuel_on_board_kg.value
            assert s.fuel_on_board_kg.value > s.trip_fuel_kg.value


def test_a_row_with_blank_columns_still_builds(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    row = rows["EV901"]
    assert row.scheduled_time is None and row.distance is None
    scenario = build(row, csv_file)
    assert scenario.taxi_in_min.value is not None
    assert scenario.trip_fuel_kg.value is not None
    # An airport with too few flights to say gives an unknown, not an invented value.
    unknown_airport = replace(rows["NK301"], destination_airport="ZZZ")
    assert build(unknown_airport, csv_file).taxi_in_min.value is None


OUTCOME_CHANGES = {
    "departure_time": 1,
    "departure_delay": 999,
    "wheels_off": 1,
    "air_time": 1,
    "elapsed_time": 1,
    "wheels_on": 2,
    "taxi_in": 77,
    "arrival_time": 3,
    "arrival_delay": 888,
    "air_system_delay": 111,
    "security_delay": 112,
    "airline_delay": 113,
}


def test_outcome_columns_do_not_change_the_scenario(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    for row in rows.values():
        base = build(row, csv_file, 3).model_dump_json()
        changed = replace(row, **OUTCOME_CHANGES)
        # The delay amounts move but stay on the same side of their threshold.
        if row.weather_delay is not None:
            changed = replace(changed, weather_delay=row.weather_delay + 50)
        if row.late_aircraft_delay is not None:
            changed = replace(changed, late_aircraft_delay=row.late_aircraft_delay + 50)
        assert changed != row
        assert build(changed, csv_file, 3).model_dump_json() == base


def test_outcome_columns_in_the_file_do_not_change_the_scenario(
    rows: dict[str, DotRow], csv_file: Path, tmp_path: Path
) -> None:
    """Other flights' outcomes (traffic, next leg) are not hindsight either."""
    changed_dir = tmp_path / "changed"
    changed_dir.mkdir()
    changed_file = changed_dir / "flights.csv"
    lines = FIXTURE.read_text().splitlines()
    header = lines[0].split(",")
    overwrite = {
        "DEPARTURE_TIME": "0001",
        "DEPARTURE_DELAY": "999",
        "WHEELS_OFF": "0002",
        "WHEELS_ON": "0003",
        "ARRIVAL_TIME": "0004",
        "ARRIVAL_DELAY": "888",
        "AIR_TIME": "5",
        "ELAPSED_TIME": "6",
    }
    out = [lines[0]]
    for line in lines[1:]:
        cells = line.split(",")
        for column, value in overwrite.items():
            cells[header.index(column)] = value
        out.append(",".join(cells))
    changed_file.write_text("\n".join(out) + "\n")
    changed_rows = {r.flight_id: r for r in dot.iter_eligible_rows(changed_file)}
    assert set(changed_rows) == set(rows)
    for flight_id, row in rows.items():
        assert changed_rows[flight_id].arrival_delay == 888
        before = build_scenario(row, 5, csv_file).model_dump_json()
        after = build_scenario(
            changed_rows[flight_id], 5, changed_file
        ).model_dump_json()
        assert after == before


def test_outcome_is_kept_apart_and_holds_the_as_flown_values(
    rows: dict[str, DotRow],
) -> None:
    outcome = outcome_of(rows["NK301"])
    assert isinstance(outcome, AsFlownOutcome)
    assert outcome.arrival_delay == 70
    assert outcome.arrival_time == 940
    assert outcome.wheels_on == 928
    assert outcome.taxi_in == 12
    assert outcome.late_aircraft_delay == 45
    assert outcome.airline_delay == 25
    assert outcome.arrival_min == 8 * 60 + 30 + 70
    # A blank arrival delay gives no as-flown arrival rather than a guess.
    assert outcome_of(rows["EV901"]).arrival_min is None


def test_outcome_fields_are_not_scenario_fields() -> None:
    forbidden = {
        "arrival_time",
        "arrival_delay",
        "wheels_on",
        "wheels_off",
        "departure_time",
        "air_time",
        "elapsed_time",
        "weather_delay",
        "late_aircraft_delay",
    }
    assert forbidden.isdisjoint(Scenario.model_fields)


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real flights.csv is not present")
def test_real_rows_build_deterministic_scenarios_with_a_real_mix() -> None:
    rows = dot.sample_rows(60, seed=21)
    results: list[str] = []
    for row in rows:
        scenario = build_scenario(row, 1)
        again = build_scenario(row, 1)
        assert scenario.model_dump_json() == again.model_dump_json()
        assert scenario.taxi_in_min.value is not None
        assert scenario.earliest_arrival_min.value is not None
        assert scenario.earliest_arrival_min.value > dot.scheduled_arrival_min(row)
        decision = decide(scenario)
        results.append(decision.kind)
    # Neither trivially legal nor impossible across the sample.
    assert 0 < results.count("NO_DEAL") < len(results)
    assert 0 < results.count("DEAL") < len(results)
