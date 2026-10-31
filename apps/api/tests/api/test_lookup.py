"""Finding any eligible row: each kind of answer, and that a found row really runs."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import catalogue as catalogue_module
from app.negotiation import dot
from tests.api.conftest import ClientFactory
from tests.api.test_routes import OUTCOME_FIELDS, _keys, _post_run, _scenarios, _sign

# Eligible by 45 minutes of late-aircraft delay. Only the identity columns change.
_TEMPLATE = (
    "2015,3,5,4,{airline},{number},{tail},{origin},{destination},0700,0812,72,14,0000,"
    "150,150,125,867,0928,12,0830,0940,70,0,0,,,,25,45,"
)


def _add_flight(csv: Path, airline: str, number: int, route: str, tail: str) -> None:
    origin, destination = route.split("-")
    line = _TEMPLATE.format(
        airline=airline,
        number=number,
        tail=tail,
        origin=origin,
        destination=destination,
    )
    with csv.open("a") as handle:
        handle.write(line + "\n")


def _lookup(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/scenarios/lookup", params={"date": "2015-03-05", **params})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def outside_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empties the sampled pool, so only the lookup can reach a row."""
    monkeypatch.setattr(catalogue_module, "POOL_SIZE", 0)


# --- the answers ---------------------------------------------------------------


def test_one_match_is_the_normal_summary_with_no_outcome_field(
    client: TestClient,
) -> None:
    body = _lookup(client, flight_number=301, airline="NK", origin="BOS")
    assert body["status"] == "one"
    assert body["total"] == 1
    assert body["reason"] is None
    row = body["matches"][0]
    assert row["scenario_id"] == "DOT-20150305-NK301-BOSORD-s0"
    assert row["route"] == "BOS to ORD"
    # Exactly what the list shows, and none of the as-flown columns.
    listed = next(
        r
        for r in _scenarios(client, limit=200)
        if r["scenario_id"] == row["scenario_id"]
    )
    assert row == listed
    assert not _keys(body) & OUTCOME_FIELDS


def test_several_matches_are_all_returned(
    make_client: ClientFactory, flights_csv: Path
) -> None:
    _add_flight(flights_csv, "NK", 555, "ATL-ORD", "N555NK")
    _add_flight(flights_csv, "DL", 555, "ATL-DEN", "N555DL")
    _add_flight(flights_csv, "DL", 555, "SEA-PDX", "N556DL")
    client = make_client()
    body = _lookup(client, flight_number=555)
    assert body["status"] == "several"
    assert body["total"] == 3
    assert {r["flight_id"] for r in body["matches"]} == {"NK555", "DL555"}

    assert _lookup(client, flight_number=555, airline="dl")["total"] == 2
    narrowed = _lookup(client, flight_number=555, origin="sea", destination="pdx")
    assert narrowed["status"] == "one"
    assert narrowed["matches"][0]["route"] == "SEA to PDX"


def test_the_result_size_is_bounded_and_says_how_many_there_are(
    make_client: ClientFactory,
    flights_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for i, route in enumerate(("ATL-ORD", "ATL-DEN", "SEA-PDX")):
        _add_flight(flights_csv, "NK", 555, route, f"N55{i}NK")
    monkeypatch.setattr(catalogue_module, "MAX_LOOKUP_RESULTS", 2)
    body = _lookup(make_client(), flight_number=555)
    assert body["status"] == "several"
    assert body["total"] == 3
    assert len(body["matches"]) == 2


@pytest.mark.parametrize(
    ("params", "reason", "words"),
    [
        (
            {"date": "2015-10-05", "flight_number": 601},
            "october_excluded",
            "numeric",
        ),
        ({"date": "2014-03-05", "flight_number": 301}, "outside_dataset", "2015 only"),
        ({"flight_number": 9999}, "not_in_data", "No flight numbered 9999"),
        ({"flight_number": 301, "origin": "ZZZ"}, "not_in_data", "No flight"),
        ({"flight_number": 302}, "below_thresholds", "not a disruption case"),
        ({"flight_number": 701}, "cancelled_or_diverted", "cancelled or diverted"),
        ({"flight_number": 501}, "no_tail_number", "tail number"),
    ],
)
def test_no_match_says_why_in_plain_words_and_is_not_an_error(
    client: TestClient, params: dict[str, Any], reason: str, words: str
) -> None:
    body = _lookup(client, **params)
    assert body["status"] == "none"
    assert body["matches"] == []
    assert body["total"] == 0
    assert body["reason"] == reason
    assert words in body["message"]
    assert not _keys(body) & OUTCOME_FIELDS


def test_a_below_threshold_answer_reveals_no_delay_of_that_flight(
    client: TestClient,
) -> None:
    """NK302's own departure delay is 55 and its arrival delay 5."""
    text = json.dumps(_lookup(client, flight_number=302))
    assert "55" not in text
    assert " 5 " not in text


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"date": "2015-03-05"},
        {"flight_number": 301},
        {"date": "not-a-date", "flight_number": 301},
        {"date": "2015-02-30", "flight_number": 301},
        {"date": "2015-03-05", "flight_number": 0},
        {"date": "2015-03-05", "flight_number": 10000},
        {"date": "2015-03-05", "flight_number": "abc"},
        {"date": "2015-03-05", "flight_number": 301, "airline": "TOOLONG"},
        {"date": "2015-03-05", "flight_number": 301, "origin": "AB"},
        {"date": "2015-03-05", "flight_number": 301, "destination": "1' OR 1=1"},
    ],
)
def test_bad_input_is_refused(client: TestClient, params: dict[str, Any]) -> None:
    assert client.get("/scenarios/lookup", params=params).status_code == 422


