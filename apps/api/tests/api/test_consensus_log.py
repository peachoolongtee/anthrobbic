"""The downloadable consensus log: complete, clean, verifiable and read-only."""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.negotiation.log import LogEntry, verify_entries
from tests.api.conftest import ClientFactory
from tests.api.test_decisions import (
    _log,
    _no_go_run,
    _reject,
    _take_over,
)
from tests.api.test_routes import (
    OUTCOME_FIELDS,
    _deal_run,
    _keys,
    _post_run,
    _record_row,
    _scenarios,
    _sign,
)

FAKE_KEY = "sk-ant-api03-THIS-IS-NOT-A-REAL-KEY-0123456789abcdef"
# The as-flown columns by their file names, which must not appear as text.
HINDSIGHT_COLUMNS = (
    "ARRIVAL_TIME",
    "ARRIVAL_DELAY",
    "WHEELS_ON",
    "WHEELS_OFF",
    "WEATHER_DELAY",
    "LATE_AIRCRAFT_DELAY",
    "DEPARTURE_DELAY",
    "AIR_TIME",
    "ELAPSED_TIME",
    "TAXI_IN",
)
LOCAL_PATH = re.compile(
    r"(?<![\w.:])/(?:Users|home|tmp|var|private|etc|opt|root|mnt)/|[A-Za-z]:\\\\"
)
TOP_LEVEL = {
    "format",
    "run_id",
    "mode",
    "scenario_id",
    "scenario",
    "field_provenance",
    "state_version",
    "field_versions",
    "airport",
    "injection",
    "turns",
    "removed_packages",
    "removed_total",
    "decision",
    "card",
    "how_reached",
    "faults",
    "final_decision",
    "log",
    "evaluation",
}


def _download(client: TestClient, run: dict[str, Any]) -> Any:
    return client.get(f"/runs/{run['run_id']}/consensus-log")


def _document(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    response = _download(client, run)
    assert response.status_code == 200, response.text
    document: dict[str, Any] = response.json()
    return document


def _entries(document: dict[str, Any]) -> list[LogEntry]:
    return [LogEntry.from_dict(e) for e in document["log"]["entries"]]


def _log_path(logs: Path, run: dict[str, Any]) -> Path:
    return logs / f"{run['run_id']}.jsonl"


# --- what the file holds -------------------------------------------------------


def test_a_fallback_run_is_complete_and_names_why(client: TestClient) -> None:
    run = _deal_run(client)
    response = _download(client, run)
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        f'attachment; filename="consensus-log-{run["run_id"]}.json"'
    )
    document = response.json()
    assert set(document) == TOP_LEVEL
    assert document["format"] == "consensus-log/1"
    assert document["run_id"] == run["run_id"]
    assert document["mode"] == "off"
    assert document["scenario"]["scenario_id"] == run["scenario_id"]
    assert document["scenario"]["delay_provenance"] in {"real", "derived", "synthetic"}
    assert set(document["field_provenance"].values()) <= {
        "real",
        "derived",
        "synthetic",
    }
    assert document["decision"] == run["decision"]
    assert document["card"]["card_hash"] == run["card"]["card_hash"]
    assert document["removed_packages"] == run["removed_packages"]
    assert document["removed_total"] == run["removed_total"]
    assert document["faults"] == run["faults"]
    assert document["how_reached"] == {
        "path": "fallback",
        "reached": "fallback_model_off",
        "fallback_trigger": "llm_off",
    }
    assert document["final_decision"] is None
    assert document["log"]["anchored_head"] == run["log_head"]
    assert document["log"]["verify"] == {
        "valid": True,
        "first_bad_seq": None,
        "reason": None,
    }
    # No evaluation output sits beside the test API.
    assert document["evaluation"] is None


def test_a_consensus_run_holds_each_agents_structured_reply(
    make_client: ClientFactory, recordings: Path
) -> None:
    _record_row(recordings, note="Model prose that is not a fact")
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "recorded")
    assert run["path"] == "consensus"
    document = _document(client, run)

    assert document["mode"] == "recorded"
    assert document["how_reached"]["reached"] == "consensus"
    assert document["how_reached"]["fallback_trigger"] is None
    [turn] = document["turns"]
    assert [a["domain"] for a in turn["agents"]] == ["atc", "pilot", "ground"]
    for agent in turn["agents"]:
        assert agent["acceptable_package_ids"]
        assert sorted(agent["ranking"]) == sorted(agent["acceptable_package_ids"])
        assert agent["prompt_hash"]
    assert run["decision"]["terms_hash"] in turn["intersection"]
    # Model prose is evidence in the log, under its unverified key, and is not
    # repeated as a fact anywhere else in the file.
    note = "Model prose that is not a fact"
    in_log = [
        k
        for e in document["log"]["entries"]
        for k, v in e["payload"].items()
        if note in json.dumps(v)
    ]
    assert in_log
    assert set(in_log) == {"unverified_model_note"}
    assert note not in json.dumps({**document, "log": None})


