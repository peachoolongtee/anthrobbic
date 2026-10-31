"""The plans offered to the agents, on the run's view, only when they answered."""

from pathlib import Path

from tests.api.conftest import ClientFactory
from tests.api.test_decisions import _no_go_run
from tests.api.test_routes import _deal_run, _post_run, _record_row, _scenarios


def test_a_recorded_run_lists_what_was_offered_with_the_chosen_plan_marked(
    make_client: ClientFactory, recordings: Path
) -> None:
    _record_row(recordings)
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "recorded")
    assert run["path"] == "consensus"

    plans = run["offered_plans"]
    assert 0 < len(plans) <= 12
    assert len(plans) <= run["packages_legal"]
    [chosen] = [p for p in plans if p["chosen"]]
    package = run["decision"]["package"]
    assert chosen["gate_id"] == package["gate_id"]
    assert chosen["runway_id"] == package["runway_id"]

    # Acceptance can be read across: an agent's accepted names are offered plans.
    names = {p["package"] for p in plans}
    for response in run["turns"][-1]["responses"]:
        assert set(response["accepted"]) <= names

    assert run["original"]["gate_provenance"] == "synthetic"
    assert run["original"]["due_provenance"] == "real"
    assert run["original"]["due"] == row["scheduled_arrival"]


def test_no_table_when_the_agents_did_not_run(make_client: ClientFactory) -> None:
    client = make_client()
    off = _deal_run(client)
    assert off["offered_plans"] == []
    assert off["original"] is not None

    assert _no_go_run(client)["offered_plans"] == []


def test_a_recording_miss_offers_nothing_to_show(make_client: ClientFactory) -> None:
    client = make_client()
    row = _scenarios(client, limit=1)[0]
    run = _post_run(client, row["scenario_id"], "recorded")
    assert {f["kind"] for f in run["faults"]} == {"recording_miss"}
    assert run["offered_plans"] == []