def test_a_missing_dataset_is_the_same_clear_error(
    tmp_path: Path, make_client: ClientFactory, flights_csv: Path
) -> None:
    client = make_client()
    flights_csv.unlink()
    dot.clear_connections()
    response = client.get(
        "/scenarios/lookup", params={"date": "2015-03-05", "flight_number": 301}
    )
    assert response.status_code == 503
    assert "FLIGHTS_CSV" in response.json()["detail"]


def test_the_count_is_every_eligible_row(client: TestClient, flights_csv: Path) -> None:
    expected = sum(1 for _ in dot.iter_eligible_rows())
    assert client.get("/scenarios/count").json() == {"eligible_total": expected}


# --- a found row runs ----------------------------------------------------------


def _found_deal(client: TestClient) -> dict[str, Any]:
    for row in dot.iter_eligible_rows():
        body = _lookup(
            client,
            date=f"{row.year}-{row.month:02d}-{row.day:02d}",
            flight_number=row.flight_number,
            airline=row.airline,
            origin=row.origin_airport,
            destination=row.destination_airport,
        )
        run = _post_run(client, body["matches"][0]["scenario_id"])
        if run["decision"]["kind"] == "DEAL":
            return run
    raise AssertionError("no fixture row reaches a deal")


@pytest.mark.usefixtures("outside_pool")
def test_a_row_outside_the_pool_runs_signs_off_and_verifies_its_log(
    client: TestClient,
) -> None:
    assert _scenarios(client, limit=200) == []
    run = _found_deal(client)
    assert _sign(client, run)["status"] == "APPROVED"
    run_id = run["run_id"]
    log = client.get(f"/runs/{run_id}/log").json()
    assert log["verify"]["valid"] is True
    assert log["entries"][-1]["kind"] == "signoff"
    assert client.post(f"/runs/{run_id}/log/verify").json()["valid"] is True
    tampered = client.post(f"/runs/{run_id}/log/verify", json={"tamper": True}).json()
    assert tampered["valid"] is False


def test_a_found_row_has_the_same_seed_and_parameters_as_the_pool(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    pooled = make_client()
    row = _scenarios(pooled, limit=1)[0]
    expected = _post_run(pooled, row["scenario_id"])

    monkeypatch.setattr(catalogue_module, "POOL_SIZE", 0)
    fresh = make_client()
    assert _scenarios(fresh, limit=200) == []
    found = _post_run(fresh, row["scenario_id"])
    assert found["state_version"] == expected["state_version"]
    assert found["field_versions"] == expected["field_versions"]
    assert found["decision"] == expected["decision"]


@pytest.mark.usefixtures("outside_pool")
@pytest.mark.parametrize(
    "scenario_id",
    [
        "nope",
        "DOT-20150305-NK9999-BOSORD-s0",  # no such flight
        "DOT-20150305-NK302-ORDDEN-s0",  # on the schedule, below the thresholds
        "DOT-20150305-NK301-BOSORD-s1",  # another seed is another scenario
        "DOT-20150230-NK301-BOSORD-s0",  # not a date
        "DOT-20151005-AA601-1039711298-s0",  # October
    ],
)
def test_runs_refuse_an_id_that_is_not_an_eligible_row(
    client: TestClient, scenario_id: str
) -> None:
    response = client.post("/runs", json={"scenario_id": scenario_id, "mode": "off"})
    assert response.status_code == 404


@pytest.mark.usefixtures("outside_pool")
def test_a_found_row_with_no_recording_says_so_and_recorded_mode_shows_the_miss(
    client: TestClient,
) -> None:
    row = _lookup(client, flight_number=301, airline="NK", origin="BOS")["matches"][0]
    assert row["has_recording"] is False
    run = _post_run(client, row["scenario_id"], "recorded")
    assert {f["kind"] for f in run["faults"]} <= {"recording_miss"}


def test_found_rows_are_bounded_and_found_again_from_their_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalogue_module, "MAX_FOUND_ENTRIES", 1)
    monkeypatch.setattr(catalogue_module, "POOL_SIZE", 0)
    first = _lookup(client, flight_number=301, airline="NK", origin="BOS")["matches"][0]
    _lookup(client, flight_number=805)
    assert len(client.app.state.runs.catalogue._found) == 1  # type: ignore[attr-defined]
    assert (
        _post_run(client, first["scenario_id"])["scenario_id"] == first["scenario_id"]
    )
