"""Scenario building: provenance, determinism, no hindsight and a usable mix."""

import shutil
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.negotiation import dot
from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    ArrivalSlot,
    Deal,
    DecisionPoint,
    FlightPlanAction,
    NoDeal,
    Package,
    Provenance,
    Scenario,
    WakeCategory,
)
from app.negotiation.dot import DotRow
from app.negotiation.fallback import decide
from app.negotiation.rules import ground
from app.negotiation.scenario import (
    FIELD_NOTES,
    AsFlownOutcome,
    EarliestBasis,
    GeneratorParams,
    build_scenario,
    earliest_basis,
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


def test_weather_earliest_is_schedule_plus_the_floor(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    weather = build(rows["DL401"], csv_file)
    # Crosses midnight: 06:50 the next day is minute 1850, plus a floor of 15.
    assert weather.earliest_arrival_min.value == 1850 + 15
    # An inbound leg exists (DL400, 90 min late) but weather rows ignore it.
    basis = earliest_basis(rows["DL401"], csv_file)
    assert basis.basis == "disruption_floor"
    assert basis.usable_inbound is False
    # The row's own real arrival delay (71 min) is nowhere in the window.
    assert rows["DL401"].arrival_delay == 71


def test_late_aircraft_earliest_follows_the_inbound_legs_lateness(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    scenario = build(rows["NK301"], csv_file)
    # NK300 was due 05:55 and landed 75 min late. NK301 leaves 07:00, so 65 min
    # were scheduled; 40 of those are above the 25 min narrow-body minimum and
    # absorb lateness. 75 - 40 = 35 carries over, which beats the floor of 20.
    assert scenario.earliest_arrival_min.value == 8 * 60 + 30 + 35
    assert scenario.latest_arrival_min.value == 8 * 60 + 30 + 35 + 60
    basis = earliest_basis(rows["NK301"], csv_file)
    assert basis == EarliestBasis(
        basis="inbound_leg",
        delay_min=35,
        floor_min=20,
        usable_inbound=True,
        inbound_flight_id="NK300",
        inbound_lateness_min=75,
        recovery_allowance_min=40,
    )
    assert scenario.earliest_arrival_min.provenance is DERIVED
    # The row's own real arrival delay (70 min) is not what set it.
    assert rows["NK301"].arrival_delay == 70


def test_an_inbound_leg_that_lands_too_late_to_be_known_gives_the_floor(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    # AS805 lands 200 min late, at 12:35, long after AS804 leaves at 10:15.
    basis = earliest_basis(rows["AS804"], csv_file)
    assert basis.basis == "disruption_floor"
    assert basis.usable_inbound is False
    assert basis.delay_min == 20
    sched = dot.scheduled_arrival_min(rows["AS804"])
    assert build(rows["AS804"], csv_file).earliest_arrival_min.value == sched + 20


def test_no_inbound_leg_or_one_elsewhere_gives_the_floor(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    # EV901 has no earlier leg for its tail at all.
    assert earliest_basis(rows["EV901"], csv_file).usable_inbound is False
    # An inbound that landed somewhere other than this origin is not an inbound.
    elsewhere = replace(rows["NK301"], origin_airport="JFK")
    assert earliest_basis(elsewhere, csv_file).usable_inbound is False


def edited_csv(
    tmp_path: Path, name: str, edit: Callable[[dict[str, str]], None]
) -> Path:
    """A copy of the fixture with `edit` applied to each row's cells."""
    folder = tmp_path / name
    folder.mkdir()
    lines = FIXTURE.read_text().splitlines()
    header = lines[0].split(",")
    out = [lines[0]]
    for line in lines[1:]:
        cells = dict(zip(header, line.split(","), strict=True))
        edit(cells)
        out.append(",".join(cells[column] for column in header))
    target = folder / "flights.csv"
    target.write_text("\n".join(out) + "\n")
    return target


def row_in(path: Path, flight_id: str) -> DotRow:
    return next(r for r in dot.iter_eligible_rows(path) if r.flight_id == flight_id)


def set_inbound_delay(delay: str) -> Callable[[dict[str, str]], None]:
    def edit(cells: dict[str, str]) -> None:
        if cells["AIRLINE"] + cells["FLIGHT_NUMBER"] == "NK300":
            cells["ARRIVAL_DELAY"] = delay

    return edit


def test_changing_the_inbound_legs_lateness_changes_the_scenario(
    csv_file: Path, tmp_path: Path
) -> None:
    base = build_scenario(row_in(csv_file, "NK301"), 2, csv_file)
    later = edited_csv(tmp_path, "later", set_inbound_delay("95"))
    worse = build_scenario(row_in(later, "NK301"), 2, later)
    # 95 - 40 = 55 min carried: the earliest arrival moves 20 min later.
    assert worse.earliest_arrival_min.value == 510 + 55
    assert worse.model_dump_json() != base.model_dump_json()
    # And lateness the schedule can absorb falls back to the floor.
    early = edited_csv(tmp_path, "early", set_inbound_delay("30"))
    mild = build_scenario(row_in(early, "NK301"), 2, early)
    assert mild.earliest_arrival_min.value == 510 + 20
    basis = earliest_basis(row_in(early, "NK301"), early)
    assert basis.basis == "disruption_floor"
    assert basis.usable_inbound is True


def test_the_knowable_margin_is_exact(csv_file: Path, tmp_path: Path) -> None:
    """NK300 lands at 05:55 plus its delay; NK301 leaves 07:00; the margin is 30."""
    at_limit = edited_csv(tmp_path, "at", set_inbound_delay("95"))  # lands 07:30
    over = edited_csv(tmp_path, "over", set_inbound_delay("96"))  # lands 07:31
    assert earliest_basis(row_in(at_limit, "NK301"), at_limit).usable_inbound is True
    assert earliest_basis(row_in(over, "NK301"), over).usable_inbound is False


def test_other_flights_outcomes_do_not_change_the_scenario(
    rows: dict[str, DotRow], csv_file: Path, tmp_path: Path
) -> None:
    """Only the inbound leg's arrival delay may matter. Traffic, the next leg
    and every other flight's outcomes are not hindsight either."""
    inbound = {"NK300", "AS805", "DL400"}
    overwrite = {
        "DEPARTURE_TIME": "0001",
        "DEPARTURE_DELAY": "999",
        "WHEELS_OFF": "0002",
        "WHEELS_ON": "0003",
        "ARRIVAL_TIME": "0004",
        "AIR_TIME": "5",
        "ELAPSED_TIME": "6",
    }

    def edit(cells: dict[str, str]) -> None:
        cells.update(overwrite)
        if cells["AIRLINE"] + cells["FLIGHT_NUMBER"] not in inbound:
            cells["ARRIVAL_DELAY"] = "888"

    changed_file = edited_csv(tmp_path, "changed", edit)
    changed_rows = {r.flight_id: r for r in dot.iter_eligible_rows(changed_file)}
    assert set(changed_rows) == set(rows)
    for flight_id, row in rows.items():
        assert changed_rows[flight_id].arrival_delay == 888
        before = build_scenario(row, 5, csv_file).model_dump_json()
        after = build_scenario(
            changed_rows[flight_id], 5, changed_file
        ).model_dump_json()
        assert after == before


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
    ids = [a.flight_id for a in arrivals]
    assert len(ids) == len(set(ids))  # unique within the scenario
    assert "NK301" not in ids  # the subject never appears, nor under its own ID
    by_id = {a.flight_id.split("-")[0]: a for a in arrivals}
    # A same-numbered flight from another origin is a different flight.
    assert any(i.startswith("NK301-CLE-") for i in ids)
    # One flight number twice from different origins stays two arrivals.
    assert {"UA1013-DEN-0640", "UA1013-SLC-0650"} <= set(ids)
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


def test_generated_values_are_always_usable_by_the_rules(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    """Positive burn and fuel, a known runway per arrival and a known gate per
    occupancy, and never the scenario's own flight among the others."""
    variants = [*rows.values(), replace(rows["NK301"], scheduled_time=0)]
    for row in variants:
        for seed in range(30):
            s = build(row, csv_file, seed)
            for field in (
                s.fuel_on_board_kg,
                s.trip_fuel_kg,
                s.cruise_burn_kg_per_min,
                s.hold_burn_kg_per_min,
                s.alternate_fuel_kg,
            ):
                assert field.value is not None and field.value > 0
            runways, gates = s.runways.value, s.gates.value
            assert runways is not None and gates is not None
            assert all(
                a.runway_id in {r.runway_id for r in runways}
                for a in s.other_arrivals.value or ()
            )
            assert all(
                o.gate_id in {g.gate_id for g in gates}
                for o in s.gate_occupancies.value or ()
            )
            own = row.flight_id
            assert own not in {a.flight_id for a in s.other_arrivals.value or ()}
            assert own not in {o.flight_id for o in s.gate_occupancies.value or ()}


def test_runway_parallel_groups_are_synthetic_pairs(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    four = GeneratorParams(runway_tiers=((100_000, 4),), p_close_parallel_pair=1.0)
    runways = build_scenario(rows["NK301"], 1, csv_file, four).runways
    assert runways.provenance is SYNTHETIC
    assert runways.value is not None
    assert [r.parallel_group for r in runways.value] == ["PG1", "PG1", "PG2", "PG2"]

    none = GeneratorParams(runway_tiers=((100_000, 4),), p_close_parallel_pair=0.0)
    ungrouped = build_scenario(rows["NK301"], 1, csv_file, none).runways.value
    assert ungrouped is not None
    assert all(r.parallel_group is None for r in ungrouped)

    # An odd runway out stays independent, and one runway is never grouped.
    three = GeneratorParams(runway_tiers=((100_000, 3),), p_close_parallel_pair=1.0)
    odd = build_scenario(rows["NK301"], 1, csv_file, three).runways.value
    assert odd is not None
    assert [r.parallel_group for r in odd] == ["PG1", "PG1", None]
    single = build_scenario(rows["NK301"], 1, csv_file).runways.value
    assert single is not None and len(single) == 1
    assert single[0].parallel_group is None
    assert "parallel_group" in FIELD_NOTES["runways"]


def test_parallel_groups_are_seeded_and_mixed_by_default(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    big = GeneratorParams(runway_tiers=((100_000, 4),))
    seen = {
        tuple(
            r.parallel_group
            for r in build_scenario(rows["NK301"], seed, csv_file, big).runways.value
            or ()
        )
        for seed in range(40)
    }
    assert len(seen) > 1  # some seeds group, some do not
    again = build_scenario(rows["NK301"], 3, csv_file, big).model_dump_json()
    assert build_scenario(rows["NK301"], 3, csv_file, big).model_dump_json() == again


def test_the_planned_gate_is_free_for_the_imposed_stay_at_the_scheduled_time(
    rows: dict[str, DotRow], csv_file: Path
) -> None:
    """A deliberate modelling choice: the plan was legal before the disruption."""
    busy_somewhere = False
    for row in rows.values():
        for seed in range(40):
            s = build(row, csv_file, seed)
            if s.taxi_in_min.value is None:
                continue  # the rule fails closed; nothing to check
            planned = s.planned_gate.value
            assert planned is not None
            package = Package(
                slot=ArrivalSlot(
                    runway_id="R1", time_min=dot.scheduled_arrival_min(row)
                ),
                gate_id=planned,
                action=FlightPlanAction.DIRECT,
            )
            assert ground.check_gate_overlap(s, package) == (), (row.flight_id, seed)
            busy_somewhere |= any(
                o.gate_id != planned for o in s.gate_occupancies.value or ()
            )
    assert busy_somewhere  # other gates are occupied, so the check is not vacuous
    assert "legal at schedule" in FIELD_NOTES["planned_gate"]


def test_the_worst_case_scenario_stays_inside_the_package_bound() -> None:
    p = GeneratorParams()
    step = rv.rule_value(rv.SLOT_STEP_MIN).value
    slots = p.plan_window_min // step
    # Airborne: DIRECT at zero delay, then hold and vector at every later slot.
    per_cell = 1 + 2 * slots
    assert (
        per_cell * p.max_runways * p.max_gates <= rv.rule_value(rv.MAX_PACKAGES).value
    )


def test_the_hard_turnaround_note_states_both_provenances_the_field_gets() -> None:
    note = FIELD_NOTES["next_leg_turnaround_hard"]
    assert "synthetic" in note and "derived" in note
    assert "when a next leg exists" in note and "none does" in note
