"""One final decision per run, file-backed log checks, and a server-held package."""

import ast
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api as api_package
from app.negotiation import dot, protocol
from app.negotiation import signoff as signoff_module
from app.negotiation.options import PackageBoundError
from app.negotiation.protocol import run_unguarded
from app.negotiation.scenario import build_scenario
from tests.api.test_routes import (
    _deal_run,
    _post_run,
    _scenarios,
    _sign,
    _signoff_body,
)
from tests.negotiation.test_agents import FakeBlock, FakeMessage

MANAGER = "Duty manager (demo, not authenticated)"
PRIVATE_TEXT = "Free text that must never be shown as a fact"


def _no_deal_run(client: TestClient) -> dict[str, Any]:
    base = _deal_run(client)
    runways = [r["id"] for r in base["airport"]["runways"]]
    run = _post_run(client, base["scenario_id"], closed_runways=runways)
    assert run["decision"]["kind"] == "NO_DEAL"
    return run


def _reject(client: TestClient, run: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/runs/{run['run_id']}/reject", json={"decided_by": MANAGER, **body}
    )


def _take_over(client: TestClient, run: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/runs/{run['run_id']}/take-over", json={"decided_by": MANAGER, **body}
    )


def _log(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"/runs/{run['run_id']}/log").json()
    return body


