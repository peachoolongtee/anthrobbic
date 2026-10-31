"""DOT row loading: eligibility, exclusions, sampling, the cache and schedule joins."""

import shutil
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.negotiation import dot
from app.negotiation.dot import DotError, DotRow

FIXTURE = Path(__file__).parent / "fixtures" / "flights_sample.csv"
REAL_CSV = dot.csv_path(None)

# Eligible rows in the fixture, by flight ID.
ELIGIBLE = {"NK301", "DL401", "EV901", "AS803", "AS804", "F9951"}
WEATHER = {"DL401", "EV901", "AS803", "F9951"}
LATE = {"NK301", "AS804"}


@pytest.fixture
def csv_file(tmp_path: Path) -> Iterator[Path]:
    """A private copy, so its cache is built under tmp_path and not the repo."""
    target = tmp_path / "flights.csv"
    shutil.copy(FIXTURE, target)
    yield target
    dot.clear_connections()


def by_flight(path: Path) -> dict[str, DotRow]:
    return {row.flight_id: row for row in dot.iter_eligible_rows(path)}


def test_eligibility_filters_rows_as_the_brief_states(csv_file: Path) -> None:
    rows = by_flight(csv_file)
    assert set(rows) == ELIGIBLE
    # Boundaries: weather 15 and late-aircraft 20 are not over the threshold.
    assert "AS801" not in rows
    assert "AS802" not in rows
    assert "AS803" in rows  # weather 16
    assert "AS804" in rows  # late-aircraft 21
    # An ordinary delay with no cause, and rows with no delay at all.
    assert "WN960" not in rows
    assert "AA1001" not in rows


def test_october_rows_are_excluded_everywhere(csv_file: Path) -> None:
    assert "AA601" not in by_flight(csv_file)
    con = dot.ensure_cache(csv_file)
    airports = {r[0] for r in con.execute("SELECT origin FROM flights")}
    assert "10397" not in airports
    assert all(row.month != 10 for row in dot.iter_eligible_rows(csv_file))


def test_rows_without_a_tail_are_not_eligible(csv_file: Path) -> None:
    assert "UA501" not in by_flight(csv_file)
    assert all(row.tail_number for row in dot.iter_eligible_rows(csv_file))


def test_cancelled_rows_are_not_eligible(csv_file: Path) -> None:
    rows = by_flight(csv_file)
    assert "WN701" not in rows
    assert not any(row.cancelled for row in rows.values())


def test_is_eligible_predicate_applies_the_same_rules(csv_file: Path) -> None:
    row = by_flight(csv_file)["AS803"]  # weather 16, no late-aircraft delay
    assert dot.is_eligible(row)
    assert not dot.is_eligible(replace(row, weather_delay=15))
    assert not dot.is_eligible(replace(row, weather_delay=None))
    assert dot.is_eligible(replace(row, weather_delay=None, late_aircraft_delay=21))
    assert not dot.is_eligible(replace(row, late_aircraft_delay=20, weather_delay=0))
    assert not dot.is_eligible(replace(row, month=10))
    assert not dot.is_eligible(replace(row, tail_number=""))


def test_cause_splits_weather_from_late_aircraft(csv_file: Path) -> None:
    rows = by_flight(csv_file)
    assert {f for f, r in rows.items() if r.cause == "weather"} == WEATHER
    assert {f for f, r in rows.items() if r.cause == "late_aircraft"} == LATE
    # Over both thresholds counts as weather.
    both = rows["F9951"]
    assert both.weather_delay == 30
    assert both.late_aircraft_delay == 40
    assert both.cause == "weather"


def test_midnight_crossing_arrival_is_above_1440(csv_file: Path) -> None:
    row = by_flight(csv_file)["DL401"]
    # Departs 22:50 Los Angeles, 5 h block, lands 06:50 New York next morning.
    assert row.scheduled_departure == 2250
    assert row.scheduled_arrival == 650
    assert dot.scheduled_arrival_min(row) == 24 * 60 + 6 * 60 + 50


def test_scheduled_arrival_without_a_block_time_still_orders_after_departure() -> None:
    assert dot.scheduled_arrival_rel(2350, 20, None) == 24 * 60 + 20
    assert dot.scheduled_arrival_rel(600, 700, None) == 7 * 60
    assert dot.hhmm_to_min(2400) == 1440