def test_a_no_go_has_no_card_and_a_taken_over_decision(client: TestClient) -> None:
    run = _no_go_run(client)
    before = _document(client, run)
    assert before["decision"]["kind"] == "NO_GO"
    assert before["card"] is None
    assert before["how_reached"]["path"] == "no_go"
    assert before["how_reached"]["reached"] is None
    assert before["final_decision"] is None

    assert _take_over(client, run).json()["status"] == "TAKEN_OVER"
    after = _document(client, run)
    assert after["final_decision"] == "TAKEN_OVER"
    assert after["log"]["entries"][-1]["kind"] == "case_taken_over"
    assert after["log"]["head"] == _log(client, run)["head"]
    # The anchor stays where the run began; the head moved on with the decision.
    assert after["log"]["anchored_head"] == run["log_head"]
    assert after["log"]["head"] != after["log"]["anchored_head"]


def test_it_downloads_in_every_decision_state(client: TestClient) -> None:
    approved = _deal_run(client)
    assert _sign(client, approved)["status"] == "APPROVED"
    rejected = _post_run(client, approved["scenario_id"])
    assert _reject(client, rejected, reason="no").json()["status"] == "REJECTED"
    refused = _post_run(client, approved["scenario_id"])
    assert _reject(client, refused).json()["status"] == "REJECTED"
    _sign(client, refused)  # refused as already decided; the file still builds

    for run, final in (
        (approved, "APPROVED"),
        (rejected, "REJECTED"),
        (refused, "REJECTED"),
    ):
        document = _document(client, run)
        assert document["final_decision"] == final
        assert document["log"]["verify"]["valid"] is True
        kinds = [e["kind"] for e in document["log"]["entries"]]
        assert kinds[-1] in {"signoff", "plan_rejected", "decision_refused"}


def test_an_injected_unsafe_plan_and_a_fault_are_in_the_file(
    make_client: ClientFactory, recordings: Path
) -> None:
    _record_row(recordings)
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    baseline = _post_run(client, row["scenario_id"], "recorded")
    gate = baseline["decision"]["package"]["gate_id"]
    # A changed request misses the recording, so the run has a fault.
    run = _post_run(
        client,
        row["scenario_id"],
        "recorded",
        closed_gates=[gate],
        inject_unsafe="ATC-WAKE-SEP",
    )
    document = _document(client, run)
    assert {f["kind"] for f in document["faults"]} == {"recording_miss"}
    assert document["how_reached"]["reached"] == "fallback_after_fault"
    assert document["injection"]["rule_id"] == "ATC-WAKE-SEP"
    assert any(p["injected"] for p in document["removed_packages"]) == (
        document["injection"]["status"] == "STOPPED"
    )


def test_it_names_the_evaluation_commit_and_mode_when_output_exists(
    make_client: ClientFactory, results: Path
) -> None:
    source = Path(__file__).parents[2] / "eval_results" / "latest_off_none.json"
    shutil.copy(source, results / source.name)
    client = make_client()
    run = _deal_run(client)
    evaluation = _document(client, run)["evaluation"]
    assert evaluation is not None
    assert evaluation["commits"] and evaluation["modes"]
    assert all(re.fullmatch(r"[0-9a-f]{1,12}", c) for c in evaluation["commits"])


# --- nothing it must not hold --------------------------------------------------