def _file_payloads(logs: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    lines = (logs / f"{run['run_id']}.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


# --- happy paths ---------------------------------------------------------------


def test_reject_logs_the_plan_and_issues_nothing(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    response = _reject(client, run, reason=PRIVATE_TEXT)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["final_decision"] == "REJECTED"

    log = _log(client, run)
    assert log["head"] == body["log_head"]
    assert log["verify"]["valid"] is True
    assert log["entries"][-1]["kind"] == "plan_rejected"
    # Recorded for the evidence, labelled, and not shown as a fact anywhere.
    assert PRIVATE_TEXT not in json.dumps(log)
    assert PRIVATE_TEXT not in response.text
    payload = _file_payloads(logs, run)[-1]["payload"]
    assert payload["package_id"] == run["decision"]["terms_hash"]
    assert payload["card_hash"] == run["card"]["card_hash"]
    assert payload["decided_by"] == MANAGER
    assert payload["unverified_reason"] == PRIVATE_TEXT
    assert payload["issued"] is False


def test_reject_needs_no_reason_and_does_not_re_run_the_rules(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    gate = run["decision"]["package"]["gate_id"]
    # The plan now breaks a rule. Rejecting it is still allowed: it issues nothing.
    client.post(f"/runs/{run['run_id']}/state", json={"closed_gates": [gate]})
    assert _reject(client, run).json()["status"] == "REJECTED"


def test_take_over_logs_the_type_of_no_deal(client: TestClient, logs: Path) -> None:
    run = _no_deal_run(client)
    response = _take_over(client, run, note=PRIVATE_TEXT)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "TAKEN_OVER"
    log = _log(client, run)
    assert log["head"] == body["log_head"]
    assert log["verify"]["valid"] is True
    assert log["entries"][-1]["kind"] == "case_taken_over"
    assert "NOTHING_LEGAL" in log["entries"][-1]["summary"]
    assert PRIVATE_TEXT not in json.dumps(log)
    payload = _file_payloads(logs, run)[-1]["payload"]
    assert payload["reason_type"] == "NOTHING_LEGAL"
    assert payload["unverified_note"] == PRIVATE_TEXT


def test_system_fault_stays_distinct_when_a_case_is_taken_over(
    client: TestClient, logs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import runs as runs_module
    from app.negotiation.contracts import NoDeal, NoDealReason

    row = _scenarios(client, limit=1)[0]
    real = runs_module.run_negotiation

    def faulted(*args: Any, **kwargs: Any) -> Any:
        result = real(*args, **kwargs)
        fault = NoDeal(
            reason_type=NoDealReason.SYSTEM_FAULT,
            binding_rule_ids=(),
            eliminations=(),
            packages_considered=0,
            nearest_package=None,
            nearest_violations=(),
            reason="injected by this test",
        )
        return result.model_copy(update={"decision": fault, "path": "no_deal"})

    monkeypatch.setattr(runs_module, "run_negotiation", faulted)
    run = _post_run(client, row["scenario_id"])
    assert _take_over(client, run).json()["status"] == "TAKEN_OVER"
    assert _file_payloads(logs, run)[-1]["payload"]["reason_type"] == "SYSTEM_FAULT"
    assert "SYSTEM_FAULT" in _log(client, run)["entries"][-1]["summary"]


# --- one final decision --------------------------------------------------------


def test_approve_after_reject_is_refused_with_nothing_issued(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    _reject(client, run)
    result = _sign(client, run)
    assert result["status"] == "REFUSED_ALREADY_DECIDED"
    assert result["final_decision"] == "REJECTED"
    assert result["airline_decisions"] == []
    assert result["requests"] == []
    assert result["card_hash"] == run["card"]["card_hash"]
    log = _log(client, run)
    assert result["log_head"] == log["head"]
    assert log["entries"][-1]["kind"] == "decision_refused"
    assert not any(e["kind"] == "signoff" for e in log["entries"])


def test_reject_after_approve_is_refused(client: TestClient) -> None:
    run = _deal_run(client)
    assert _sign(client, run)["status"] == "APPROVED"
    body = _reject(client, run).json()
    assert body["status"] == "REFUSED_ALREADY_DECIDED"
    assert body["final_decision"] == "APPROVED"
    kinds = [e["kind"] for e in _log(client, run)["entries"]]
    assert "plan_rejected" not in kinds


def test_a_refused_signoff_is_not_a_decision_so_reject_still_works(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    gate = run["decision"]["package"]["gate_id"]
    client.post(f"/runs/{run['run_id']}/state", json={"closed_gates": [gate]})
    assert _sign(client, run)["status"] == "REFUSED_STATE_CHANGED"
    assert _reject(client, run).json()["status"] == "REJECTED"


def test_replaying_an_approval_keeps_signoffs_own_status(client: TestClient) -> None:
    run = _deal_run(client)
    assert _sign(client, run)["status"] == "APPROVED"
    assert _sign(client, run)["status"] == "REFUSED_ALREADY_USED"


def test_a_second_approval_at_a_new_state_is_refused(client: TestClient) -> None:
    """A fresh token cannot approve a run twice, even if every other check passes."""
    run = _deal_run(client)
    assert _sign(client, run)["status"] == "APPROVED"
    other = next(
        g["id"]
        for g in run["airport"]["gates"]
        if g["id"] != run["decision"]["package"]["gate_id"]
    )
    changed = client.post(
        f"/runs/{run['run_id']}/state", json={"closed_gates": [other]}
    ).json()
    result = _sign(
        client,
        run,
        state_version_seen=changed["state_version"],
        field_versions_seen=changed["field_versions"],
    )
    assert result["status"] == "REFUSED_ALREADY_DECIDED"
    assert result["requests"] == []


def test_double_decisions_are_refused(client: TestClient) -> None:
    run = _deal_run(client)
    assert _reject(client, run).json()["status"] == "REJECTED"
    again = _reject(client, run).json()
    assert again["status"] == "REFUSED_ALREADY_DECIDED"
    assert again["final_decision"] == "REJECTED"

    case = _no_deal_run(client)
    assert _take_over(client, case).json()["status"] == "TAKEN_OVER"
    second = _take_over(client, case).json()
    assert second["status"] == "REFUSED_ALREADY_DECIDED"
    assert second["final_decision"] == "TAKEN_OVER"
    kinds = [e["kind"] for e in _log(client, case)["entries"]]
    assert kinds.count("case_taken_over") == 1


def test_the_wrong_decision_for_the_run_is_a_typed_error_with_no_log_entry(
    client: TestClient,
) -> None:
    deal = _deal_run(client)
    before = _log(client, deal)
    response = _take_over(client, deal)
    assert response.status_code == 409
    assert response.json()["code"] == "WRONG_DECISION_KIND"
    assert _log(client, deal) == before

    case = _no_deal_run(client)
    before = _log(client, case)
    response = _reject(client, case)
    assert response.status_code == 409
    assert response.json()["code"] == "WRONG_DECISION_KIND"
    assert _log(client, case) == before


def test_decisions_validate_input_and_the_run(client: TestClient) -> None:
    run = _deal_run(client)
    blank = client.post(f"/runs/{run['run_id']}/reject", json={"decided_by": "  "})
    assert blank.status_code == 422
    long = _reject(client, run, reason="x" * 2001)
    assert long.status_code == 422
    missing = client.post("/runs/none/reject", json={"decided_by": MANAGER})
    assert missing.status_code == 404
    missing = client.post("/runs/none/take-over", json={"decided_by": MANAGER})
    assert missing.status_code == 404


def test_racing_decisions_leave_exactly_one_final_decision(client: TestClient) -> None:
    run = _deal_run(client)
    statuses: list[str] = []
    start = threading.Barrier(12)

    def approve() -> None:
        start.wait()
        statuses.append(_sign(client, run)["status"])

    def reject() -> None:
        start.wait()
        statuses.append(_reject(client, run).json()["status"])

    threads = [threading.Thread(target=f) for f in (approve, reject) * 6]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(s in ("APPROVED", "REJECTED") for s in statuses) == 1
    log = _log(client, run)
    assert log["verify"]["valid"] is True
    final = [
        e
        for e in log["entries"]
        if e["kind"] == "plan_rejected"
        or (e["kind"] == "signoff" and "APPROVED" in e["summary"])
    ]
    assert len(final) == 1


def test_a_failed_log_write_is_not_a_decision(client: TestClient, logs: Path) -> None:
    run = _deal_run(client)
    aside = logs.parent / "logs-aside"
    logs.rename(aside)
    logs.write_text("a file where the directory was")
    failing = TestClient(client.app, raise_server_exceptions=False)
    response = _reject(failing, run)
    assert response.status_code == 503
    assert "nothing was issued" in response.json()["detail"]
    logs.unlink()
    aside.rename(logs)
    assert _reject(failing, run).json()["status"] == "REJECTED"
    assert _log(client, run)["verify"]["valid"] is True


def test_a_log_edited_on_disk_refuses_decisions_and_issues_nothing(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    path = logs / f"{run['run_id']}.jsonl"
    original = path.read_text()
    path.write_text(original + original.splitlines()[0] + "\n")

    failing = TestClient(client.app, raise_server_exceptions=False)
    for response in (
        _reject(failing, run),
        failing.post(f"/runs/{run['run_id']}/signoff", json=_signoff_body(run)),
    ):
        assert response.status_code == 409
        assert response.json()["code"] == "LOG_INTEGRITY"
        assert "nothing was issued" in response.json()["detail"]

    # Neither attempt counted as the run's decision.
    path.write_text(original)
    assert _sign(failing, run)["status"] == "APPROVED"


def test_a_package_the_scenario_cannot_show_it_offered_is_not_eligible(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _deal_run(client)

    def over_bound(_: Any) -> None:
        raise PackageBoundError("over the bound")

    monkeypatch.setattr(signoff_module, "enumerate_packages", over_bound)
    result = _sign(client, run)
    assert result["status"] == "REFUSED_NOT_ELIGIBLE"
    assert result["airline_decisions"] == []
    assert result["requests"] == []
    # A refusal is not the run's decision.
    assert _reject(client, run).json()["status"] == "REJECTED"


def test_how_a_plan_was_reached_comes_from_the_result_and_the_client_cannot_set_it(
    client: TestClient,
) -> None:
    run = _deal_run(client)
    assert run["card"]["how_reached"] == "fallback"
    faulted = _post_run(client, run["scenario_id"], "recorded")
    assert faulted["card"]["how_reached"] == "fallback_after_fault"
    # It is in the card hash, so the two plans' cards differ.
    assert faulted["card"]["card_hash"] != run["card"]["card_hash"]

    response = client.post(
        f"/runs/{run['run_id']}/signoff",
        json={**_signoff_body(run), "reached": "consensus"},
    )
    assert response.status_code == 422


def test_a_faulted_fallback_signs_off_against_the_card_it_showed(
    client: TestClient,
) -> None:
    base = _deal_run(client)
    run = _post_run(client, base["scenario_id"], "recorded")
    assert run["card"]["how_reached"] == "fallback_after_fault"
    assert _sign(client, run)["status"] == "APPROVED"


# --- the log, from the file ----------------------------------------------------


@pytest.mark.parametrize("decision", ["approve", "reject", "take_over"])
def test_each_decision_verifies_and_tampering_with_it_is_detected(
    client: TestClient, decision: str
) -> None:
    if decision == "approve":
        run = _deal_run(client)
        _sign(client, run)
    elif decision == "reject":
        run = _deal_run(client)
        _reject(client, run)
    else:
        run = _no_deal_run(client)
        _take_over(client, run)
    log = _log(client, run)
    assert log["verify"]["valid"] is True
    plain = client.post(f"/runs/{run['run_id']}/log/verify").json()
    assert plain["valid"] is True

    tampered = client.post(
        f"/runs/{run['run_id']}/log/verify", json={"tamper": True}
    ).json()
    last = len(log["entries"]) - 1
    assert tampered["valid"] is False
    assert tampered["tampered_seq"] == last
    assert tampered["first_bad_seq"] == last
    assert tampered["reason"] == "entry_hash_mismatch"
    assert tampered["real_log_valid"] is True
    assert _log(client, run) == log


def test_verification_reads_the_file_so_an_edit_on_disk_is_caught(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    _reject(client, run, reason="original")
    path = logs / f"{run['run_id']}.jsonl"
    lines = path.read_text().splitlines()
    entry = json.loads(lines[-1])
    entry["payload"]["decided_by"] = "Someone else"
    lines[-1] = json.dumps(entry)
    path.write_text("\n".join(lines) + "\n")

    expected = len(lines) - 1
    verified = client.post(f"/runs/{run['run_id']}/log/verify").json()
    assert verified["valid"] is False
    assert verified["first_bad_seq"] == expected
    assert verified["real_log_valid"] is False
    log = _log(client, run)
    assert log["verify"]["valid"] is False
    assert "Someone else" in log["entries"][-1]["summary"]


def test_a_truncated_file_fails_the_anchor_and_a_garbled_one_is_malformed(
    client: TestClient, logs: Path
) -> None:
    run = _deal_run(client)
    path = logs / f"{run['run_id']}.jsonl"
    content = path.read_text()

    path.write_text("")
    verified = client.post(f"/runs/{run['run_id']}/log/verify").json()
    assert verified == {
        **verified,
        "valid": False,
        "reason": "anchor_not_found",
    }

    path.write_text("not json\n")
    garbled = client.post(f"/runs/{run['run_id']}/log/verify").json()
    assert garbled["valid"] is False
    assert garbled["reason"] == "malformed_entry"
    assert _log(client, run)["verify"]["valid"] is False

    path.write_text(content)
    assert client.post(f"/runs/{run['run_id']}/log/verify").json()["valid"] is True


# --- the package comes from the server -----------------------------------------


def test_signoff_cannot_carry_a_package_from_the_client(client: TestClient) -> None:
    run = _deal_run(client)
    body = {
        "terms_hash": run["decision"]["terms_hash"],
        "state_version_seen": run["state_version"],
        "card_hash_seen": run["card"]["card_hash"],
        "decided_by": MANAGER,
        "airline_decisions_approved": True,
        "requests_to_send": True,
        "package": {
            "slot": {"runway_id": "R1", "time_min": 1},
            "gate_id": "G1",
            "action": "hold",
        },
    }
    response = client.post(f"/runs/{run['run_id']}/signoff", json=body)
    assert response.status_code == 422
    kinds = [e["kind"] for e in _log(client, run)["entries"]]
    assert "signoff" not in kinds


class _UnguardedClient:
    """A fake transport: picks the first offered package, legal or not."""

    def with_options(self, **_: Any) -> "_UnguardedClient":
        return self

    @property
    def beta(self) -> "_UnguardedClient":
        return self

    @property
    def messages(self) -> "_UnguardedClient":
        return self

    def create(self, **_: Any) -> FakeMessage:
        body = {
            "chosen_package_id": "P01",
            "reason_codes": ["other"],
            "model_note": "",
        }
        return FakeMessage(content=(FakeBlock("text", json.dumps(body)),))


def test_an_unguarded_pick_cannot_be_signed_through_a_run(client: TestClient) -> None:
    run = _deal_run(client)
    row = next(
        r
        for r in dot.iter_eligible_rows()
        if build_scenario(r).scenario_id.value == run["scenario_id"]
    )
    unguarded = run_unguarded(build_scenario(row), "live", client=_UnguardedClient())
    assert unguarded.package is not None
    assert unguarded.eligible_for_signoff is False
    assert unguarded.package.terms_hash != run["decision"]["terms_hash"]

    result = _sign(client, run, terms_hash=unguarded.package.terms_hash)
    assert result["status"] == "REFUSED_PACKAGE_CHANGED"
    assert result["airline_decisions"] == []
    assert result["requests"] == []


def test_the_routes_cannot_create_a_signable_unguarded_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No route calls the arm, no body can ask for it, and the API never names it."""

    def forbidden(*_: Any, **__: Any) -> None:
        raise AssertionError("a route reached the unguarded arm")

    monkeypatch.setattr(protocol, "run_unguarded", forbidden)
    row = _scenarios(client, limit=1)[0]
    for mode in ("off", "recorded"):
        _post_run(client, row["scenario_id"], mode)
    for body in (
        {"scenario_id": row["scenario_id"], "mode": "unguarded"},
        {"scenario_id": row["scenario_id"], "mode": "off", "arm": "unguarded_baseline"},
    ):
        assert client.post("/runs", json=body).status_code == 422

    assert api_package.__file__ is not None
    for path in Path(api_package.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text())
        names = {
            node.name if isinstance(node, ast.alias) else node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.alias | ast.Name)
        }
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert not (names | attributes) & {"run_unguarded", "UnguardedResult"}, path