def test_blank_columns_are_none_and_the_row_still_loads(csv_file: Path) -> None:
    row = by_flight(csv_file)["EV901"]
    assert row.scheduled_time is None
    assert row.distance is None
    assert row.arrival_delay is None
    assert row.arrival_time is None
    assert row.weather_delay == 25
    assert row.late_aircraft_delay is None


def test_source_row_points_back_at_the_csv(csv_file: Path) -> None:
    lines = csv_file.read_text().splitlines()
    for row in dot.iter_eligible_rows(csv_file):
        fields = lines[row.source_row].split(",")  # header is line 0
        assert fields[4] + fields[5] == row.flight_id


def test_sample_is_deterministic_and_seed_dependent(csv_file: Path) -> None:
    first = dot.sample_rows(4, seed=7, path=csv_file)
    again = dot.sample_rows(4, seed=7, path=csv_file)
    assert first == again
    assert {r.flight_id for r in first} <= ELIGIBLE
    orders = {
        tuple(r.flight_id for r in dot.sample_rows(4, seed=s, path=csv_file))
        for s in range(8)
    }
    assert len(orders) > 1


def test_stratified_sample_is_half_and_half(csv_file: Path) -> None:
    rows = dot.sample_rows(4, seed=1, path=csv_file)
    assert len(rows) == 4
    assert sum(r.cause == "weather" for r in rows) == 2
    assert sum(r.cause == "late_aircraft" for r in rows) == 2
    odd = dot.sample_rows(3, seed=1, path=csv_file)
    assert sum(r.cause == "weather" for r in odd) == 1
    assert sum(r.cause == "late_aircraft" for r in odd) == 2  # the extra row


def test_sample_by_cause_and_short_strata(csv_file: Path) -> None:
    weather = dot.sample_rows(3, seed=1, cause="weather", path=csv_file)
    assert len(weather) == 3
    assert all(r.cause == "weather" for r in weather)
    late = dot.sample_rows(10, seed=1, cause="late_aircraft", path=csv_file)
    assert {r.flight_id for r in late} == LATE  # only two exist
    assert dot.sample_rows(0, seed=1, path=csv_file) == []


