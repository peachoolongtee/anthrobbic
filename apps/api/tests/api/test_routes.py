"""Every dashboard endpoint, every try-to-break-it control, with no key or network."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import runs as runs_module
from app.api.runs import RunService, build_injected
from app.config import Settings
from app.main import create_app
from app.negotiation import dot
from app.negotiation.card import MODEL_NOTE_LABEL, REASON_CODES
from app.negotiation.contracts import Deal
from app.negotiation.protocol import NegotiationResult, run_negotiation
from app.negotiation.recording import RecordingClient
from app.negotiation.rules import check_package, rule_ids
from app.negotiation.scenario import build_scenario
from tests.api.conftest import ClientFactory
from tests.negotiation.test_agents import ScriptedClient, accept_all, reply_message

# Every as-flown column on `DotRow`. None may appear as a key in any response.
OUTCOME_FIELDS = frozenset(
    {
        "departure_time",
        "departure_delay",
        "departure_delay_min",
        "wheels_off",
        "elapsed_time",
        "air_time",
        "wheels_on",
        "taxi_in",
        "arrival_time",
        "arrival_delay",
        "arrival_min",
        "air_system_delay",
        "security_delay",
        "airline_delay",
        "late_aircraft_delay",
        "weather_delay",
        "diverted",
        "cancelled",
        "cancellation_reason",
    }
)
UI_UNSAFE_OPTIONS = (
    "PLT-FUEL-POLICY",
    "ATC-RWY-CLOSED",
    "ATC-WAKE-SEP",
    "GND-GATE-OVERLAP",
)
CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _scenarios(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/scenarios", params=params)
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def _post_run(
    client: TestClient, scenario_id: str, mode: str = "off", **overrides: Any
) -> dict[str, Any]:
    response = client.post(
        "/runs",
        json={"scenario_id": scenario_id, "mode": mode, "overrides": overrides},
    )
    assert response.status_code == 200, response.text
    run: dict[str, Any] = response.json()
    return run


def _deal_run(client: TestClient) -> dict[str, Any]:
    for row in _scenarios(client, limit=200):
        run = _post_run(client, row["scenario_id"])
        if run["decision"]["kind"] == "DEAL":
            return run
    raise AssertionError("no fixture row reaches a deal")


def _signoff_body(run: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "terms_hash": run["decision"]["terms_hash"],
        "state_version_seen": run["state_version"],
        "card_hash_seen": run["card"]["card_hash"],
        "decided_by": "Duty manager",
        "airline_decisions_approved": True,
        "requests_to_send": True,
        "field_versions_seen": run["field_versions"],
        "card_field_hashes_seen": run["card"]["field_hashes"],
        **changes,
    }


def _sign(client: TestClient, run: dict[str, Any], **changes: Any) -> dict[str, Any]:
    response = client.post(
        f"/runs/{run['run_id']}/signoff", json=_signoff_body(run, **changes)
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def _record_row(recordings: Path, note: str = "") -> dot.DotRow:
    """Records every call a fixture row makes, through a fake transport."""
    row = next(iter(dot.iter_eligible_rows()))

    def script(_d: Any, _t: int, ids: list[str], _k: dict[str, Any]) -> Any:
        return reply_message(ids, model_note=note)

    recorder = RecordingClient(ScriptedClient(script), recordings, record=True)
    result = run_negotiation(build_scenario(row), "live", client=recorder)
    assert result.path == "consensus"
    return row


# --- health and scenarios ------------------------------------------------------


def test_health_still_works(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_scenarios_are_real_rows_with_their_fields(client: TestClient) -> None:
    rows = _scenarios(client, limit=200)
    assert rows
    for row in rows:
        assert row["scenario_id"].startswith("DOT-2015")
        assert " to " in row["route"]
        assert CLOCK.match(row["scheduled_arrival"])
        assert row["cause"] in ("weather", "late_aircraft")
        assert row["delay_provenance"] == "derived"
        assert row["has_recording"] is False
        if row["next_leg"]:
            assert CLOCK.match(row["next_leg"]["scheduled_departure"])
            assert row["next_leg"]["provenance"] == "derived"
            assert row["next_leg"]["delay_provenance"] == "synthetic"
    assert any(row["next_leg"] for row in rows)


def test_scenario_ids_are_stable_across_limits_and_processes(
    client: TestClient, make_client: ClientFactory
) -> None:
    every = [r["scenario_id"] for r in _scenarios(client, limit=200)]
    assert [r["scenario_id"] for r in _scenarios(client, limit=3)] == every[:3]
    assert [r["scenario_id"] for r in _scenarios(make_client(), limit=200)] == every
    assert len(every) == len(set(every))


def test_scenarios_filter_by_cause_and_validate_input(client: TestClient) -> None:
    for cause in ("weather", "late_aircraft"):
        rows = _scenarios(client, cause=cause, limit=200)
        assert rows and {r["cause"] for r in rows} == {cause}
    assert len(_scenarios(client, limit=1)) == 1
    assert client.get("/scenarios", params={"cause": "bogus"}).status_code == 422
    assert client.get("/scenarios", params={"limit": 0}).status_code == 422


def test_a_missing_dataset_is_a_clear_error_without_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nowhere" / "private-name.csv"
    monkeypatch.setenv(dot.ENV_CSV, str(missing))
    response = TestClient(create_app(Settings())).get("/scenarios")
    assert response.status_code == 503
    assert "FLIGHTS_CSV" in response.json()["detail"]
    assert "private-name" not in response.text


def test_rows_with_a_complete_recording_come_first_and_are_flagged(
    make_client: ClientFactory, recordings: Path
) -> None:
    row = _record_row(recordings)
    rows = _scenarios(make_client(), limit=200)
    assert rows[0]["has_recording"] is True
    assert rows[0]["flight_id"] == row.flight_id
    assert sum(r["has_recording"] for r in rows) == 1


# --- no as-flown outcome anywhere ----------------------------------------------


def test_no_outcome_field_appears_in_any_response(
    client: TestClient, results: Path
) -> None:
    responses: list[Any] = [client.get("/scenarios", params={"limit": 200}).json()]
    run = _deal_run(client)
    responses.append(run)
    responses.append(_post_run(client, run["scenario_id"], "recorded"))
    responses.append(
        _post_run(client, run["scenario_id"], inject_unsafe="PLT-FUEL-POLICY")
    )
    run_id = run["run_id"]
    gate = run["decision"]["package"]["gate_id"]
    responses.append(
        client.post(f"/runs/{run_id}/state", json={"closed_gates": [gate]}).json()
    )
    responses.append(_sign(client, run))
    responses.append(client.get(f"/runs/{run_id}/log").json())
    responses.append(
        client.post(f"/runs/{run_id}/log/verify", json={"tamper": True}).json()
    )
    responses.append(client.get("/evaluation").json())
    for body in responses:
        assert not _keys(body) & OUTCOME_FIELDS


def test_changing_as_flown_columns_changes_no_response(
    make_client: ClientFactory, flights_csv: Path
) -> None:
    """The row's own outcome and its next leg's departure delay are not read."""
    before = make_client()
    rows = _scenarios(before, limit=200)
    target = next(r for r in rows if r["next_leg"])
    baseline = _post_run(before, target["scenario_id"])

    lines = flights_csv.read_text().splitlines()
    header = lines[0].split(",")
    columns = ("ARRIVAL_TIME", "ARRIVAL_DELAY", "WHEELS_ON", "TAXI_IN", "AIR_TIME")
    positions = [header.index(c) for c in columns]
    delay_at = header.index("DEPARTURE_DELAY")
    number_at = header.index("FLIGHT_NUMBER")
    airline_at = header.index("AIRLINE")
    origin_at = header.index("ORIGIN_AIRPORT")
    dest_at = header.index("DESTINATION_AIRPORT")
    origin, dest = target["route"].split(" to ")
    edited = [lines[0]]
    for line in lines[1:]:
        cells = line.split(",")
        flight = f"{cells[airline_at]}{cells[number_at]}"
        if (
            flight == target["flight_id"]
            and cells[origin_at] == origin
            and cells[dest_at] == dest
        ):
            for at in positions:
                cells[at] = "999"
        if flight == target["next_leg"]["flight_id"]:
            cells[delay_at] = "777"
        edited.append(",".join(cells))
    flights_csv.write_text("\n".join(edited) + "\n")
    dot.clear_connections()

    after = make_client()
    assert _scenarios(after, limit=200) == rows
    changed = _post_run(after, target["scenario_id"])
    assert changed["state_version"] == baseline["state_version"]
    assert changed["card"] == baseline["card"]


# --- runs ----------------------------------------------------------------------


def test_off_mode_returns_the_full_run_with_card_text_from_the_card(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    assert run["mode"] == "off"
    assert run["path"] == "fallback"
    assert run["fallback_trigger"] == "llm_off"
    assert run["turns"] == []
    assert run["faults"] == []
    assert run["model_notes"] == []
    assert run["state_version"] and run["field_versions"]
    assert run["log_head"] != "0" * 64
    assert run["airport"]["runways"] and run["airport"]["gates"]

    decision = run["decision"]
    card = run["card"]
    assert decision["terms_hash"] and card["card_hash"] and card["field_hashes"]
    assert card["action"].startswith(card["package_name"])
    assert card["action"].endswith("every hard rule passes at the current state.")
    assert REASON_CODES["FALLBACK_LOWEST_COST"] in card["why"]
    assert {f["key"] for f in card["airline_decisions"]} == {"gate_id"}
    assert {f["key"] for f in card["requests"]} == {"slot", "action"}
    assert all(CLOCK.search(f["value"][-6:-1]) for f in card["action_facts"][1:2])
    for line in card["rules"]:
        assert line["rule_id"] and line["source"] and line["status"]
        assert line["label"] and line["message"] is None
        assert line["result"] == "pass"


def test_failed_rule_lines_carry_message_observed_limit_and_unit(
    client: TestClient,
) -> None:
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"])
    lines = [line for p in run["removed_packages"] for line in p["violations"]]
    assert lines
    for line in lines:
        assert line["result"] in ("fail", "missing_data")
        assert line["message"]
        assert line["source"] and line["status"]
        if line["result"] == "fail":
            assert line["observed"] is not None and line["limit"] is not None
            assert line["unit"]


def test_unknown_scenario_and_mode_are_refused(client: TestClient) -> None:
    missing = client.post("/runs", json={"scenario_id": "nope", "mode": "off"})
    assert missing.status_code == 404
    row = _scenarios(client, limit=1)[0]
    bad = client.post("/runs", json={"scenario_id": row["scenario_id"], "mode": "x"})
    assert bad.status_code == 422


def test_recorded_mode_with_no_recording_logs_the_miss_and_falls_back(
    client: TestClient,
) -> None:
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "recorded")
    assert run["path"] in ("fallback", "no_deal")
    assert run["fallback_trigger"] == "fault"
    assert {f["kind"] for f in run["faults"]} == {"recording_miss"}
    assert {f["domain"] for f in run["faults"]} == {"atc", "pilot", "ground"}
    log = client.get(f"/runs/{run['run_id']}/log").json()
    faults = [e for e in log["entries"] if e["kind"] == "fault"]
    assert len(faults) == 3
    assert all("recording_miss" in e["summary"] for e in faults)


def test_recorded_mode_with_a_recording_shows_consensus_and_unverified_notes(
    make_client: ClientFactory, recordings: Path
) -> None:
    secret_note = "Model prose that must stay out of the facts"
    _record_row(recordings, note=secret_note)
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "recorded")
    assert run["path"] == "consensus"
    assert run["faults"] == []
    assert len(run["turns"]) == 1
    assert [r["domain"] for r in run["turns"][0]["responses"]] == [
        "atc",
        "pilot",
        "ground",
    ]
    notes = run["model_notes"]
    assert [n["domain"] for n in notes] == ["atc", "pilot", "ground"]
    for note in notes:
        assert note["text"] == secret_note
        assert note["unverified"] is True
        assert note["label"] == MODEL_NOTE_LABEL
    assert secret_note not in json.dumps(run["card"])
    assert secret_note not in json.dumps(run["decision"])
    log = client.get(f"/runs/{run['run_id']}/log")
    assert secret_note not in log.text


def test_an_override_changes_the_request_so_the_recording_misses_loudly(
    make_client: ClientFactory, recordings: Path
) -> None:
    _record_row(recordings)
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    baseline = _post_run(client, row["scenario_id"], "recorded")
    gate = baseline["decision"]["package"]["gate_id"]
    run = _post_run(client, row["scenario_id"], "recorded", closed_gates=[gate])
    assert {f["kind"] for f in run["faults"]} == {"recording_miss"}


# --- live is gated -------------------------------------------------------------


def test_live_is_refused_by_default_with_a_clear_error(client: TestClient) -> None:
    row = _scenarios(client, limit=1)[0]
    response = client.post(
        "/runs", json={"scenario_id": row["scenario_id"], "mode": "live"}
    )
    assert response.status_code == 403
    assert "ALLOW_LIVE=1" in response.json()["detail"]
    assert "no model call" in response.json()["detail"]


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "2"])
def test_only_one_enables_live(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ALLOW_LIVE", value)
    assert Settings().ALLOW_LIVE is False


def test_allow_live_reads_the_environment_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOW_LIVE", "1")
    assert Settings().ALLOW_LIVE is True


def test_allow_live_without_a_key_is_a_logged_fault_not_a_call(
    make_client: ClientFactory,
) -> None:
    client = make_client(allow_live=True)
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "live")
    assert [f["kind"] for f in run["faults"]] == ["missing_key"]


def test_the_key_is_never_returned(
    make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "sk-ant-test-never-show-this"
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    client = make_client(allow_live=True, live_client=ScriptedClient(accept_all))
    row = _scenarios(client, limit=1)[0]
    bodies = [
        _post_run(client, row["scenario_id"], mode)
        for mode in ("off", "recorded", "live")
    ]
    logs = [client.get(f"/runs/{b['run_id']}/log").text for b in bodies]
    assert key not in json.dumps(bodies)
    assert not any(key in text for text in logs)


# --- close a runway, block a gate ----------------------------------------------


def test_closing_every_runway_is_no_deal_with_binding_rules_and_no_card(
    client: TestClient,
) -> None:
    base = _deal_run(client)
    runways = [r["id"] for r in base["airport"]["runways"]]
    run = _post_run(client, base["scenario_id"], closed_runways=runways)
    assert run["path"] == "no_deal"
    assert run["card"] is None
    decision = run["decision"]
    assert decision["kind"] == "NO_DEAL"
    assert decision["reason_type"] == "NOTHING_LEGAL"
    assert decision["reason"].startswith("NO DEAL: nothing legal.")
    binding = {line["rule_id"]: line for line in decision["binding_rules"]}
    assert binding["ATC-RWY-CLOSED"]["observed"] == 1
    assert binding["ATC-RWY-CLOSED"]["limit"] == 0
    assert binding["ATC-RWY-CLOSED"]["message"] == "Uses a closed runway"
    assert decision["nearest_package"]
    assert decision["what_would_change"]
    assert all(r["closed"] for r in run["airport"]["runways"])

    response = client.post(
        f"/runs/{run['run_id']}/signoff",
        json={
            "terms_hash": decision["nearest_package"]["package_id"],
            "state_version_seen": run["state_version"],
            "card_hash_seen": "x",
            "decided_by": "Duty manager",
            "airline_decisions_approved": True,
            "requests_to_send": True,
        },
    )
    assert response.status_code == 409


def test_blocking_the_chosen_gate_moves_the_plan_and_shows_on_the_airport(
    client: TestClient,
) -> None:
    base = _deal_run(client)
    gate = base["decision"]["package"]["gate_id"]
    run = _post_run(client, base["scenario_id"], closed_gates=[gate])
    assert next(g for g in run["airport"]["gates"] if g["id"] == gate)["closed"]
    assert run["state_version"] != base["state_version"]
    if run["decision"]["kind"] == "DEAL":
        assert run["decision"]["package"]["gate_id"] != gate


def test_overrides_rebuild_a_new_scenario_and_leave_the_row_alone(
    client: TestClient,
) -> None:
    base = _deal_run(client)
    runway = base["airport"]["runways"][0]["id"]
    gate = base["airport"]["gates"][0]["id"]
    _post_run(client, base["scenario_id"], closed_runways=[runway], closed_gates=[gate])
    again = _post_run(client, base["scenario_id"])
    assert again["state_version"] == base["state_version"]
    assert again["decision"] == base["decision"]


def test_overrides_naming_unknown_resources_are_refused(client: TestClient) -> None:
    row = _scenarios(client, limit=1)[0]
    for overrides in (
        {"closed_runways": ["NOPE"]},
        {"closed_gates": ["NOPE"]},
        {"inject_unsafe": "NOT-A-RULE"},
    ):
        response = client.post(
            "/runs",
            json={
                "scenario_id": row["scenario_id"],
                "mode": "off",
                "overrides": overrides,
            },
        )
        assert response.status_code == 422
        assert "NOT-A-RULE" in response.text or "NOPE" in response.text


# --- the injected plan ---------------------------------------------------------


@pytest.mark.parametrize("rule_id", UI_UNSAFE_OPTIONS)
def test_injected_plan_is_stopped_by_its_named_rule_and_marked(
    client: TestClient, rule_id: str
) -> None:
    base = _deal_run(client)
    run = _post_run(client, base["scenario_id"], inject_unsafe=rule_id)
    assert run["injection"]["status"] == "STOPPED"
    assert run["injection"]["rule_id"] == rule_id
    injected = [p for p in run["removed_packages"] if p["injected"]]
    assert len(injected) == 1
    package = injected[0]
    assert package["package_id"] == run["injection"]["package_id"]
    assert package["label"].startswith("PKG-")
    assert package["violations"][0]["rule_id"] == rule_id
    assert package["violations"][0]["message"]
    assert not [p for p in run["removed_packages"][1:] if p["injected"]]

    log = client.get(f"/runs/{run['run_id']}/log").json()
    entries = [e for e in log["entries"] if e["kind"] == "injected_unsafe"]
    assert len(entries) == 1
    assert "STOPPED" in entries[0]["summary"]


@pytest.mark.parametrize("rule_id", rule_ids())
@pytest.mark.parametrize("mode", ["off", "recorded"])
def test_injected_plan_can_never_be_the_deal(
    client: TestClient, rule_id: str, mode: str
) -> None:
    for row in _scenarios(client, limit=200):
        run = _post_run(client, row["scenario_id"], mode, inject_unsafe=rule_id)
        decision = run["decision"]
        injected_id = run["injection"]["package_id"]
        if run["injection"]["status"] == "NOT_REACHED":
            assert injected_id is None
            assert not any(p["injected"] for p in run["removed_packages"])
            continue
        if decision["kind"] != "DEAL":
            continue
        assert decision["terms_hash"] != injected_id
        result = _sign(client, run, terms_hash=injected_id)
        assert result["status"] == "REFUSED_PACKAGE_CHANGED"
        assert result["airline_decisions"] == []
        assert result["requests"] == []


def test_the_injected_package_really_fails_every_scenario_it_is_built_for(
    flights_csv: Path,
) -> None:
    for row in dot.iter_eligible_rows():
        scenario = build_scenario(row)
        for rule_id in rule_ids():
            judged = build_injected(scenario, rule_id)
            if judged is None:
                continue
            package, violations = judged
            assert violations == tuple(
                sorted(
                    check_package(scenario, package),
                    key=lambda v: v.rule_id != rule_id,
                )
            )
            assert violations[0].rule_id == rule_id


def test_a_run_that_somehow_ends_on_the_injected_plan_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails closed even if the protocol were broken to return the injected plan."""
    base = _deal_run(client)

    def broken(scenario: Any, mode: Any, **kwargs: Any) -> NegotiationResult:
        real = run_negotiation(scenario, mode, **kwargs)
        judged = build_injected(scenario, "ATC-WAKE-SEP")
        assert judged is not None and isinstance(real.decision, Deal)
        forced = real.decision.model_copy(update={"package": judged[0]})
        return real.model_copy(update={"decision": forced})

    monkeypatch.setattr(runs_module, "run_negotiation", broken)
    response = client.post(
        "/runs",
        json={
            "scenario_id": base["scenario_id"],
            "mode": "off",
            "overrides": {"inject_unsafe": "ATC-WAKE-SEP"},
        },
    )
    assert response.status_code == 500
    assert "Run refused" in response.json()["detail"]


