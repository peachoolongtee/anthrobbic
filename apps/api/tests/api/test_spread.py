"""Delay spread: a hand-calculated chain, absorption, edges, no hindsight, speed.

The CSVs here are built per test so each chain is fully known. Turnarounds come
from the workbook: ORD and DEN 45 minutes, BOS and MDW 35.
"""

import csv
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.spread import NO_PLAN, delay_spread
from app.api.wire import DelaySpread
from app.negotiation import dot
from app.negotiation.dot import DotRow
from tests.api.test_routes import OUTCOME_FIELDS, _keys, _post_run, _scenarios

HEADER = (
    "YEAR,MONTH,DAY,DAY_OF_WEEK,AIRLINE,FLIGHT_NUMBER,TAIL_NUMBER,ORIGIN_AIRPORT,"
    "DESTINATION_AIRPORT,SCHEDULED_DEPARTURE,DEPARTURE_TIME,DEPARTURE_DELAY,TAXI_OUT,"
    "WHEELS_OFF,SCHEDULED_TIME,ELAPSED_TIME,AIR_TIME,DISTANCE,WHEELS_ON,TAXI_IN,"
    "SCHEDULED_ARRIVAL,ARRIVAL_TIME,ARRIVAL_DELAY,DIVERTED,CANCELLED,"
    "CANCELLATION_REASON,AIR_SYSTEM_DELAY,SECURITY_DELAY,AIRLINE_DELAY,"
    "LATE_AIRCRAFT_DELAY,WEATHER_DELAY"
).split(",")
REAL_CSV = dot.csv_path(None)


def flight(
    number: int,
    tail: str,
    origin: str,
    dest: str,
    dep: str,
    arr: str,
    *,
    day: int = 5,
    **outcome: Any,
) -> dict[str, Any]:
    """A row with schedule columns as given and as-flown columns that look sane."""
    row: dict[str, Any] = dict.fromkeys(HEADER, "")
    row.update(
        YEAR=2015,
        MONTH=3,
        DAY=day,
        DAY_OF_WEEK=4,
        AIRLINE="AA",
        FLIGHT_NUMBER=number,
        TAIL_NUMBER=tail,
        ORIGIN_AIRPORT=origin,
        DESTINATION_AIRPORT=dest,
        SCHEDULED_DEPARTURE=dep,
        SCHEDULED_ARRIVAL=arr,
        DEPARTURE_TIME=dep,
        DEPARTURE_DELAY=0,
        TAXI_OUT=10,
        WHEELS_OFF=dep,
        WHEELS_ON=arr,
        TAXI_IN=8,
        ARRIVAL_TIME=arr,
        ARRIVAL_DELAY=0,
        DIVERTED=0,
        CANCELLED=0,
        LATE_AIRCRAFT_DELAY=30,  # the subject rows must be eligible
    )
    row.update(outcome)
    return row