@pytest.mark.parametrize("state", ["open", "approved", "rejected", "no_go", "injected"])
def test_no_key_path_or_hindsight_column_is_in_the_file(
    client: TestClient,
    logs: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", FAKE_KEY)
    if state == "no_go":
        run = _no_go_run(client)
    elif state == "injected":
        base = _deal_run(client)
        run = _post_run(client, base["scenario_id"], inject_unsafe="ATC-WAKE-SEP")
    else:
        run = _deal_run(client)
    if state == "approved":
        assert _sign(client, run)["status"] == "APPROVED"
    if state == "rejected":
        assert _reject(client, run, reason="plain words").status_code == 200

    response = _download(client, run)
    assert response.status_code == 200
    text = response.text
    document = response.json()

    assert FAKE_KEY not in text
    assert "sk-ant" not in text
    assert str(tmp_path) not in text
    assert str(logs) not in text
    assert str(Path.home()) not in text
    assert str(Path(__file__).parents[2]) not in text
    assert not LOCAL_PATH.search(text)
    assert ".jsonl" not in text
    assert not _keys(document) & OUTCOME_FIELDS
    for column in HINDSIGHT_COLUMNS:
        # By file name, and as a JSON key. The card's priced "arrival delay" line is
        # a simulated cost of the plan, not the flown column, so it is not matched.
        assert column not in text
        assert f'"{column.lower()}"' not in text
    # Not even the as-flown figures of this row, kept next to its fields.
    assert _keys(document["scenario"]).isdisjoint(OUTCOME_FIELDS)


# --- the entries are the log ---------------------------------------------------


def test_the_entries_verify_against_the_anchored_head_and_the_head(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    assert _sign(client, run)["status"] == "APPROVED"
    document = _document(client, run)
    entries = _entries(document)

    assert verify_entries(entries, document["log"]["anchored_head"]).valid
    assert verify_entries(entries, document["log"]["head"]).valid
    assert verify_entries(entries).valid
    assert entries[-1].entry_hash == document["log"]["head"]
    assert [e["hash"] for e in _log(client, run)["entries"]] == [
        e.entry_hash for e in entries
    ]


def test_an_entry_edited_in_the_file_downloaded_does_not_verify(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    document = _document(client, run)
    document["log"]["entries"][1]["payload"]["tampered"] = True
    result = verify_entries(_entries(document), document["log"]["anchored_head"])
    assert not result.valid
    assert result.first_bad_seq == 1


# --- read-only -----------------------------------------------------------------


def test_downloading_leaves_the_log_and_the_run_unchanged(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    path = _log_path(logs, run)
    file_before = path.read_bytes()
    stat_before = path.stat()
    log_before = _log(client, run)

    first = _download(client, run)
    second = _download(client, run)

    assert first.text == second.text
    assert path.read_bytes() == file_before
    assert path.stat().st_mtime_ns == stat_before.st_mtime_ns
    assert _log(client, run) == log_before
    # A decision still goes through on the same, unchanged log.
    assert _sign(client, run)["status"] == "APPROVED"


def test_downloading_after_a_decision_adds_no_entry(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    assert _reject(client, run).json()["status"] == "REJECTED"
    path = _log_path(logs, run)
    before = path.read_bytes()
    _download(client, run)
    _download(client, run)
    assert path.read_bytes() == before
    assert len(before.splitlines()) == len(_document(client, run)["log"]["entries"])


# --- a log edited on disk ------------------------------------------------------


def _edit_keeping_size_and_time(path: Path) -> None:
    original = path.read_text()
    times = path.stat()
    target = next(c for c in original if c.isdigit())
    swapped = "1" if target != "1" else "2"
    path.write_text(original.replace(target, swapped, 1))
    os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns))


@pytest.mark.parametrize("edit", ["same_size", "appended", "deleted_line", "removed"])
def test_a_log_file_edited_on_disk_is_reported_invalid(
    client: TestClient, logs: Path, edit: str
) -> None:
    run = _deal_run(client)
    path = _log_path(logs, run)
    original = path.read_text()
    lines = original.splitlines(keepends=True)
    if edit == "same_size":
        _edit_keeping_size_and_time(path)
    elif edit == "appended":
        path.write_text(original + lines[0])
    elif edit == "deleted_line":
        path.write_text("".join(lines[:1] + lines[2:]))
    else:
        path.unlink()

    response = _download(client, run)
    assert response.status_code == 200
    log = response.json()["log"]
    assert log["verify"]["valid"] is False
    assert log["verify"]["reason"]
    if edit in {"deleted_line", "appended"}:
        # What is shown is what is on disk, and the chain fails on its own too.
        entries = [LogEntry.from_dict(e) for e in log["entries"]]
        assert not verify_entries(entries, log["anchored_head"]).valid
    # Downloading did not write to the file, and a decision is still refused.
    assert not path.exists() or path.read_text() != original
    failing = TestClient(client.app, raise_server_exceptions=False)
    refused = _reject(failing, run)
    assert refused.status_code == 409
    assert refused.json()["code"] == "LOG_INTEGRITY"


def test_a_log_file_that_cannot_be_parsed_is_reported_invalid(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    path = _log_path(logs, run)
    path.write_text("this is not json\n")
    response = _download(client, run)
    assert response.status_code == 200
    assert response.json()["log"]["verify"]["valid"] is False
    assert path.read_text() == "this is not json\n"


def test_a_restored_log_downloads_valid_again(client: TestClient, logs: Path) -> None:
    run = _deal_run(client)
    path = _log_path(logs, run)
    original = path.read_text()
    path.write_text(original + original.splitlines()[0] + "\n")
    assert _document(client, run)["log"]["verify"]["valid"] is False
    path.write_text(original)
    assert _document(client, run)["log"]["verify"]["valid"] is True


# --- unknown run ---------------------------------------------------------------


def test_an_unknown_run_is_a_404(client: TestClient) -> None:
    response = client.get("/runs/not-a-run/consensus-log")
    assert response.status_code == 404
    assert "Unknown run" in response.json()["detail"]
    assert "content-disposition" not in response.headers