# --- state and sign-off --------------------------------------------------------


def test_signoff_approves_then_refuses_reuse_with_exact_statuses(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    approved = _sign(client, run)
    assert approved["status"] == "APPROVED"
    assert approved["package_name"] == run["card"]["package_name"]
    assert approved["changed_fields"] == []
    assert {t["name"] for t in approved["airline_decisions"]} == {"gate_id"}
    assert {t["name"] for t in approved["requests"]} == {"slot", "action"}
    assert approved["card_hash"] == run["card"]["card_hash"]

    log = client.get(f"/runs/{run['run_id']}/log").json()
    assert approved["log_head"] == log["head"]
    assert log["entries"][-1]["kind"] == "signoff"
    assert "APPROVED" in log["entries"][-1]["summary"]

    assert _sign(client, run)["status"] == "REFUSED_ALREADY_USED"


def test_signoff_only_issues_what_was_ticked(client: TestClient) -> None:
    run = _deal_run(client)
    result = _sign(client, run, requests_to_send=False)
    assert result["status"] == "APPROVED"
    assert result["airline_decisions"] and result["requests"] == []


def test_signoff_with_nothing_ticked_is_invalid(client: TestClient) -> None:
    run = _deal_run(client)
    response = client.post(
        f"/runs/{run['run_id']}/signoff",
        json=_signoff_body(
            run, airline_decisions_approved=False, requests_to_send=False
        ),
    )
    assert response.status_code == 422


def test_state_change_returns_a_new_version_and_stale_signoff_is_refused(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    gate = run["decision"]["package"]["gate_id"]
    changed = client.post(f"/runs/{run['run_id']}/state", json={"closed_gates": [gate]})
    assert changed.status_code == 200
    body = changed.json()
    assert body["state_version"] != run["state_version"]
    assert body["field_versions"] != run["field_versions"]

    result = _sign(client, run)
    assert result["status"] == "REFUSED_STATE_CHANGED"
    assert result["changed_fields"] == ["gate_occupancies"]
    assert result["airline_decisions"] == []
    assert result["requests"] == []
    assert any(v["rule_id"] == "GND-GATE-OVERLAP" for v in result["violations"])

    kinds = [
        e["kind"] for e in client.get(f"/runs/{run['run_id']}/log").json()["entries"]
    ]
    assert "state_change" in kinds
    assert kinds[-1] == "signoff"


def test_stale_signoff_names_no_field_without_the_seen_versions(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    runway = run["decision"]["package"]["runway_id"]
    client.post(f"/runs/{run['run_id']}/state", json={"closed_runways": [runway]})
    result = _sign(client, run, field_versions_seen=None)
    assert result["status"] == "REFUSED_STATE_CHANGED"
    assert result["changed_fields"] == ["unattributed"]


def test_state_change_validates_ids_and_the_run(client: TestClient) -> None:
    run = _deal_run(client)
    response = client.post(
        f"/runs/{run['run_id']}/state", json={"closed_runways": ["NOPE"]}
    )
    assert response.status_code == 422
    assert client.post("/runs/none/state", json={}).status_code == 404


def test_signoff_with_a_changed_package_or_card_is_refused(client: TestClient) -> None:
    run = _deal_run(client)
    moved = _sign(client, run, terms_hash="0" * 64)
    assert moved["status"] == "REFUSED_PACKAGE_CHANGED"
    fields = dict(run["card"]["field_hashes"])
    fields["why"] = "0" * 64
    changed = _sign(client, run, card_hash_seen="0" * 64, card_field_hashes_seen=fields)
    assert changed["status"] == "REFUSED_CARD_CHANGED"
    assert changed["changed_card_fields"] == ["unattributed"]


def test_signoff_on_an_unknown_run_says_runs_are_in_memory(client: TestClient) -> None:
    response = client.post(
        "/runs/none/signoff",
        json={
            "terms_hash": "x",
            "state_version_seen": "x",
            "card_hash_seen": "x",
            "decided_by": "Duty manager",
            "airline_decisions_approved": True,
            "requests_to_send": True,
        },
    )
    assert response.status_code == 404
    assert "in memory" in response.json()["detail"]


def test_used_tokens_are_per_process(make_client: ClientFactory) -> None:
    first = make_client()
    run = _deal_run(first)
    assert _sign(first, run)["status"] == "APPROVED"
    same_process = _post_run(first, run["scenario_id"])
    assert _sign(first, same_process)["status"] == "REFUSED_ALREADY_USED"
    new_process = make_client()
    fresh = _post_run(new_process, run["scenario_id"])
    assert _sign(new_process, fresh)["status"] == "APPROVED"


# --- the log -------------------------------------------------------------------


def test_log_lists_every_entry_and_verifies(client: TestClient) -> None:
    run = _deal_run(client)
    log = client.get(f"/runs/{run['run_id']}/log").json()
    assert [e["seq"] for e in log["entries"]] == list(range(len(log["entries"])))
    kinds = [e["kind"] for e in log["entries"]]
    assert kinds[0] == "run_context"
    assert "run_start" in kinds and "result" in kinds and "card_shown" in kinds
    assert all(e["hash"] and isinstance(e["summary"], str) for e in log["entries"])
    assert log["verify"] == {"valid": True, "first_bad_seq": None, "reason": None}
    assert log["head"] == run["log_head"]

    plain = client.post(f"/runs/{run['run_id']}/log/verify").json()
    assert plain["valid"] is True
    assert plain["tampered_copy"] is False


def test_tamper_is_detected_on_a_copy_and_the_real_log_is_untouched(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    run_id = run["run_id"]
    before = client.get(f"/runs/{run_id}/log").json()

    result = client.post(f"/runs/{run_id}/log/verify", json={"tamper": True}).json()
    assert result["valid"] is False
    assert result["tampered_copy"] is True
    assert result["first_bad_seq"] == result["tampered_seq"]
    assert result["reason"] == "entry_hash_mismatch"
    assert result["real_log_valid"] is True

    assert client.get(f"/runs/{run_id}/log").json() == before
    clean = client.post(f"/runs/{run_id}/log/verify", json={"tamper": False}).json()
    assert clean["valid"] is True


def test_log_of_an_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/runs/none/log").status_code == 404
    assert client.post("/runs/none/log/verify", json={}).status_code == 404


def test_the_oldest_runs_are_dropped_past_the_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs_module, "MAX_RUNS", 1)
    row = _scenarios(client, limit=1)[0]
    first = _post_run(client, row["scenario_id"])
    second = _post_run(client, row["scenario_id"])
    assert client.get(f"/runs/{first['run_id']}/log").status_code == 404
    assert client.get(f"/runs/{second['run_id']}/log").status_code == 200


# --- evaluation ----------------------------------------------------------------


def _measure(**changes: Any) -> dict[str, Any]:
    return {
        "name": "Fallback rate",
        "compared_against": "reported as measured",
        "evidence_class": "rules_only",
        "status": "measured",
        "value": 0.25,
        "unit": "",
        "k": 1,
        "n": 4,
        "ci_low": 0.05,
        "ci_high": 0.7,
        "note": "",
        "meta": {"commit": "abc1234", "mode": "off", "seed": 7},
        **changes,
    }


def test_evaluation_with_no_output_is_marked_not_yet_run(client: TestClient) -> None:
    assert client.get("/evaluation").json() == {
        "status": "not_yet_run",
        "rows": [],
        "limits": [],
    }


def test_evaluation_reads_output_without_changing_a_number(
    client: TestClient, results: Path
) -> None:
    report = {
        "panels": [
            {
                "measures": [
                    _measure(),
                    _measure(name="Unguarded violations", k=None, value=3, unit="rows"),
                    _measure(name="Control", status="NOT_REACHED", value=None),
                ]
            }
        ],
        "limits": ["Simulated outcomes on 2015 data."],
    }
    (results / "latest_off_all.json").write_text(json.dumps(report))
    body = client.get("/evaluation").json()
    assert body["status"] == "ok"
    assert body["limits"] == ["Simulated outcomes on 2015 data."]
    first, unguarded, control = body["rows"]
    assert first["value"] == "1/4"
    assert first["interval"] == [0.05, 0.7]
    assert first["evidence_class"] == "rules_only"
    assert (first["commit"], first["mode"], first["seed"]) == ("abc1234", "off", 7)
    assert first["arm"] == "guarded"
    assert unguarded["arm"] == "unguarded_model"
    assert unguarded["value"] == "3 rows"
    assert control["value"] == "NOT_REACHED"


def test_broken_evaluation_output_shows_no_numbers(
    client: TestClient, results: Path
) -> None:
    (results / "latest_off_all.json").write_text("{ not json")
    assert client.get("/evaluation").json() == {
        "status": "unreadable",
        "rows": [],
        "limits": [],
    }
    (results / "latest_off_all.json").write_text(json.dumps({"panels": [{}]}))
    assert client.get("/evaluation").json()["status"] == "unreadable"


def test_the_default_service_does_not_touch_the_dataset_at_import() -> None:
    service = RunService(Settings())
    assert service.catalogue._entries is None
