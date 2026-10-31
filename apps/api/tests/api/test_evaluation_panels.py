"""The workbook-limits and headline routes, read against the real results file."""

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api import evaluation as evaluation_module
from app.api.headline import HEADLINE
from app.negotiation import rule_values as rv
from app.negotiation.contracts import AircraftSize
from app.negotiation.protocol import MAX_TURNS

REAL = Path(evaluation_module.DEFAULT_RESULTS_DIR) / "latest_off_none.json"
LIMIT_IDS = [
    "turns",
    "runway_capacity",
    "fuel_on_board",
    "alternate_fuel",
    "synthetic_fields",
    "hold_burn",
    "departure_wake",
    "flights_file",
]


def _real_measures() -> dict[str, dict[str, Any]]:
    report = json.loads(REAL.read_text())
    return {m["name"]: m for p in report["panels"] for m in p["measures"]}


# --- limits ----------------------------------------------------------------------


def test_limits_list_every_difference_with_what_we_do_and_why(
    client: TestClient,
) -> None:
    body = client.get("/evaluation/limits").json()
    assert body["title"] == "Where we differ from the challenge workbook"
    assert [i["id"] for i in body["items"]] == LIMIT_IDS
    for item in body["items"]:
        assert set(item) == {"id", "limit", "what_we_do", "why", "checked_against"}
        assert all(item[k].strip() for k in item)


def test_limits_agree_with_the_code_they_describe(client: TestClient) -> None:
    items = {i["id"]: i for i in client.get("/evaluation/limits").json()["items"]}
    # Turns: the brief's 3 is stated, and the code's cap is the 2 we state.
    assert MAX_TURNS == 2
    turns = items["turns"]["what_we_do"]
    assert "within 3 turns" in turns
    assert "the fallback decides" in turns
    assert turns.endswith("We stop at 2.")
    # Closed runways leave the hourly limit as it was.
    assert (
        "does not lower the airport's hourly limit"
        in items["runway_capacity"]["what_we_do"]
    )
    assert "arrivals only" in items["runway_capacity"]["what_we_do"]
    # Fuel: the workbook's default is 45, and the text must not claim flights sit at it.
    assert rv.rule_value(rv.FUEL_SPARE_ON_ARRIVAL_MIN).value == 45
    fuel = items["fuel_on_board"]["what_we_do"]
    assert "usually above the workbook's 45-minute default" in fuel
    assert "around" not in fuel
    # The alternate test is our policy, not the workbook's.
    assert rv.rule_value(rv.ALTERNATE_WINDOW_MIN).status is rv.Status.POLICY
    # Holding burn: 6,500 kg/h rounds up to 109 kg/min.
    assert rv.rule_value(rv.HOLD_BURN_WIDE_KG_PER_H).value == 6500
    assert rv.hold_burn_kg_per_min(AircraftSize.WIDE_BODY) == 109
    assert "6,500 kg an hour" in items["hold_burn"]["what_we_do"]
    assert "109 kg a minute" in items["hold_burn"]["what_we_do"]
    # Decision time is derived, so it is not in the synthetic group.
    synthetic = items["synthetic_fields"]
    assert "decision time" not in synthetic["limit"].lower()
    assert "Decision time is not in this group" in synthetic["why"]


# --- headline --------------------------------------------------------------------


def test_headline_reads_the_real_results_without_changing_a_value(
    client: TestClient, results: Path
) -> None:
    shutil.copy(REAL, results / REAL.name)
    stored = _real_measures()
    body = client.get("/evaluation/headline").json()
    assert body["status"] == "ok"
    assert body["live"] == []
    assert body["other"] == []
    items = body["rules_only"]
    assert [i["metric"] for i in items] == [metric for _, _, metric in HEADLINE]
    meta = json.loads(REAL.read_text())["meta"]
    for item in items:
        source = stored[item["metric"]]
        assert item["state"] == "measured"
        assert item["evidence_class"] == source["evidence_class"] == "rules_only"
        assert item["value"].startswith(f"{source['k']}/{source['n']} (")
        assert item["value"].endswith("%)")
        assert item["n"] == source["n"]
        assert item["interval_text"].endswith("%")
        assert item["commit"] == meta["commit"][:12]
        assert item["mode"] == meta["mode"] == "off"
        assert item["seed"] == meta["seed"]