def write(path: Path, rows: list[dict[str, Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture(autouse=True)
def _close_connections() -> Iterator[None]:
    yield
    dot.clear_connections()


def subject(path: Path, flight_id: str) -> DotRow:
    return next(r for r in dot.iter_eligible_rows(path) if r.flight_id == flight_id)


def spread(path: Path, flight_id: str, plan_min: int | None) -> DelaySpread:
    return delay_spread(subject(path, flight_id), plan_min, path)


def knock_ons(result: DelaySpread) -> list[int | None]:
    return [
        leg.projection.knock_on_min if leg.projection else None for leg in result.legs
    ]


CHAIN = [
    flight(1, "N1", "BOS", "ORD", "0700", "0830"),  # arrives 08:30
    flight(2, "N1", "ORD", "DEN", "1000", "1130"),
    flight(3, "N1", "DEN", "ORD", "1215", "1500"),
    flight(4, "N1", "ORD", "MDW", "1630", "1715"),
    flight(5, "N2", "ORD", "DEN", "1000", "1130"),  # another aircraft
    flight(6, "N1", "ORD", "DEN", "0600", "0700", day=6),  # the next day
    flight(7, "N1", "MDW", "ORD", "0600", "0700"),  # departs before the subject lands
]


def test_hand_calculated_chain_carries_then_absorbs(tmp_path: Path) -> None:
    path = write(tmp_path / "flights.csv", CHAIN)
    # Plan lands at the gate 09:50 (590). Hand calculation, minutes after midnight:
    #  NK2: earliest 590 + 45 (ORD) = 635 vs 600 -> 35 late, arrives 690 + 35 = 725
    #  NK3: earliest 725 + 45 (DEN) = 770 vs 735 -> 35 late, arrives 900 + 35 = 935
    #  NK4: earliest 935 + 45 (ORD) = 980 vs 990 -> 0, a 10 minute gap absorbs it
    result = spread(path, "AA1", 590)
    assert [leg.flight_id for leg in result.legs] == ["AA2", "AA3", "AA4"]
    assert knock_ons(result) == [35, 35, 0]
    projections = [leg.projection for leg in result.legs]
    assert all(p is not None for p in projections)
    assert [p.earliest_departure for p in projections if p] == [
        "10:35",
        "12:50",
        "16:20",
    ]
    assert [p.projected_arrival for p in projections if p] == [
        "12:05",
        "15:35",
        "17:15",
    ]
    assert [p.turnaround_min for p in projections if p] == [45, 45, 45]
    assert result.plan_arrival == "09:50"
    assert result.scheduled_arrival == "08:30"
    assert result.tail_number == "N1"
    assert result.route == "BOS to ORD"
    first = result.legs[0]
    assert (first.scheduled_departure, first.scheduled_arrival) == ("10:00", "11:30")
    assert first.route == "ORD to DEN"


def test_labels_say_real_for_schedule_and_derived_for_computed(tmp_path: Path) -> None:
    result = spread(write(tmp_path / "f.csv", CHAIN), "AA1", 590)
    assert result.plan_arrival_provenance == "derived"
    for leg in result.legs:
        assert leg.provenance == "real"
        assert leg.projection is not None
        assert leg.projection.provenance == "derived"
        # The workbook's turnaround is synthetic and is labelled so.
        assert leg.projection.turnaround_provenance == "synthetic"
    assert "not what actually happened" in result.note


def test_a_chain_that_absorbs_the_delay_shows_no_knock_on(tmp_path: Path) -> None:
    path = write(tmp_path / "f.csv", CHAIN)
    # Gate at 09:00 (540): earliest NK2 departure 585 is before 600, and so on.
    result = spread(path, "AA1", 540)
    assert knock_ons(result) == [0, 0, 0]
    # Exactly on the line: 555 + 45 = 600 is the scheduled departure, not late.
    assert knock_ons(spread(path, "AA1", 555)) == [0, 0, 0]
    # One minute over is one minute late, and the next gap soaks it up.
    assert knock_ons(spread(path, "AA1", 556)) == [1, 1, 0]


def test_an_early_plan_never_gives_a_negative_knock_on(tmp_path: Path) -> None:
    result = spread(write(tmp_path / "f.csv", CHAIN), "AA1", 60)
    assert knock_ons(result) == [0, 0, 0]
    assert result.legs[0].projection is not None
    assert result.legs[0].projection.projected_arrival == "11:30"


def test_no_later_legs_gives_an_empty_chain(tmp_path: Path) -> None:
    path = write(tmp_path / "f.csv", [flight(1, "N1", "BOS", "ORD", "0700", "0830")])
    result = spread(path, "AA1", 590)
    assert result.legs == ()
    assert result.plan_arrival == "09:50"


def test_no_go_lists_the_chain_without_a_projection(tmp_path: Path) -> None:
    result = spread(write(tmp_path / "f.csv", CHAIN), "AA1", None)
    assert [leg.flight_id for leg in result.legs] == ["AA2", "AA3", "AA4"]
    assert result.plan_arrival is None
    assert result.plan_arrival_provenance is None
    for leg in result.legs:
        assert leg.projection is None
        assert leg.unprojected_reason == NO_PLAN
        assert leg.provenance == "real"


def test_an_unknown_airport_stops_the_projection_and_says_why(tmp_path: Path) -> None:
    path = write(
        tmp_path / "f.csv",
        [
            flight(1, "N1", "BOS", "ORD", "0700", "0830"),
            flight(2, "N1", "ORD", "ZZZ", "1000", "1130"),
            flight(3, "N1", "ZZZ", "ORD", "1215", "1500"),
            flight(4, "N1", "ORD", "DEN", "1630", "1900"),
        ],
    )
    result = spread(path, "AA1", 590)
    assert knock_ons(result) == [35, None, None]
    assert result.legs[1].unprojected_reason is not None
    assert "ZZZ" in result.legs[1].unprojected_reason
    # The leg after it cannot be carried either, and gets the same reason.
    assert result.legs[2].unprojected_reason == result.legs[1].unprojected_reason
    # The schedule values are still shown, still real.
    assert result.legs[1].route == "ZZZ to ORD"
    assert result.legs[1].provenance == "real"


def test_a_leg_that_leaves_from_elsewhere_is_not_carried(tmp_path: Path) -> None:
    path = write(
        tmp_path / "f.csv",
        [
            flight(1, "N1", "BOS", "ORD", "0700", "0830"),
            flight(2, "N1", "MDW", "DEN", "1000", "1130"),  # lands ORD, leaves MDW
            flight(3, "N1", "DEN", "ORD", "1300", "1530"),
        ],
    )
    result = spread(path, "AA1", 590)
    assert knock_ons(result) == [None, None]
    reason = result.legs[0].unprojected_reason
    assert reason is not None and "ORD" in reason and "MDW" in reason


def test_date_boundaries(tmp_path: Path) -> None:
    path = write(
        tmp_path / "f.csv",
        [
            flight(1, "N1", "BOS", "ORD", "2000", "2130"),
            flight(
                2, "N1", "ORD", "MDW", "2359", "0040"
            ),  # last minute, lands tomorrow
            flight(3, "N1", "MDW", "ORD", "0000", "0100", day=6),  # first minute after
            flight(4, "N3", "BOS", "ORD", "2300", "0100"),  # subject lands tomorrow
            flight(5, "N3", "ORD", "MDW", "2330", "0030"),  # before it lands: not later
            flight(6, "N3", "ORD", "DEN", "0500", "0800", day=6),
        ],
    )
    result = spread(path, "AA1", 21 * 60 + 50)  # 21:50 at the gate
    assert [leg.flight_id for leg in result.legs] == ["AA2"]
    leg = result.legs[0]
    # 21:50 + 45 = 22:35, long before 23:59, so nothing is carried.
    assert leg.projection is not None and leg.projection.knock_on_min == 0
    assert leg.scheduled_departure == "23:59"
    assert leg.scheduled_arrival == "00:40 next day"
    assert leg.projection.projected_arrival == "00:40 next day"

    # A late plan pushes a departure itself past midnight: 23:30 + 45 = 00:15.
    late = spread(path, "AA1", 23 * 60 + 30)
    assert late.legs[0].projection is not None
    assert late.legs[0].projection.earliest_departure == "00:15 next day"
    assert late.legs[0].projection.knock_on_min == 16

    # A subject that lands tomorrow has nothing left on its own date.
    assert spread(path, "AA4", 1500).legs == ()


def test_a_scheduled_arrival_at_midnight_is_the_next_day(tmp_path: Path) -> None:
    path = write(
        tmp_path / "f.csv",
        [
            flight(1, "N1", "SFO", "ORD", "1800", "0000", SCHEDULED_TIME=240),
            flight(2, "N1", "ORD", "JFK", "2300", "0200", SCHEDULED_TIME=180),
        ],
    )
    result = spread(path, "AA1", 1440 + 10)
    assert result.scheduled_arrival == "00:00 next day"
    assert result.legs == ()  # 23:00 departs before the 24:00 arrival


def test_flight_with_a_blank_tail_has_no_chain(tmp_path: Path) -> None:
    path = write(tmp_path / "f.csv", [flight(1, "N1", "BOS", "ORD", "0700", "0830")])
    row = subject(path, "AA1")
    assert dot.later_legs(replace(row, tail_number=""), path) == ()


def test_as_flown_columns_cannot_change_the_output(tmp_path: Path) -> None:
    """Every outcome column of every row is rewritten; the answer is identical."""
    as_scheduled = [
        flight(1, "N1", "BOS", "ORD", "0700", "0830"),
        flight(2, "N1", "ORD", "DEN", "1000", "1130"),
        flight(3, "N1", "DEN", "ORD", "1215", "1500"),
    ]
    scrambled = [
        flight(
            row["FLIGHT_NUMBER"],
            row["TAIL_NUMBER"],
            row["ORIGIN_AIRPORT"],
            row["DESTINATION_AIRPORT"],
            row["SCHEDULED_DEPARTURE"],
            row["SCHEDULED_ARRIVAL"],
            DEPARTURE_TIME="2301",
            DEPARTURE_DELAY=777,
            TAXI_OUT=99,
            WHEELS_OFF="2315",
            ELAPSED_TIME=999,
            AIR_TIME=888,
            WHEELS_ON="0005",
            TAXI_IN=77,
            ARRIVAL_TIME="0030",
            ARRIVAL_DELAY=888,
            DIVERTED=1,
            CANCELLED=1,
            CANCELLATION_REASON="B",
            AIR_SYSTEM_DELAY=11,
            SECURITY_DELAY=12,
            AIRLINE_DELAY=13,
            LATE_AIRCRAFT_DELAY=99,
            WEATHER_DELAY=14,
        )
        for row in as_scheduled
    ]
    plain = spread(write(tmp_path / "a.csv", as_scheduled), "AA1", 590)
    changed = spread(write(tmp_path / "b.csv", scrambled), "AA1", 590)
    assert plain == changed
    assert plain.model_dump_json() == changed.model_dump_json()
    assert knock_ons(plain) == [35, 35]


def test_the_query_never_names_an_as_flown_column(tmp_path: Path) -> None:
    path = write(tmp_path / "f.csv", CHAIN)
    row = subject(path, "AA1")
    con = dot.ensure_cache(path)
    seen: list[str] = []
    con.set_trace_callback(seen.append)
    try:
        dot.later_legs(row, path)
    finally:
        con.set_trace_callback(None)
    assert seen
    for statement in seen:
        lowered = statement.lower()
        for forbidden in (
            "delay",
            "departure_time",
            "arrival_time",
            "wheels",
            "cancel",
        ):
            assert forbidden not in lowered


def test_the_lookup_uses_the_tail_index(tmp_path: Path) -> None:
    """The cache's existing (tail, dep_abs) index serves it; no table scan."""
    path = write(tmp_path / "f.csv", CHAIN)
    con = dot.ensure_cache(path)
    plan = " ".join(
        str(r[3])
        for r in con.execute(
            "EXPLAIN QUERY PLAN SELECT flight, origin, dest, dep_abs, arr_abs "
            "FROM flights WHERE tail = ? AND dep_abs > ? AND dep_abs < ? "
            "ORDER BY dep_abs, flight",
            ("N1", 0, 1),
        )
    )
    assert "flights_tail_dep" in plan
    assert "SCAN" not in plan.replace("SCAN flights USING", "")


# --- the route -----------------------------------------------------------------


def _run_for(client: TestClient, flight_id: str) -> dict[str, Any]:
    row = next(r for r in _scenarios(client, limit=200) if r["flight_id"] == flight_id)
    return _post_run(client, row["scenario_id"])


def test_route_projects_a_deal_run_from_the_plan_arrival(client: TestClient) -> None:
    run = _run_for(client, "NK301")
    assert run["decision"]["kind"] == "DEAL"
    response = client.get(f"/runs/{run['run_id']}/spread")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flight_id"] == "NK301"
    assert body["tail_number"] == "N300NK"
    assert body["plan_arrival"] is not None
    assert [leg["flight_id"] for leg in body["legs"]] == ["NK302", "NK303"]
    first = body["legs"][0]
    assert first["scheduled_departure"] == "10:30"
    assert first["provenance"] == "real"
    assert first["projection"]["provenance"] == "derived"
    assert first["projection"]["knock_on_min"] >= 0
    assert "not what actually happened" in body["note"]
    assert not _keys(body) & OUTCOME_FIELDS


def test_route_lists_the_chain_for_a_no_go_run_without_a_projection(
    client: TestClient,
) -> None:
    run = _run_for(client, "NK301")
    # Close every runway: nothing is legal, so the run ends in a no-go.
    closed = [r["id"] for r in run["airport"]["runways"]]
    no_go = _post_run(
        client,
        next(r for r in _scenarios(client, limit=200) if r["flight_id"] == "NK301")[
            "scenario_id"
        ],
        closed_runways=closed,
    )
    assert no_go["decision"]["kind"] == "NO_GO"
    body = client.get(f"/runs/{no_go['run_id']}/spread").json()
    assert [leg["flight_id"] for leg in body["legs"]] == ["NK302", "NK303"]
    assert body["plan_arrival"] is None
    assert all(leg["projection"] is None for leg in body["legs"])
    assert all(leg["unprojected_reason"] for leg in body["legs"])


def test_route_for_a_flight_with_no_later_legs(client: TestClient) -> None:
    run = _run_for(client, "EV901")
    body = client.get(f"/runs/{run['run_id']}/spread").json()
    assert body["legs"] == []


def test_route_for_an_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/runs/nope/spread").status_code == 404


def test_route_changes_no_card_hash_or_log(client: TestClient) -> None:
    run = _run_for(client, "NK301")
    before = client.get(f"/runs/{run['run_id']}/log").json()
    for _ in range(2):
        assert client.get(f"/runs/{run['run_id']}/spread").status_code == 200
    assert client.get(f"/runs/{run['run_id']}/log").json() == before


# --- the real data -------------------------------------------------------------


def _real_cache_exists() -> bool:
    try:
        return REAL_CSV.exists() and dot.cache_path(REAL_CSV).exists()
    except dot.DotError:
        return False


@pytest.mark.skipif(
    not _real_cache_exists(), reason="the real flights cache has not been built"
)
def test_real_data_answers_in_well_under_a_second() -> None:
    rows = dot.sample_rows(100, seed=3)
    worst = 0.0
    for row in rows:
        started = time.perf_counter()
        result = delay_spread(row, dot.scheduled_arrival_min(row) + 60)
        worst = max(worst, time.perf_counter() - started)
        assert all(leg.provenance == "real" for leg in result.legs)
    assert worst < 1.0