def test_sample_rejects_bad_arguments(csv_file: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        dot.sample_rows(-1, seed=1, path=csv_file)
    with pytest.raises(ValueError, match="unknown cause"):
        dot.sample_rows(1, seed=1, cause="fog", path=csv_file)  # type: ignore[arg-type]


def test_cache_is_written_beside_the_csv_and_reused(csv_file: Path) -> None:
    cache = dot.cache_path(csv_file)
    assert not cache.exists()
    dot.sample_rows(2, seed=1, path=csv_file)
    assert cache.parent == csv_file.parent / ".cache"
    assert cache.exists()
    # The cache directory ignores itself, wherever the CSV lives.
    assert (cache.parent / ".gitignore").read_text().strip() == "*"
    stamp = cache.stat().st_mtime_ns
    dot.clear_connections()
    dot.sample_rows(2, seed=2, path=csv_file)
    assert cache.stat().st_mtime_ns == stamp


def test_cache_follows_the_csv_when_it_changes(csv_file: Path) -> None:
    before = dot.cache_path(csv_file)
    assert len(list(dot.iter_eligible_rows(csv_file))) == len(ELIGIBLE)
    dot.clear_connections()
    with csv_file.open("a") as handle:
        handle.write(
            "2015,3,5,4,NK,990,N990NK,BOS,ORD,0700,,,,,150,,,867,,,0830,,70,0,0,,,,,45,\n"
        )
    assert dot.cache_path(csv_file) != before
    assert len(list(dot.iter_eligible_rows(csv_file))) == len(ELIGIBLE) + 1


def test_missing_csv_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(DotError, match="not found"):
        dot.sample_rows(1, seed=1, path=tmp_path / "absent.csv")


def test_csv_without_the_expected_columns_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("YEAR,MONTH\n2015,1\n")
    with pytest.raises(DotError, match="lacks columns"):
        dot.ensure_cache(bad)
    assert not any((tmp_path / ".cache").glob("*.sqlite"))  # no half-built cache
    assert not any((tmp_path / ".cache").glob("*.tmp"))


def test_env_variable_selects_the_csv(
    csv_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(dot.ENV_CSV, str(csv_file))
    assert dot.csv_path(None) == csv_file
    assert {r.flight_id for r in dot.iter_eligible_rows()} == ELIGIBLE
    monkeypatch.delenv(dot.ENV_CSV)
    assert dot.csv_path(None) == dot.DEFAULT_CSV


def test_next_leg_is_the_same_tails_next_departure_that_day(csv_file: Path) -> None:
    rows = by_flight(csv_file)
    leg = dot.next_leg(rows["NK301"], csv_file)
    assert leg is not None
    assert leg.flight_id == "NK302"  # not NK303, which leaves later
    assert leg.scheduled_departure_min == 10 * 60 + 30
    assert leg.destination == "DEN"
    assert leg.departure_delay_min == 55


def test_next_leg_ignores_the_next_day_and_other_tails(csv_file: Path) -> None:
    rows = by_flight(csv_file)
    assert dot.next_leg(rows["DL401"], csv_file) is None  # DL402 is on day 6
    assert dot.next_leg(rows["EV901"], csv_file) is None


def test_traffic_uses_scheduled_times_and_excludes_the_subject(csv_file: Path) -> None:
    subject = by_flight(csv_file)["NK301"]  # scheduled to land at 08:30 = 510
    found = {
        a.flight_id: a.arrival_min
        for a in dot.traffic_near(subject, 470, 650, csv_file)
    }
    assert "NK301" not in found
    assert found["DL1003"] == 510  # scheduled 08:30; actual was 10:10
    assert found["AA1004"] == 525  # scheduled 08:45; actual was 06:00
    assert found["WN1005"] == 540  # no tail number, still a scheduled arrival
    assert "DL1010" not in found  # 15:00, outside the window
    assert "AA1011" not in found  # 03:00, outside the window
    assert list(found.values()) == sorted(found.values())


def test_traffic_is_not_changed_by_actual_arrival_columns(
    csv_file: Path, tmp_path: Path
) -> None:
    subject = by_flight(csv_file)["NK301"]
    before = dot.traffic_near(subject, 0, 2000, csv_file)
    other = tmp_path / "other"
    other.mkdir()
    changed = other / "flights.csv"
    lines = FIXTURE.read_text().splitlines()
    header = lines[0].split(",")
    i_arr, i_delay = header.index("ARRIVAL_TIME"), header.index("ARRIVAL_DELAY")
    out = [lines[0]]
    for line in lines[1:]:
        cells = line.split(",")
        cells[i_arr], cells[i_delay] = "0001", "999"
        out.append(",".join(cells))
    changed.write_text("\n".join(out) + "\n")
    assert dot.traffic_near(subject, 0, 2000, changed) == before


def test_typical_taxi_in_is_the_airport_median(csv_file: Path) -> None:
    value = dot.typical_taxi_in("ORD", csv_file)
    assert value is not None
    assert 8 <= value <= 14
    assert dot.typical_taxi_in("ZZZ", csv_file) is None  # unknown airport
    assert dot.typical_taxi_in("DEN", csv_file) is None  # too few flights


def test_daily_arrivals_counts_the_destinations_day(csv_file: Path) -> None:
    subject = by_flight(csv_file)["NK301"]
    assert dot.daily_arrivals(subject, csv_file) >= 12


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real flights.csv is not present")
def test_real_csv_samples_are_eligible_and_fast_once_cached() -> None:
    """Exercises the real file. The first run may build the cache (minutes at most)."""
    rows = dot.sample_rows(200, seed=11)
    assert len(rows) == 200
    assert sum(r.cause == "weather" for r in rows) == 100
    for row in rows:
        assert dot.is_eligible(row)
        assert row.month != 10
        assert row.tail_number
        assert row.origin_airport.isalpha()
        assert len(row.destination_airport) == 3

    dot.clear_connections()
    start = time.perf_counter()
    again = dot.sample_rows(200, seed=11)
    elapsed = time.perf_counter() - start
    assert again == rows
    assert elapsed < 2.0, f"cached sample took {elapsed:.2f}s"

    con = dot.ensure_cache()
    total, weather = con.execute(
        "SELECT COUNT(*), SUM(cause = 'weather') FROM eligible"
    ).fetchone()
    # 376,125 eligible by the brief, less October's 17,351.
    assert total == 376_125 - 17_351
    assert 0.05 < weather / total < 0.2  # late-aircraft dominates, as the plan says