def test_headline_values_match_the_evaluation_rows_exactly(
    client: TestClient, results: Path
) -> None:
    shutil.copy(REAL, results / REAL.name)
    rows = {r["metric"]: r for r in client.get("/evaluation").json()["rows"]}
    for item in client.get("/evaluation/headline").json()["rules_only"]:
        row = rows[item["metric"]]
        assert item["value"] == row["value"]
        assert item["interval_text"] == row["interval_text"]
        assert item["n"] == row["n"]
        assert item["evidence_class"] == row["evidence_class"]


def test_headline_says_not_yet_run_and_unreadable(
    client: TestClient, results: Path
) -> None:
    empty = {"status": "not_yet_run", "rules_only": [], "live": [], "other": []}
    assert client.get("/evaluation/headline").json() == empty
    (results / "latest_off_none.json").write_text("{ not json")
    assert client.get("/evaluation/headline").json() == {
        **empty,
        "status": "unreadable",
    }


def test_headline_marks_a_measure_the_results_lack_as_absent(
    client: TestClient, results: Path
) -> None:
    report = json.loads(REAL.read_text())
    dropped = "Final packages breaking a rule"
    for panel in report["panels"]:
        panel["measures"] = [m for m in panel["measures"] if m["name"] != dropped]
    (results / "latest_off_none.json").write_text(json.dumps(report))
    items = {
        i["metric"]: i for i in client.get("/evaluation/headline").json()["rules_only"]
    }
    gone = items[dropped]
    assert gone["state"] == "absent"
    assert gone["value"] is None
    assert gone["evidence_class"] is None
    assert gone["commit"] is None
    assert items["Deal rate, all rows"]["state"] == "measured"


def test_headline_marks_a_measure_not_reached(
    client: TestClient, results: Path
) -> None:
    report = json.loads(REAL.read_text())
    name = "Deal rate, all rows"
    for panel in report["panels"]:
        for m in panel["measures"]:
            if m["name"] == name:
                m.update(status="NOT_REACHED", value=None, k=None, n=None)
                m.update(ci_low=None, ci_high=None, note="no model ran")
    (results / "latest_off_none.json").write_text(json.dumps(report))
    item = client.get("/evaluation/headline").json()["rules_only"][0]
    assert item["metric"] == name
    assert item["state"] == "not_reached"
    assert item["value"] == "NOT_REACHED"
    assert item["n"] is None
    assert item["interval_text"] is None
    assert item["note"] == "no model ran"


def test_headline_lists_live_measures_apart_from_rules_only(
    client: TestClient, results: Path
) -> None:
    shutil.copy(REAL, results / REAL.name)
    live_meta = {
        "commit": "feedface0123456789",
        "commit_dirty": False,
        "mode": "live",
        "split": "frozen",
        "seed": 3,
        "sample_size": 30,
        "generated_at": "2026-10-31T06:00:00+00:00",
    }
    live_measure = {
        "name": "Deal rate, all rows",
        "compared_against": "reported as measured",
        "evidence_class": "live",
        "status": "MEASURED",
        "value": 0.5,
        "unit": "",
        "k": 15,
        "n": 30,
        "ci_low": 0.33,
        "ci_high": 0.67,
        "note": "",
        "meta": live_meta,
    }
    report = {
        "panels": [
            {
                "title": "Live",
                "evidence_class": "live",
                "meta": live_meta,
                "measures": [live_measure],
            }
        ],
        "limits": [],
    }
    (results / "latest_live_frozen.json").write_text(json.dumps(report))
    body = client.get("/evaluation/headline").json()
    assert {i["evidence_class"] for i in body["rules_only"]} == {"rules_only"}
    live = {i["metric"]: i for i in body["live"]}
    assert live["Deal rate, all rows"]["state"] == "measured"
    assert live["Deal rate, all rows"]["value"] == "15/30 (50.0%)"
    assert live["Deal rate, all rows"]["mode"] == "live"
    assert live["Deal rate, all rows"]["commit"] == "feedface0123"
    assert live["Deal rate, all rows"]["seed"] == 3
    # A live list says plainly which headline measures it lacks.
    assert live["Final packages breaking a rule"]["state"] == "absent"
    assert len(body["live"]) == len(HEADLINE)
    # The rules-only deal rate is untouched by the live one.
    stored = json.loads(REAL.read_text())
    deal = next(
        m
        for panel in stored["panels"]
        for m in panel["measures"]
        if m["name"] == "Deal rate, all rows"
    )
    assert body["rules_only"][0]["value"].startswith(f"{deal['k']}/{deal['n']}")
