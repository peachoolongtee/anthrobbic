"""The evaluation harness, on local fakes of `dot`, `scenario` and `protocol`.

The fakes follow the agreed interfaces. Tests using them prove the harness, not
those modules. No test here makes a model call.
"""

import importlib.util
import json
import random
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.negotiation import evaluate as ev
from app.negotiation import rules as rules_registry
from app.negotiation.baselines import PackageMetrics
from app.negotiation.contracts import (
    Deal,
    NoDeal,
    Package,
    Provenance,
    Runway,
    Scenario,
    Sourced,
)
from app.negotiation.fallback import decide
from app.negotiation.options import PackageBoundError, enumerate_packages
from app.negotiation.rules import check_package
from app.negotiation.utility import CostWeights, weight_sensitivity
from tests.negotiation.factories import random_scenario

_COMMAND_PATH = Path(__file__).parents[2] / "scripts" / "evaluate.py"
_COMMAND_SPEC = importlib.util.spec_from_file_location(
    "evaluate_command", _COMMAND_PATH
)
assert _COMMAND_SPEC is not None and _COMMAND_SPEC.loader is not None
evaluate_command = importlib.util.module_from_spec(_COMMAND_SPEC)
_COMMAND_SPEC.loader.exec_module(evaluate_command)

HOT_DESTINATIONS = [f"D{i:02d}" for i in range(40)]


@dataclass(frozen=True)
class FakeRow:
    year: int
    month: int
    day: int
    airline: str
    flight_number: int
    origin_airport: str
    destination_airport: str
    scheduled_departure: int


@dataclass(frozen=True)
class FakeOutcome:
    arrival_delay: int | None
    arrival_min: int | None


@dataclass(frozen=True)
class FakeBasis:
    basis: str


@dataclass(frozen=True)
class FakeParams:
    p_next_leg_hard: float = 0.35
    gate_util_base: float = 0.35
    surplus_pre_departure_min: tuple[int, int] = (30, 90)
    p_planned_gate_conflict: float = 0.5


@dataclass(frozen=True)
class FakeNegotiation:
    decision: Deal | NoDeal
    path: str
    turns_used: int
    faults: tuple[str, ...]
    model_calls: int
    events: tuple[()] = ()


@dataclass(frozen=True)
class FakeUnguarded:
    package: Package | None
    model_calls: int = 1


def fake_sample_rows(
    n: int, seed: int, cause: str | None = None, path: str | None = None
) -> list[FakeRow]:
    rng = random.Random(f"{seed}-{cause}")
    months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12]
    return [
        FakeRow(
            year=2015,
            month=rng.choice(months),
            day=rng.randrange(1, 29),
            airline="AA",
            flight_number=rng.randrange(1, 9_999) * 10 + (cause == ev.CAUSE_WEATHER),
            origin_airport="ORG",
            destination_airport=rng.choice(HOT_DESTINATIONS),
            scheduled_departure=i,
        )
        for i in range(n)
    ]


FAKE_PARAMS = FakeParams()


def fake_build_scenario(
    row: FakeRow,
    seed: int = 0,
    path: str | None = None,
    params: FakeParams = FAKE_PARAMS,
) -> Scenario:
    scenario = random_scenario(hash((row.flight_number, row.day, seed)) % 100_000)
    # A generator knob that really moves the outcome: at 0.7 nothing is legal.
    if params.p_next_leg_hard == 0.7:
        return scenario.model_copy(
            update={"runways": Sourced(value=(), provenance=Provenance.SYNTHETIC)}
        )
    return scenario


def fake_outcome_of(row: FakeRow) -> FakeOutcome:
    # Scheduled arrival at minute 50, so a real delay of 30 lands at 80.
    return FakeOutcome(arrival_delay=30, arrival_min=80)


def fake_earliest_basis(row: FakeRow, path: str | None = None) -> FakeBasis:
    return FakeBasis("inbound_leg" if row.day % 2 else "disruption_floor")


class FakeProtocol:
    """Mode off is the real fallback. Other modes agree on the second-cheapest
    legal package when there is one, so a consensus row has a real cost gap."""

    def __init__(self, calls_per_run: int = 6) -> None:
        self.calls_per_run = calls_per_run
        self.modes: Counter[str] = Counter()
        self.scripted_modes: Counter[str] = Counter()
        self.unguarded_modes: Counter[str] = Counter()

    def run_negotiation(
        self, scenario: Scenario, mode: str, sink: Any = None, client: Any = None
    ) -> FakeNegotiation:
        # A scripted client is a control with no model behind it, so count apart.
        scripted = isinstance(client, ev.ScriptedAgentClient)
        (self.scripted_modes if scripted else self.modes)[mode] += 1
        decision = decide(scenario)
        if isinstance(client, ev.ScriptedAgentClient) and client.hostile:
            path = ev.PATH_FALLBACK if isinstance(decision, Deal) else ev.PATH_NO_DEAL
            return FakeNegotiation(decision, path, 1, ("hallucinated",), 3)
        if mode == ev.MODE_OFF:
            path = ev.PATH_FALLBACK if isinstance(decision, Deal) else ev.PATH_NO_DEAL
            return FakeNegotiation(decision, path, 0, ("llm_off",), 0)
        if isinstance(decision, NoDeal):
            return FakeNegotiation(decision, ev.PATH_NO_DEAL, 2, (), self.calls_per_run)
        return FakeNegotiation(decision, ev.PATH_CONSENSUS, 1, (), self.calls_per_run)

    def run_unguarded(
        self, scenario: Scenario, mode: str, sink: Any = None, client: Any = None
    ) -> FakeUnguarded:
        self.unguarded_modes[mode] += 1
        packages = enumerate_packages(scenario)
        return FakeUnguarded(package=packages[0] if packages else None)


def fake_backends(protocol: FakeProtocol | None = None) -> ev.Backends:
    fake = protocol or FakeProtocol()
    return ev.Backends(
        sample_rows=fake_sample_rows,
        build_scenario=fake_build_scenario,
        outcome_of=fake_outcome_of,
        earliest_basis=fake_earliest_basis,
        generator_params=FakeParams(),
        run_negotiation=fake.run_negotiation,
        run_unguarded=fake.run_unguarded,
    )


def _meta(mode: str = "off", split: str = "none") -> ev.RunMeta:
    return ev.collect_meta(mode, split, 0, 10)


def _measures(report: ev.Report) -> dict[tuple[str, str], ev.Measure]:
    return {(p.title, m.name): m for p in report.panels for m in p.measures}


def _by_name(report: ev.Report, name: str) -> list[ev.Measure]:
    return [m for p in report.panels for m in p.measures if m.name == name]


# --- Numbers and labels -----------------------------------------------------


def test_wilson_matches_worked_values() -> None:
    low, high = ev.wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)
    low, high = ev.wilson_interval(0, 30)
    assert low == 0.0
    assert high == pytest.approx(0.1135, abs=1e-3)
    low, high = ev.wilson_interval(20, 20)
    assert low == pytest.approx(0.8389, abs=1e-3)
    assert high == 1.0


@pytest.mark.parametrize(("k", "n"), [(0, 0), (-1, 5), (6, 5)])
def test_wilson_refuses_nonsense(k: int, n: int) -> None:
    with pytest.raises(ValueError):
        ev.wilson_interval(k, n)


def test_panel_refuses_a_measure_of_another_class() -> None:
    meta = _meta()
    live = ev.PanelBuilder(ev.EvidenceClass.LIVE, "x", meta)
    live.rate("a rate", 1, 2)
    with pytest.raises(ValidationError):
        ev.Panel(
            evidence_class=ev.EvidenceClass.RECORDED,
            title="mixed",
            meta=meta,
            measures=tuple(live.measures),
        )


def test_a_rate_with_no_trials_is_not_reached_rather_than_zero() -> None:
    builder = ev.PanelBuilder(ev.EvidenceClass.TEST, "x", _meta())
    builder.rate("empty", 0, 0, empty_reason="did not run")
    measure = builder.build().measures[0]
    assert measure.status is ev.MeasureStatus.NOT_REACHED
    assert measure.value is None
    assert measure.note == "did not run"
    assert measure.display_value() == "NOT_REACHED"


def test_meta_is_generated_from_the_repository() -> None:
    meta = _meta()
    assert len(meta.commit) == 40
    assert meta.generated_at.endswith("+00:00")


def test_every_evidence_class_in_the_plan_exists() -> None:
    assert {c.value for c in ev.EvidenceClass} == {
        "unseen",
        "tuned",
        "recorded",
        "live",
        "rules_only",
        "test",
    }


@pytest.mark.parametrize(
    ("mode", "split", "number", "expected"),
    [
        ("off", "none", 0, ev.EvidenceClass.RULES_ONLY),
        ("off", "frozen", 0, ev.EvidenceClass.RULES_ONLY),
        ("recorded", "frozen", 0, ev.EvidenceClass.RECORDED),
        ("live", "tune", 0, ev.EvidenceClass.TUNED),
        ("live", "frozen", 1, ev.EvidenceClass.UNSEEN),
        ("live", "frozen", 2, ev.EvidenceClass.LIVE),
        ("live", "none", 0, ev.EvidenceClass.LIVE),
    ],
)
def test_evidence_class_of_a_run(
    mode: str, split: str, number: int, expected: ev.EvidenceClass
) -> None:
    assert ev.llm_evidence_class(mode, split, number) is expected


# --- Controls and mutation --------------------------------------------------


def test_every_registered_rule_has_an_injected_case() -> None:
    covered = {case.rule_id for case in ev.injected_cases()}
    assert covered == set(rules_registry.rule_ids())


@pytest.mark.parametrize("case", ev.injected_cases(), ids=lambda c: c.case_id)
def test_injected_case_breaks_only_its_rule_and_is_defended(
    case: ev.InjectedCase,
) -> None:
    fired = {v.rule_id for v in check_package(case.scenario, case.unsafe)}
    assert fired == {case.rule_id}
    assert ev.run_injected_case(case).defended


def test_every_rule_is_defended_through_the_decision_path() -> None:
    results = [ev.run_injected_case(c) for c in ev.injected_cases()]
    statuses = ev.rule_control_statuses(results, rules_registry.rule_ids())
    assert set(statuses.values()) == {ev.ControlStatus.DEFENDED}


def test_disabling_a_rule_is_noticed_and_then_restored() -> None:
    case = next(c for c in ev.injected_cases() if c.rule_id == "ATC-RWY-CLOSED")
    original = rules_registry.ALL_RULES
    assert decide(case.scenario).package != case.unsafe  # type: ignore[union-attr]
    with ev.disabled_rule("ATC-RWY-CLOSED"):
        assert not check_package(case.scenario, case.unsafe)
        assert decide(case.scenario).package == case.unsafe  # type: ignore[union-attr]
    assert rules_registry.ALL_RULES is original


def test_a_rule_is_restored_even_if_the_body_raises() -> None:
    original = rules_registry.ALL_RULES
    with pytest.raises(RuntimeError), ev.disabled_rule("GND-GATE-SIZE"):
        raise RuntimeError("boom")
    assert rules_registry.ALL_RULES is original


def test_disabling_an_unknown_rule_is_an_error() -> None:
    with pytest.raises(KeyError):
        with ev.disabled_rule("NOT-A-RULE"):
            pass


def test_a_rule_with_no_case_is_not_reached_not_defended() -> None:
    statuses = ev.rule_control_statuses([], ["NEW-RULE"])
    assert statuses == {"NEW-RULE": ev.ControlStatus.NOT_REACHED}


def test_a_case_masked_by_a_second_rule_is_a_blind_spot() -> None:
    """If another rule also rejects the package, disabling the target proves
    nothing. The harness must say so."""
    base = next(c for c in ev.injected_cases() if c.rule_id == "ATC-RWY-CLOSED")
    masked = replace(
        base,
        scenario=base.scenario.model_copy(
            update={"fuel_on_board_kg": base.scenario.trip_fuel_kg}
        ),
    )
    result = ev.run_injected_case(masked)
    assert not result.isolated
    assert not result.passes_gate_when_disabled
    assert not result.defended
    statuses = ev.rule_control_statuses([result], ["ATC-RWY-CLOSED"])
    assert statuses == {"ATC-RWY-CLOSED": ev.ControlStatus.BLIND_SPOT}


def test_a_rule_only_the_gate_can_see_is_defended_at_the_gate() -> None:
    base = next(c for c in ev.injected_cases() if c.rule_id == "GND-GATE-SIZE")
    gate_only = ev.run_injected_case(
        replace(base, decision_stage=False, gate_only=True)
    )
    statuses = ev.rule_control_statuses([gate_only], ["GND-GATE-SIZE"])
    assert statuses == {"GND-GATE-SIZE": ev.ControlStatus.DEFENDED}


def test_a_case_that_never_ran_the_decision_is_not_reached() -> None:
    base = next(c for c in ev.injected_cases() if c.rule_id == "GND-GATE-SIZE")
    gate_only = ev.run_injected_case(replace(base, decision_stage=False))
    statuses = ev.rule_control_statuses([gate_only], ["GND-GATE-SIZE"])
    assert statuses == {"GND-GATE-SIZE": ev.ControlStatus.NOT_REACHED}


@pytest.mark.parametrize("control", ev.expected_controls(), ids=lambda c: c.control_id)
def test_expected_controls_hold_on_the_fallback(control: ev.ExpectedControl) -> None:
    assert ev.control_matches(control, decide(control.scenario))


def test_a_refuse_everything_system_fails_the_positive_controls() -> None:
    """Usefulness beside safety: a system that never deals must not pass."""
    refuse = decide(ev.control_scenario(gates=None))
    positives = [c for c in ev.expected_controls() if c.expected_package is not None]
    assert positives
    assert not any(ev.control_matches(c, refuse) for c in positives)


# --- Input sensitivity ------------------------------------------------------


def test_input_sensitivity_on_a_real_decision() -> None:
    pairs = {p.pair: p for p in ev.input_sensitivity(ev.control_scenario())}
    assert set(pairs) == set(ev.SENSITIVITY_PAIRS)
    assert pairs["close_chosen_runway"].status is ev.PairStatus.CHANGED
    assert pairs["close_other_runway"].status is ev.PairStatus.UNAFFECTED_WITH_REASON
    assert "28R" in pairs["close_other_runway"].reason
    assert pairs["close_all_runways"].status is ev.PairStatus.CHANGED
    assert pairs["unrelated_far_arrival"].status is (
        ev.PairStatus.UNAFFECTED_WITH_REASON
    )
    assert pairs["unrelated_far_gate_use"].status is (
        ev.PairStatus.UNAFFECTED_WITH_REASON
    )
    assert pairs["reorder_input_lists"].status is ev.PairStatus.UNAFFECTED_WITH_REASON


def test_a_decider_blind_to_state_fails_the_runway_pairs() -> None:
    frozen = decide(ev.control_scenario())
    pairs = {
        p.pair: p for p in ev.input_sensitivity(ev.control_scenario(), lambda _: frozen)
    }
    assert pairs["close_chosen_runway"].status is ev.PairStatus.FAILED
    assert pairs["close_all_runways"].status is ev.PairStatus.FAILED


def test_a_decider_that_reacts_to_unrelated_traffic_fails() -> None:
    base = ev.control_scenario()
    other = ev._pkg(runway_id="28R")

    def jumpy(scenario: Scenario) -> Deal | NoDeal:
        decision = decide(scenario)
        arrivals = scenario.other_arrivals.value or ()
        if isinstance(decision, Deal) and any(
            a.flight_id == "UNRELATED" for a in arrivals
        ):
            return decision.model_copy(update={"package": other})
        return decision

    pairs = {p.pair: p for p in ev.input_sensitivity(base, jumpy)}
    assert pairs["unrelated_far_arrival"].status is ev.PairStatus.FAILED


def test_sensitivity_with_no_deal_is_not_reached() -> None:
    closed = (Runway(runway_id="28L", closed=True, parallel_group=None),)
    pairs = ev.input_sensitivity(ev.control_scenario(runways=closed))
    assert {p.status for p in pairs} == {ev.PairStatus.NOT_REACHED}


def test_unrelated_gate_use_lies_past_a_late_next_departure() -> None:
    """Found on real rows: the aircraft holds the gate until a departure 650 minutes
    past the window, so a use at 600 was a real conflict and not unrelated."""
    late = ev.control_scenario(next_departure_min=120 + 650)
    pairs = {p.pair: p for p in ev.input_sensitivity(late)}
    assert pairs["unrelated_far_gate_use"].status is (
        ev.PairStatus.UNAFFECTED_WITH_REASON
    )
    # The rule was right to object to a use inside that stay.
    inside = ev.GateOccupancy(gate_id="A1", flight_id="X", start_min=720, end_min=750)
    held = ev.control_scenario(next_departure_min=770, gate_occupancies=(inside,))
    rule_ids = {v.rule_id for v in check_package(held, ev._pkg())}
    assert "GND-GATE-OVERLAP" in rule_ids


def test_sensitivity_with_one_runway_cannot_close_another() -> None:
    open_one = (Runway(runway_id="28L", closed=False, parallel_group=None),)
    pairs = {
        p.pair: p for p in ev.input_sensitivity(ev.control_scenario(runways=open_one))
    }
    assert pairs["close_other_runway"].status is ev.PairStatus.NOT_REACHED
    assert pairs["close_chosen_runway"].status is ev.PairStatus.CHANGED


def test_sensitivity_holds_on_random_scenarios() -> None:
    statuses: Counter[str] = Counter()
    for seed in range(150):
        try:
            pairs = ev.input_sensitivity(random_scenario(seed, small=True))
        except PackageBoundError:
            continue
        for pair in pairs:
            assert pair.status is not ev.PairStatus.FAILED, (seed, pair)
            statuses[pair.status.value] += 1
    assert statuses[ev.PairStatus.CHANGED.value] > 0


# --- Weights ----------------------------------------------------------------


def test_fast_weight_sensitivity_matches_utility() -> None:
    """The faster re-weighing must agree with the public implementation."""
    variants = ev.alternate_weights()
    compared = 0
    for seed in range(60):
        scenario = random_scenario(seed, small=True)
        decision = decide(scenario)
        if not isinstance(decision, Deal):
            continue
        legal = [
            p for p in enumerate_packages(scenario) if not check_package(scenario, p)
        ]
        fast = ev._weight_changes(scenario, legal, decision.package)
        for name, weights in variants.items():
            assert fast[name] == weight_sensitivity(scenario, weights).changed
            compared += 1
    assert compared > 0


def test_weight_sensitivity_can_fire() -> None:
    """A measure that can never fire would prove nothing. Here A1 is busy, so the
    default moves to B1 for 50, against 400 of hold fuel to wait for A1. A gate move
    at 10 times the weight costs 500, so the choice flips to waiting."""
    busy = (ev.GateOccupancy(gate_id="A1", flight_id="O", start_min=60, end_min=100),)
    scenario = ev.control_scenario(gate_occupancies=busy)
    decision = decide(scenario)
    assert isinstance(decision, Deal)
    assert decision.package == ev._pkg(gate_id="B1")
    legal = [p for p in enumerate_packages(scenario) if not check_package(scenario, p)]
    fast = ev._weight_changes(scenario, legal, decision.package)
    assert fast["per_gate_move x10"] is True
    assert fast["per_gate_move x2"] is False
    variants = ev.alternate_weights()
    for name, weights in variants.items():
        assert fast[name] == weight_sensitivity(scenario, weights).changed, name


def _legal(scenario: Scenario) -> list[Package]:
    return [p for p in enumerate_packages(scenario) if not check_package(scenario, p)]


def test_pick_dominates_when_nothing_is_better_on_any_component() -> None:
    scenario = ev.control_scenario()
    decision = decide(scenario)
    assert isinstance(decision, Deal)
    assert ev.pick_dominates(scenario, _legal(scenario), decision.package) is True


def test_pick_does_not_dominate_when_a_real_trade_off_exists() -> None:
    """Moving to B1 costs a gate move; waiting for A1 costs fuel. Neither wins on
    every component, which is the case the weight sweep exists to expose."""
    busy = (ev.GateOccupancy(gate_id="A1", flight_id="O", start_min=60, end_min=100),)
    scenario = ev.control_scenario(gate_occupancies=busy)
    decision = decide(scenario)
    assert isinstance(decision, Deal)
    assert ev.pick_dominates(scenario, _legal(scenario), decision.package) is False


def test_pick_dominance_with_no_pick_is_none() -> None:
    assert ev.pick_dominates(ev.control_scenario(), [], None) is None


def test_live_schedule_is_the_planned_count() -> None:
    assert dict(ev.live_call_schedule()) == {
        "tune": 60,
        "first frozen (negotiation + unguarded)": 140,
        "second frozen": 120,
        "re-record TURN2-CONFLICT (outside this harness)": 6,
    }
    assert sum(calls for _, calls in ev.live_call_schedule()) == 326
    harness = sum(calls for _, calls in ev.live_call_schedule()[:3])
    assert harness == ev.LIVE_CALL_CEILING


def test_controls_reach_the_real_protocol_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On the merged tree the gate controls must run, not report NOT_REACHED."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    backends = ev.load_backends()
    assert backends.run_negotiation is not None
    panel, failures = ev.controls_panel(_meta(), backends)
    assert not failures
    reached_only_by_a_person = {
        "Hand-calculated scenarios checked by someone who did not write the code"
    }
    missed = {
        m.name for m in panel.measures if m.status is ev.MeasureStatus.NOT_REACHED
    }
    assert missed == reached_only_by_a_person


def test_alternate_weights_scale_each_weight_both_ways() -> None:
    variants = ev.alternate_weights()
    assert len(variants) == 4 * len(CostWeights.model_fields)
    assert variants["per_gate_move x10"].per_gate_move == 500
    assert variants["fuel_per_kg /10"].fuel_per_kg == 1  # floored, never zero


# --- Frozen split -----------------------------------------------------------


def _pools(seed: int = ev.SPLIT_SEED, size: int = 600) -> dict[str, list[FakeRow]]:
    return {c: fake_sample_rows(size, seed, cause=c) for c in ev.CAUSES}


def _entries(split: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [e for e in split["rows"] if e["role"] == role]


def test_split_sizes_and_balance() -> None:
    split = ev.build_split(_pools())
    assert len(_entries(split, "tune")) == 10
    assert len(_entries(split, "frozen")) == 20
    for role, per_cause in (("tune", 5), ("frozen", 10)):
        causes = Counter(e["cause"] for e in _entries(split, role))
        assert causes == {
            ev.CAUSE_WEATHER: per_cause,
            ev.CAUSE_LATE_AIRCRAFT: per_cause,
        }


def test_split_holds_out_by_season_and_destination() -> None:
    split = ev.build_split(_pools())
    tune = _entries(split, "tune")
    frozen = _entries(split, "frozen")
    assert {e["month"] for e in tune} <= set(range(1, 7))
    assert {e["month"] for e in frozen} <= {7, 8, 9, 11, 12}
    assert not {e["destination"] for e in tune} & {e["destination"] for e in frozen}
    grouping = split["grouping"]
    assert grouping["excluded_month"] == 10
    assert grouping["tune_months"] == [1, 2, 3, 4, 5, 6]
    assert grouping["frozen_months"] == [7, 8, 9, 11, 12]
    assert set(grouping["tune_destinations"]) == {e["destination"] for e in tune}
    assert set(grouping["frozen_destinations"]) == {e["destination"] for e in frozen}


def test_split_is_deterministic_for_a_seed_and_differs_by_seed() -> None:
    assert ev.build_split(_pools()) == ev.build_split(_pools())
    assert ev.build_split(_pools(), seed=1)["rows"] != ev.build_split(_pools())["rows"]


def test_split_ignores_pool_order() -> None:
    pools = _pools()
    shuffled = {c: list(reversed(rows)) for c, rows in pools.items()}
    assert ev.build_split(pools)["rows"] == ev.build_split(shuffled)["rows"]


def test_split_drops_a_row_sampled_under_both_causes() -> None:
    pools = _pools()
    shared = pools[ev.CAUSE_WEATHER][0]
    pools[ev.CAUSE_LATE_AIRCRAFT][0] = shared
    split = ev.build_split(pools)
    assert ev.row_key(shared) not in {e["key"] for e in split["rows"]}


def test_split_refuses_a_pool_that_cannot_fill_it() -> None:
    with pytest.raises(ev.SplitError, match="raise the pool size"):
        ev.build_split(_pools(size=8))


def test_split_refuses_a_pool_of_only_october_or_winter() -> None:
    pools = {c: [replace(r, month=2) for r in rows] for c, rows in _pools().items()}
    with pytest.raises(ev.SplitError, match="frozen"):
        ev.build_split(pools)


@pytest.mark.parametrize(
    ("role", "change"),
    [
        ("frozen", {"month": 10}),
        ("frozen", {"month": 3}),
        ("tune", {"month": 7}),
        ("frozen", {"cause": ev.CAUSE_WEATHER}),
    ],
)
def test_a_stored_split_breaking_a_property_is_refused(
    role: str, change: dict[str, Any]
) -> None:
    split = ev.build_split(_pools())
    next(e for e in split["rows"] if e["role"] == role and e["cause"] != "x").update(
        change
    )
    if change.get("cause"):
        late = next(
            e
            for e in split["rows"]
            if e["role"] == role and e["cause"] == ev.CAUSE_LATE_AIRCRAFT
        )
        late["cause"] = ev.CAUSE_WEATHER
    split["split_hash"] = ev._split_payload_hash(split)
    with pytest.raises(ev.SplitError):
        ev.validate_split(split)


def test_a_stored_split_sharing_a_destination_is_refused() -> None:
    split = ev.build_split(_pools())
    _entries(split, "frozen")[0]["destination"] = _entries(split, "tune")[0][
        "destination"
    ]
    split["split_hash"] = ev._split_payload_hash(split)
    with pytest.raises(ev.SplitError, match="share destinations"):
        ev.validate_split(split)


def test_an_edited_split_fails_its_hash(tmp_path: Path) -> None:
    ev.ensure_split(tmp_path, fake_backends())
    path = tmp_path / ev.FROZEN_SPLIT_FILE
    stored = json.loads(path.read_text())
    stored["rows"][0]["destination"] = "EDITED"
    path.write_text(json.dumps(stored))
    with pytest.raises(ev.SplitError, match="hash"):
        ev.ensure_split(tmp_path, fake_backends())


def test_an_old_split_without_grouping_must_be_regenerated(tmp_path: Path) -> None:
    ev.ensure_split(tmp_path, fake_backends())
    path = tmp_path / ev.FROZEN_SPLIT_FILE
    stored = json.loads(path.read_text())
    del stored["grouping"]
    stored["split_hash"] = ev._split_payload_hash(stored)
    path.write_text(json.dumps(stored))
    with pytest.raises(ev.SplitError, match="regenerate"):
        ev.ensure_split(tmp_path, fake_backends())
    split, _ = ev.ensure_split(tmp_path, fake_backends(), regenerate=True)
    assert "grouping" in split


def test_split_is_written_once_and_reused(tmp_path: Path) -> None:
    first, pools = ev.ensure_split(tmp_path, fake_backends())
    second, _ = ev.ensure_split(tmp_path, fake_backends())
    assert first == second
    rows = ev.rows_for_role(first, "frozen", pools)
    assert len(rows) == 20
    assert Counter(cause for cause, _ in rows) == {
        ev.CAUSE_WEATHER: 10,
        ev.CAUSE_LATE_AIRCRAFT: 10,
    }


def test_split_rows_missing_from_the_data_are_an_error(tmp_path: Path) -> None:
    split, _ = ev.ensure_split(tmp_path, fake_backends())
    other = {c: fake_sample_rows(600, 999, cause=c) for c in ev.CAUSES}
    with pytest.raises(ev.SplitError, match="not found"):
        ev.rows_for_role(split, "frozen", other)


def test_regenerating_is_refused_after_a_live_frozen_run(tmp_path: Path) -> None:
    ev.ensure_split(tmp_path, fake_backends())
    ev.claim_run(tmp_path, _meta("live", "frozen"), 140)
    with pytest.raises(ev.SplitError, match="cannot be regenerated"):
        ev.ensure_split(tmp_path, fake_backends(), regenerate=True)


# --- Guard and budget -------------------------------------------------------


def test_the_call_ceiling_is_the_planned_320() -> None:
    assert ev.LIVE_CALL_CEILING == 320
    ledger = ev._empty_ledger()
    assert ev.plan_live_calls("tune", 10, ledger).total == 60
    first = ev.plan_live_calls("frozen", 20, ledger)
    assert (first.negotiation_calls, first.unguarded_calls) == (120, 20)
    ledger["runs"].append(
        {
            "mode": "live",
            "split": "frozen",
            "status": "completed",
            "planned_calls": 140,
            "actual_calls": 140,
        }
    )
    assert ev.plan_live_calls("frozen", 20, ledger).unguarded_calls == 0
    assert ev.plan_live_calls("frozen", 20, ledger).total == 120


def test_live_needs_an_explicit_covering_confirmation() -> None:
    plan = ev.plan_live_calls("frozen", 20, ev._empty_ledger())
    with pytest.raises(ev.LiveCallsNotConfirmed, match="--confirm-live-calls 140"):
        ev.check_live_confirmation(plan, None)
    with pytest.raises(ev.LiveCallsNotConfirmed, match="does not cover"):
        ev.check_live_confirmation(plan, 139)
    ev.check_live_confirmation(plan, 140)


def test_third_live_frozen_run_is_refused_unless_forced(tmp_path: Path) -> None:
    meta = _meta("live", "frozen")
    first, number = ev.claim_run(tmp_path, meta, 10)
    assert number == 1
    ev.complete_run(tmp_path, first, None, 10)
    _, number = ev.claim_run(tmp_path, meta, 10)
    assert number == 2
    with pytest.raises(ev.FrozenRescoreRefused, match="--force-frozen-rescore"):
        ev.claim_run(tmp_path, meta, 10)
    assert len(ev.load_ledger(tmp_path)["runs"]) == 2  # a refusal spends nothing
    forced, number = ev.claim_run(tmp_path, meta, 10, force=True)
    assert number == 3
    runs = ev.load_ledger(tmp_path)["runs"]
    assert next(r for r in runs if r["run_id"] == forced)["forced"] is True


def test_a_crashed_run_still_counts_and_stays_charged(tmp_path: Path) -> None:
    meta = _meta("live", "frozen")
    run_id, _ = ev.claim_run(tmp_path, meta, 140)
    ev.complete_run(tmp_path, run_id, None, None, status="failed")
    ledger = ev.load_ledger(tmp_path)
    assert ledger["runs"][0]["status"] == "failed"
    assert ev._calls_charged(ledger) == 140
    assert ledger["first_frozen_score"] is None
    _, number = ev.claim_run(tmp_path, meta, 120)
    assert number == 2


def test_other_modes_are_recorded_but_do_not_spend_the_runs(tmp_path: Path) -> None:
    for mode in ("off", "recorded", "recorded", "off"):
        _, number = ev.claim_run(tmp_path, _meta(mode, "frozen"), 0)
        assert number == 0
    ledger = ev.load_ledger(tmp_path)
    assert len(ledger["runs"]) == 4
    assert ev._live_frozen_runs(ledger) == []


def test_the_ceiling_refuses_runs_that_would_pass_320(tmp_path: Path) -> None:
    meta = _meta("live", "none")
    ev.claim_run(tmp_path, meta, 300)
    with pytest.raises(ev.FrozenRescoreRefused, match="ceiling"):
        ev.claim_run(tmp_path, meta, 21)
    ev.claim_run(tmp_path, meta, 20)


def test_a_corrupt_ledger_fails_closed(tmp_path: Path) -> None:
    (tmp_path / ev.FROZEN_LEDGER_FILE).write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        ev.claim_run(tmp_path, _meta("live", "frozen"), 10)


def test_first_score_is_preserved_even_if_poor(tmp_path: Path) -> None:
    meta = _meta("live", "frozen")
    poor = {"overall": {"consensus": 0.0}}
    good = {"overall": {"consensus": 1.0}}
    first, _ = ev.claim_run(tmp_path, meta, 10)
    ev.complete_run(tmp_path, first, poor, 10)
    second, _ = ev.claim_run(tmp_path, meta, 10)
    ledger = ev.complete_run(tmp_path, second, good, 10)
    assert ledger["first_frozen_score"]["score"] == poor
    assert ledger["first_frozen_score"]["run_id"] == first
    runs = {r["run_id"]: r["score"] for r in ledger["runs"]}
    assert runs == {first: poor, second: good}


def test_recorded_scores_never_become_the_first_score(tmp_path: Path) -> None:
    run_id, _ = ev.claim_run(tmp_path, _meta("recorded", "frozen"), 0)
    ledger = ev.complete_run(tmp_path, run_id, {"overall": {}}, 0)
    assert ledger["first_frozen_score"] is None


@pytest.mark.parametrize(
    ("mode", "split", "number", "expected"),
    [
        ("live", "frozen", 1, True),
        ("live", "frozen", 2, False),
        ("live", "tune", 0, False),
        ("live", "none", 0, False),
        ("recorded", "frozen", 0, True),
        ("off", "frozen", 0, False),
    ],
)
def test_unguarded_runs_once_on_frozen_rows(
    mode: str, split: str, number: int, expected: bool
) -> None:
    assert ev.unguarded_may_run(mode, split, number) is expected


# --- Arms and scoring -------------------------------------------------------


def _rows(n: int = 12) -> list[tuple[str, FakeRow]]:
    rows = []
    for index, row in enumerate(fake_sample_rows(n, 5, cause=ev.CAUSE_WEATHER)):
        rows.append((ev.CAUSES[index % 2], row))
    return rows


def test_llm_budget_stops_before_spending_more() -> None:
    fake = FakeProtocol()
    rows = ev.run_llm_arm(_rows(5), "live", fake_backends(fake), budget=12)
    assert [r.reached for r in rows] == [True, True, False, False, False]
    assert fake.modes["live"] == 2


def test_llm_error_is_counted_and_charged_rather_than_dropped() -> None:
    def boom(*_: Any, **__: Any) -> None:
        raise TimeoutError("late")

    backends = replace(fake_backends(), run_negotiation=boom)
    rows = ev.run_llm_arm(_rows(1), "recorded", backends)
    assert rows[0].path == ev.PATH_ERROR
    assert "TimeoutError" in (rows[0].error or "")
    assert rows[0].model_calls == ev.CALLS_PER_SCENARIO
    assert ev.score_llm_group(rows)["error"]["k"] == 1


def test_cost_gap_is_only_for_consensus() -> None:
    scenario = ev.control_scenario()
    best = decide(scenario)
    assert isinstance(best, Deal)
    dearer = ev._pkg(gate_id="A1", time_min=105, action=ev.FlightPlanAction.HOLD)
    dear_deal = best.model_copy(update={"package": dearer})
    consensus = ev._llm_row(
        "a", "weather", scenario, FakeNegotiation(dear_deal, "consensus", 1, (), 6)
    )
    fallback = ev._llm_row(
        "b", "weather", scenario, FakeNegotiation(dear_deal, "fallback", 2, ("x",), 6)
    )
    score = ev.score_llm_group([consensus, fallback])
    assert score["consensus_cost_gap_n"] == 1
    assert score["consensus_cost_gap_mean"] > 0
    assert consensus.same_package_as_fallback is False
    only_fallback = ev.score_llm_group([fallback])
    assert only_fallback["consensus_cost_gap_mean"] is None
    assert only_fallback["consensus_cost_gap_n"] == 0


def test_cost_gap_without_consensus_is_not_reached_in_the_panel() -> None:
    scenario = ev.control_scenario()
    best = decide(scenario)
    assert isinstance(best, Deal)
    row = ev._llm_row(
        "b", "weather", scenario, FakeNegotiation(best, "fallback", 2, ("x",), 6)
    )
    panel, _ = ev.llm_panel([row], ev.EvidenceClass.RECORDED, _meta("recorded"), "t")
    gap = next(
        m for m in panel.measures if m.name == "Cost gap of consensus to best package"
    )
    assert gap.status is ev.MeasureStatus.NOT_REACHED


def test_gate_breach_by_the_protocol_is_a_failure() -> None:
    scenario = ev.control_scenario()
    best = decide(scenario)
    assert isinstance(best, Deal)
    unsafe = ev._pkg(gate_id="A2")  # regional gate, narrow-body aircraft
    bad = best.model_copy(update={"package": unsafe})
    row = ev._llm_row(
        "b", "weather", scenario, FakeNegotiation(bad, "consensus", 1, (), 6)
    )
    assert row.final_violations == ("GND-GATE-SIZE",)
    _, failures = ev.llm_panel([row], ev.EvidenceClass.RECORDED, _meta("recorded"), "t")
    assert any("break a rule" in failure for failure in failures)


def test_a_fault_raised_by_all_three_agents_counts_once_per_row() -> None:
    """Found on a real replay: three agents missing a recording crashed the rate."""
    row = ev.LlmRow(
        key="k",
        cause=ev.CAUSE_WEATHER,
        reached=True,
        path=ev.PATH_FALLBACK,
        faults=("recording_miss", "recording_miss", "recording_miss"),
    )
    panel, _ = ev.llm_panel([row], ev.EvidenceClass.RECORDED, _meta("recorded"), "t")
    fault = next(m for m in panel.measures if m.name == "Fault: recording_miss")
    assert (fault.k, fault.n) == (1, 1)


def test_a_missed_recording_is_not_a_failure_to_converge() -> None:
    missed = ev.LlmRow(
        key="k",
        cause=ev.CAUSE_WEATHER,
        reached=True,
        path=ev.PATH_FALLBACK,
        faults=("recording_miss",),
        model_calls=3,
    )
    assert not missed.model_answered
    panel, _ = ev.llm_panel([missed], ev.EvidenceClass.RECORDED, _meta("recorded"), "t")
    named = {m.name: m for m in panel.measures}
    assert named["Convergence rate, all rows"].status is ev.MeasureStatus.NOT_REACHED
    assert named["Turns used"].status is ev.MeasureStatus.NOT_REACHED
    assert named["Rows a model answered, all rows"].k == 0
    assert ev.score_llm_group([missed])["consensus"]["n"] == 0


def _no_key_backends(fake: FakeProtocol) -> ev.Backends:
    def no_key(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        if mode == ev.MODE_LIVE:
            path = ev.PATH_FALLBACK
            return FakeNegotiation(decide(scenario), path, 0, ("missing_key",), 0)
        return fake.run_negotiation(scenario, mode, **_)

    return replace(fake_backends(fake), run_negotiation=no_key)


def test_a_live_run_with_no_key_spends_no_planned_run_and_sets_no_score(
    tmp_path: Path,
) -> None:
    """Otherwise a forgotten key would freeze 0% as the permanent first score."""
    fake = FakeProtocol()
    request = _request(
        tmp_path, mode="live", split="frozen", confirm_live_calls=140, synthetic_seeds=1
    )
    ev.run_evaluation(request, _no_key_backends(fake))
    ledger = ev.load_ledger(tmp_path)
    assert ledger["runs"][0]["status"] == ev.RUN_NO_MODEL
    assert ledger["first_frozen_score"] is None
    assert ev._live_frozen_runs(ledger) == []
    assert ev.plan_live_calls("frozen", 20, ledger).unguarded_calls == 20
    report = ev.run_evaluation(request, fake_backends(fake))
    assert report.first_frozen_score is not None
    assert report.first_frozen_score["frozen_live_run_number"] == 1
    assert any(
        p.evidence_class is ev.EvidenceClass.UNSEEN
        and p.title.startswith("Frozen score")
        for p in report.panels
    )


def test_turn_and_call_caps_are_checked() -> None:
    row = ev.LlmRow(
        key="k",
        cause="weather",
        reached=True,
        path="fallback",
        turns_used=3,
        model_calls=9,
    )
    panel, failures = ev.llm_panel(
        [row], ev.EvidenceClass.RECORDED, _meta("recorded"), "t"
    )
    assert any("turn cap" in f for f in failures)
    assert any("call cap" in f for f in failures)
    over = next(m for m in panel.measures if m.name == "Runs over the turn cap")
    assert over.status is ev.MeasureStatus.FAILED


def test_unguarded_scores_with_rules_and_harm() -> None:
    fake = FakeProtocol()
    backends = fake_backends(fake)
    rows = ev.run_unguarded_arm(_rows(30), "recorded", backends)
    assert fake.unguarded_modes["recorded"] == 30
    assert any(r.violated_rule_ids for r in rows)  # the first package is often illegal
    assert any(r.harmful for r in rows)


def test_unguarded_budget_and_errors() -> None:
    fake = FakeProtocol()
    rows = ev.run_unguarded_arm(_rows(4), "live", fake_backends(fake), budget=2)
    assert [r.reached for r in rows] == [True, True, False, False]

    def boom(*_: Any, **__: Any) -> None:
        raise ValueError("bad")

    rows = ev.run_unguarded_arm(
        _rows(1), "recorded", replace(fake_backends(), run_unguarded=boom)
    )
    assert "ValueError" in (rows[0].error or "")


def test_unguarded_with_no_protocol_is_not_reached() -> None:
    backends = replace(fake_backends(), run_unguarded=None)
    rows = ev.run_unguarded_arm(_rows(1), "recorded", backends)
    panel = ev.guarded_vs_unguarded_panel(
        [], rows, ev.EvidenceClass.RECORDED, _meta("recorded")
    )
    named = {m.name: m for m in panel.measures}
    assert (
        named["Unguarded packages breaking a rule, all rows"].status
        is ev.MeasureStatus.NOT_REACHED
    )


def test_frozen_score_reports_overall_and_each_type_with_sizes() -> None:
    rows = [
        ev.LlmRow(
            key="a",
            cause=ev.CAUSE_WEATHER,
            reached=True,
            path="consensus",
            model_calls=3,
        ),
        ev.LlmRow(
            key="b",
            cause=ev.CAUSE_WEATHER,
            reached=True,
            path="fallback",
            model_calls=6,
        ),
        ev.LlmRow(key="c", cause=ev.CAUSE_LATE_AIRCRAFT, reached=True, path="no_deal"),
        ev.LlmRow(key="d", cause=ev.CAUSE_LATE_AIRCRAFT, reached=False),
    ]
    score = ev.frozen_score(rows)
    assert score["overall"]["n_planned"] == 4
    assert score["overall"]["n_reached"] == 3
    weather = score["by_disruption_type"][ev.CAUSE_WEATHER]
    assert weather["consensus"]["k"] == 1
    assert weather["consensus"]["n"] == 2
    assert score["by_disruption_type"][ev.CAUSE_LATE_AIRCRAFT]["n_reached"] == 1


# --- Whole runs -------------------------------------------------------------


def _request(tmp_path: Path, **kwargs: Any) -> ev.RunRequest:
    return ev.RunRequest(results_dir=tmp_path, **kwargs)


def test_mode_off_runs_no_model_and_marks_model_measures_not_reached(
    tmp_path: Path,
) -> None:
    fake = FakeProtocol()
    report = ev.run_evaluation(
        _request(tmp_path, sample=12, synthetic_seeds=2), fake_backends(fake)
    )
    assert set(fake.modes) == {ev.MODE_OFF}
    assert not fake.unguarded_modes
    for name in (
        "Convergence rate",
        "Turns used",
        "Cost gap of consensus to best package",
        "LLM versus fallback on the same rows",
        "Unguarded arm violation rate",
    ):
        statuses = {m.status for m in _by_name(report, name)}
        assert statuses == {ev.MeasureStatus.NOT_REACHED}, name
    assert not report.failures
    assert report.meta.sample_size == 12


def test_mode_off_table_has_a_class_and_meta_on_every_number(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=10, seed=3, synthetic_seeds=2), fake_backends()
    )
    classes = {panel.evidence_class for panel in report.panels}
    assert classes == {ev.EvidenceClass.RULES_ONLY, ev.EvidenceClass.TEST}
    for panel in report.panels:
        for measure in panel.measures:
            assert measure.evidence_class is panel.evidence_class
            assert measure.meta.commit
            assert measure.meta.generated_at
            assert measure.meta.seed == 3
            if measure.k is not None:
                assert measure.ci_low is not None and measure.ci_high is not None


def test_mode_off_reports_the_plan_measures(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=30, synthetic_seeds=2), fake_backends()
    )
    names = {m.name for p in report.panels for m in p.measures}
    required = {
        "Context: simulated arrival delay, inbound data set the window",
        "Context: real ARRIVAL_DELAY, disruption floor set the window",
        "first_come_first_served: packages breaking a rule",
        "human_heuristic: packages breaking a rule",
        "Delay past the scenario's earliest arrival, fallback",
        "Delay past the scenario's earliest arrival, fallback minus "
        "first_come_first_served, paired on the same window",
        "Delay past the scenario's earliest arrival, fallback minus "
        "human_heuristic, paired on the same window",
        "Fuel-reserve margin, first_come_first_served, all its packages",
        "Connection passengers at risk, human_heuristic, only its legal packages",
        "Ground overtime, first_come_first_served, only its legal packages",
        "Chosen package changes under at least one alternate weight",
        "Chosen package changes across synthetic seeds",
        "Input sensitivity, close_chosen_runway",
        "Input sensitivity, unrelated_far_arrival",
        "Fallback rate (LLM off)",
        "Final packages the independent harm check calls harmful",
        "Controls that must succeed, through protocol mode off",
        "Rules defended: injected violation caught, and noticed when disabled",
    }
    missing = required - names
    assert not missing
    assert any(n.startswith("Binding: ATC-RWY-CLOSED") for n in names)
    assert any(n.startswith("NO_DEAL SYSTEM_FAULT rate, weather") for n in names)
    assert any(n.startswith("NO_DEAL NOTHING_LEGAL rate, late_aircraft") for n in names)


def test_real_delay_is_context_only_and_split_by_inbound_data(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=80, synthetic_seeds=1), fake_backends()
    )
    measures = [m for p in report.panels for m in p.measures]
    context = [m for m in measures if m.name.startswith("Context:")]
    assert context
    for measure in context:
        assert measure.compared_against == ev.NOT_A_SAVING
    real = [
        m for m in context if m.status is ev.MeasureStatus.MEASURED and "real" in m.name
    ]
    assert {m.value for m in real} == {30.0}
    labels = {m.name for m in real}
    assert "Context: real ARRIVAL_DELAY, inbound data set the window" in labels
    assert "Context: real ARRIVAL_DELAY, disruption floor set the window" in labels
    # A difference against reality would read as a saving, so none is offered.
    assert not [m for m in measures if "minus real" in m.name.lower()]
    assert not [m for m in measures if "ARRIVAL_DELAY" in m.name and m not in context]


def test_simulated_delay_comes_from_the_schedule_in_the_outcome() -> None:
    package = ev._pkg(time_min=100)
    outcome = FakeOutcome(arrival_delay=30, arrival_min=80)  # scheduled at 50
    assert ev._simulated_delay(outcome, package) == 50.0
    assert ev._simulated_delay(FakeOutcome(None, None), package) is None


def test_paired_difference_uses_the_same_row_and_skips_illegal_baselines() -> None:
    def metrics(delay: int) -> PackageMetrics:
        return PackageMetrics(delay, 0, 0, 0, 0, 0, 0)

    legal = ev.BaselineRow("b", True, (), False, (), metrics(5))
    illegal = ev.BaselineRow("b", True, ("X",), True, (), metrics(0))
    rows = [
        ev.RowResult(key="1", cause="weather", metrics=metrics(15), baselines=(legal,)),
        ev.RowResult(
            key="2", cause="weather", metrics=metrics(9), baselines=(illegal,)
        ),
        ev.RowResult(key="3", cause="weather", metrics=None, baselines=(legal,)),
    ]
    assert ev._paired_differences(rows, "b", "delay_min") == [10.0]


def test_generator_table_shows_the_rate_moving(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=20, synthetic_seeds=1), fake_backends()
    )
    panel = next(p for p in report.panels if "generator parameters" in p.title)
    assert panel.evidence_class is ev.EvidenceClass.RULES_ONLY
    named = {m.name: m for m in panel.measures}
    assert len(named) == 3 * (1 + len(ev.GENERATOR_VARIANTS))
    default = named["NO_DEAL rate, all rows, default parameters"]
    moved = named["NO_DEAL rate, all rows, p_next_leg_hard=0.7"]
    assert default.n == moved.n == 20
    assert moved.value == 1.0  # the fake's knob empties the runways
    assert default.value is not None and default.value < 1.0
    assert "points against default" in moved.note
    for name in ("gate_util_base=0.55", "surplus_pre_departure_min=(-10, 5)"):
        assert f"NO_DEAL rate, weather, {name}" in named


def test_generator_table_is_not_reached_without_parameters(tmp_path: Path) -> None:
    backends = replace(fake_backends(), generator_params=None)
    report = ev.run_evaluation(_request(tmp_path, sample=4), backends)
    panel = next(p for p in report.panels if "generator parameters" in p.title)
    assert [m.status for m in panel.measures] == [ev.MeasureStatus.NOT_REACHED]


def test_generator_sweep_runs_on_an_evenly_spaced_subset() -> None:
    config = ev.RowConfig(synthetic_seeds=1, generator_rows=3)
    results = ev.evaluate_rows(_rows(12), config, fake_backends())
    swept = [i for i, r in enumerate(results) if r.generator]
    assert swept == [0, 4, 8]
    off = ev.RowConfig(synthetic_seeds=1, generator_rows=0)
    assert not any(
        r.generator for r in ev.evaluate_rows(_rows(4), off, fake_backends())
    )


def test_zero_cost_picks_are_reported_with_the_weight_result(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=20, synthetic_seeds=1), fake_backends()
    )
    measure = _by_name(report, "Chosen package has zero soft cost")[0]
    assert measure.status is ev.MeasureStatus.MEASURED
    assert measure.n == _by_name(report, "Final packages breaking a rule")[0].n
    assert _by_name(report, "Legal packages per deal row")[0].unit == "packages"


def test_binding_is_reported_by_decision_point(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=30, synthetic_seeds=1), fake_backends()
    )
    names = {m.name for p in report.panels for m in p.measures}
    assert any(n.startswith("Binding at pre_departure: PLT-FUEL-POLICY") for n in names)


def test_faults_read_as_text_in_every_shape() -> None:
    @dataclass(frozen=True)
    class Record:
        kind: ev.PairStatus

    texts = ev._fault_texts(
        ["plain", ev.PairStatus.FAILED, Record(ev.PairStatus.CHANGED)]
    )
    assert texts == ("plain", "FAILED", "CHANGED")


def test_missing_modules_are_not_reached_and_listed(tmp_path: Path) -> None:
    empty = ev.Backends(missing=("app.negotiation.dot.sample_rows",))
    report = ev.run_evaluation(_request(tmp_path, sample=10), empty)
    assert report.meta.sample_size == 0
    assert report.awaiting == ("app.negotiation.dot.sample_rows",)
    delay = _by_name(
        report, "Context: real ARRIVAL_DELAY, inbound data set the window"
    )[0]
    assert delay.status is ev.MeasureStatus.NOT_REACHED
    assert "dot has not landed" in delay.note
    protocol = _by_name(
        report, "Controls that must succeed, through protocol mode off"
    )[0]
    assert protocol.status is ev.MeasureStatus.NOT_REACHED
    assert not report.failures  # the controls themselves held


def test_decide_only_run_says_the_protocol_did_not_run(tmp_path: Path) -> None:
    backends = replace(fake_backends(), run_negotiation=None, run_unguarded=None)
    report = ev.run_evaluation(
        _request(tmp_path, sample=6, synthetic_seeds=1), backends
    )
    fallback = _by_name(report, "Fallback rate (LLM off)")[0]
    assert fallback.status is ev.MeasureStatus.NOT_REACHED
    assert "fallback.decide ran directly" in fallback.note


def test_a_row_that_raises_is_counted_and_fails_the_run(tmp_path: Path) -> None:
    def boom(row: Any, seed: int = 0) -> Scenario:
        raise RuntimeError("bad row")

    report = ev.run_evaluation(
        _request(tmp_path, sample=4), replace(fake_backends(), build_scenario=boom)
    )
    assert any("rows errored" in f for f in report.failures)
    assert _by_name(report, "Rows that errored")[0].k == 4


def test_mode_off_decision_differing_from_fallback_is_a_failure(tmp_path: Path) -> None:
    fake = FakeProtocol()

    def wrong(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        return FakeNegotiation(
            decide(ev.control_scenario(gates=None)), ev.PATH_NO_DEAL, 0, ("off",), 0
        )

    backends = replace(fake_backends(fake), run_negotiation=wrong)
    report = ev.run_evaluation(
        _request(tmp_path, sample=8, synthetic_seeds=1), backends
    )
    assert any("differ from fallback.decide" in f for f in report.failures)


def test_a_logged_fallback_trigger_counts_as_not_clean() -> None:
    @dataclass(frozen=True)
    class Event:
        kind: str
        payload: dict[str, str]

    @dataclass(frozen=True)
    class Done:
        faults: tuple[str, ...]
        events: tuple[Event, ...]

    assert ev._labelled_not_clean(Done(("x",), ()))
    assert ev._labelled_not_clean(
        Done((), (Event("fallback", {"trigger": "llm_off"}),))
    )
    assert not ev._labelled_not_clean(Done((), (Event("fallback", {}),)))
    assert not ev._labelled_not_clean(Done((), (Event("result", {"trigger": "x"}),)))
    assert not ev._labelled_not_clean(Done((), ()))


def test_scripted_client_answers_in_the_agent_shape_without_a_model() -> None:
    client = ev.ScriptedAgentClient()
    response = client.with_options(timeout=1).beta.messages.create(model="x")
    reply = json.loads(response.content[0].text)
    assert reply["acceptable_package_ids"] == ["P00"] == reply["ranking"]
    hostile = ev.ScriptedAgentClient(hostile=True)
    response = hostile.beta.messages.create()
    assert json.loads(response.content[0].text)["ranking"] == ["P99"]


def test_protocol_gate_control_notices_a_protocol_that_lets_unsafe_through() -> None:
    case = next(c for c in ev.injected_cases() if c.decision_stage)
    template = decide(ev.control_scenario())
    assert isinstance(template, Deal)

    def yes_man(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        # No gate: it always returns the first enumerated package.
        package = enumerate_packages(scenario)[0]
        bad = template.model_copy(update={"package": package})
        return FakeNegotiation(bad, ev.PATH_CONSENSUS, 1, (), 3)

    builder = ev.PanelBuilder(ev.EvidenceClass.TEST, "t", _meta())
    failures: list[str] = []
    backends = replace(fake_backends(), run_negotiation=yes_man)
    ev.protocol_gate_control(backends, builder, failures)
    assert "an unsafe package came out of the protocol gate" in failures
    assert case.rule_id  # the registry supplied a case


def test_protocol_gate_control_is_not_reached_when_replies_cannot_arrive() -> None:
    template = decide(ev.control_scenario())

    def broken(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        return FakeNegotiation(template, ev.PATH_FALLBACK, 0, ("internal_error",), 0)

    builder = ev.PanelBuilder(ev.EvidenceClass.TEST, "t", _meta())
    failures: list[str] = []
    backends = replace(fake_backends(), run_negotiation=broken)
    ev.protocol_gate_control(backends, builder, failures)
    assert {m.status for m in builder.measures} == {ev.MeasureStatus.NOT_REACHED}
    assert not failures


def test_mode_off_logged_as_clean_is_a_failure(tmp_path: Path) -> None:
    def clean(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        decision = decide(scenario)
        path = ev.PATH_FALLBACK if isinstance(decision, Deal) else ev.PATH_NO_DEAL
        return FakeNegotiation(decision, path, 0, (), 0)

    backends = replace(fake_backends(), run_negotiation=clean)
    report = ev.run_evaluation(_request(tmp_path), backends)
    assert any("not logged as a fault" in f for f in report.failures)
    assert any(
        m.name.startswith("Mode off runs labelled") and m.k == 0
        for p in report.panels
        for m in p.measures
    )


def test_recorded_frozen_run_with_guarded_and_unguarded_panels(tmp_path: Path) -> None:
    fake = FakeProtocol()
    report = ev.run_evaluation(
        _request(tmp_path, mode="recorded", split="frozen", synthetic_seeds=1),
        fake_backends(fake),
    )
    assert fake.modes["recorded"] == 20
    assert fake.unguarded_modes["recorded"] == 20
    pair = next(p for p in report.panels if p.title.startswith("Guarded against"))
    assert pair.evidence_class is ev.EvidenceClass.RECORDED
    names = {m.name: m for m in pair.measures}
    unguarded = names["Unguarded packages breaking a rule, all rows"]
    guarded = names["Guarded packages breaking a rule, all rows"]
    assert unguarded.ci_high is not None and guarded.ci_high is not None
    assert guarded.k == 0
    for cause in ev.CAUSES:
        assert f"Unguarded packages breaking a rule, {cause}" in names
    assert report.first_frozen_score is None  # recordings do not set it
    frozen = next(p for p in report.panels if p.title.startswith("Frozen score"))
    assert frozen.evidence_class is ev.EvidenceClass.RECORDED


def test_live_without_confirmation_spends_nothing(tmp_path: Path) -> None:
    fake = FakeProtocol()
    with pytest.raises(ev.LiveCallsNotConfirmed):
        ev.run_evaluation(
            _request(tmp_path, mode="live", split="frozen"), fake_backends(fake)
        )
    assert not fake.modes
    assert not fake.unguarded_modes
    assert ev.load_ledger(tmp_path)["runs"] == []


def test_full_live_plan_on_fakes_stays_within_320(tmp_path: Path) -> None:
    """The planned sequence, end to end, with a fake client."""
    fake = FakeProtocol()
    backends = fake_backends(fake)
    tuned = ev.run_evaluation(
        _request(
            tmp_path,
            mode="live",
            split="tune",
            confirm_live_calls=60,
            synthetic_seeds=1,
        ),
        backends,
    )
    assert any(p.evidence_class is ev.EvidenceClass.TUNED for p in tuned.panels)
    first = ev.run_evaluation(
        _request(
            tmp_path,
            mode="live",
            split="frozen",
            confirm_live_calls=140,
            synthetic_seeds=1,
        ),
        backends,
    )
    assert fake.unguarded_modes["live"] == 20
    assert any(
        p.evidence_class is ev.EvidenceClass.UNSEEN
        and p.title.startswith("Frozen score")
        for p in first.panels
    )
    pair = next(p for p in first.panels if p.title.startswith("Guarded against"))
    assert pair.evidence_class is ev.EvidenceClass.LIVE

    second = ev.run_evaluation(
        _request(
            tmp_path,
            mode="live",
            split="frozen",
            confirm_live_calls=120,
            synthetic_seeds=1,
        ),
        backends,
    )
    assert fake.unguarded_modes["live"] == 20  # run once
    assert fake.modes["live"] == 10 + 20 + 20
    this_run = next(p for p in second.panels if p.title.startswith("Frozen score"))
    assert this_run.evidence_class is ev.EvidenceClass.LIVE
    preserved = next(p for p in second.panels if p.title.startswith("First frozen"))
    assert preserved.evidence_class is ev.EvidenceClass.UNSEEN
    assert second.first_frozen_score is not None
    assert second.first_frozen_score["run_id"] == first.run_id

    ledger = ev.load_ledger(tmp_path)
    assert ev._calls_charged(ledger) == 320
    assert [r["status"] for r in ledger["runs"]] == ["completed"] * 3

    with pytest.raises(ev.FrozenRescoreRefused):
        ev.run_evaluation(
            _request(
                tmp_path,
                mode="live",
                split="frozen",
                confirm_live_calls=120,
                synthetic_seeds=1,
            ),
            backends,
        )
    assert fake.modes["live"] == 50


def test_a_live_run_that_crashes_is_recorded_as_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(*_: Any, **__: Any) -> None:
        raise RuntimeError("worker died")

    monkeypatch.setattr(ev, "run_llm_arm", crash)
    with pytest.raises(RuntimeError):
        ev.run_evaluation(
            _request(
                tmp_path,
                mode="live",
                split="frozen",
                confirm_live_calls=140,
                synthetic_seeds=1,
            ),
            fake_backends(),
        )
    ledger = ev.load_ledger(tmp_path)
    assert ledger["runs"][0]["status"] == "failed"
    assert ev._calls_charged(ledger) == 140


def test_limits_are_stated_automatically(tmp_path: Path) -> None:
    report = ev.run_evaluation(_request(tmp_path, sample=10), fake_backends())
    text = ev.render_markdown(report)
    for phrase in (
        "simulated outcomes",
        "synthetic",
        "no cancelled or diverted",
        "October is excluded",
        "Wilson",
        "Safety rests on the gate",
    ):
        assert phrase in text, phrase
    assert "11.4%" in text  # computed, 0 of 30
    assert "binding counts partly describe our generator" in text
    assert "shows no saving" in text
    assert "assumed approach speed" in text
    assert "reassigned stay on the planned gate on 50% of flights" in text
    assert "before any model output existed" in text


def test_results_are_written_as_json_and_markdown(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=4, seed=9, synthetic_seeds=1), fake_backends()
    )
    stored = json.loads((tmp_path / "latest_off_none.json").read_text())
    assert stored["meta"]["commit"] == report.meta.commit
    assert stored["meta"]["seed"] == 9
    assert stored["panels"][0]["measures"][0]["meta"]["sample_size"] == 4
    assert (tmp_path / "latest_off_none.md").read_text().startswith("# Evaluation")
    assert list(tmp_path.glob("eval_off_none_seed9_*.json"))


def test_row_results_are_stable_for_a_seed() -> None:
    backends = fake_backends()
    rows = _rows(6)
    config = ev.RowConfig(synthetic_seeds=2)
    assert ev.evaluate_rows(rows, config, backends) == ev.evaluate_rows(
        rows, config, backends
    )


def test_process_pool_returns_rows_in_order() -> None:
    """Workers resolve the real modules, so without them each row is a labelled
    error. Order and denominators must still hold."""
    rows = _rows(6)
    results = ev.evaluate_rows(rows, ev.RowConfig(), ev.load_backends(), workers=2)
    assert [r.key for r in results] == [ev.row_key(row) for _, row in rows]


def test_the_command_refuses_live_without_confirmation_and_prints_the_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProtocol()
    monkeypatch.setattr(ev, "load_backends", lambda: fake_backends(fake))
    code = evaluate_command.main(
        ["--mode", "live", "--split", "frozen", "--results-dir", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert code == evaluate_command.EXIT_REFUSED
    assert "Planned live calls: 140" in out
    assert "REFUSED" in out
    assert not fake.modes
    assert not fake.unguarded_modes


def test_the_command_runs_live_only_with_a_covering_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProtocol()
    monkeypatch.setattr(ev, "load_backends", lambda: fake_backends(fake))
    base = ["--mode", "live", "--split", "tune", "--results-dir", str(tmp_path)]
    base += ["--workers", "1", "--synthetic-seeds", "1", "--generator-rows", "0"]
    code = evaluate_command.main([*base, "--confirm-live-calls", "59"])
    assert code == evaluate_command.EXIT_REFUSED
    assert not fake.modes["live"]
    code = evaluate_command.main([*base, "--confirm-live-calls", "60"])
    assert code == evaluate_command.EXIT_OK
    assert fake.modes["live"] == 10
    assert "Planned live calls: 60" in capsys.readouterr().out


def test_the_command_prints_the_live_schedule_and_spends_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProtocol()
    monkeypatch.setattr(ev, "load_backends", lambda: fake_backends(fake))
    assert evaluate_command.main(["--print-live-plan"]) == evaluate_command.EXIT_OK
    out = capsys.readouterr().out
    assert "tune: 60" in out
    assert "second frozen: 120" in out
    assert "total: 326" in out
    assert "TURN2-CONFLICT re-record is 6 calls outside the ledger" in out
    assert not fake.modes


def test_comparison_reads_both_columns_from_the_run_files(tmp_path: Path) -> None:
    before = ev.run_evaluation(
        _request(tmp_path, sample=6, seed=1, synthetic_seeds=1), fake_backends()
    )
    after = ev.run_evaluation(
        _request(tmp_path, sample=8, seed=2, synthetic_seeds=1), fake_backends()
    )
    text = ev.render_comparison(
        before.model_dump(mode="json"), after.model_dump(mode="json"), "Heading"
    )
    assert "sample size 6" in text
    assert "sample size 8" in text
    assert "| Deal rate, all rows |" in text
    old = _by_name(before, "Deal rate, all rows")[0]
    new = _by_name(after, "Deal rate, all rows")[0]
    assert f"| {old.display_value()}, {old.display_interval()} |" in text
    assert f"| {new.display_value()}, {new.display_interval()} |" in text


def test_comparison_says_when_a_run_did_not_measure_something(tmp_path: Path) -> None:
    run = ev.run_evaluation(
        _request(tmp_path, sample=4, synthetic_seeds=1), fake_backends()
    ).model_dump(mode="json")
    older = json.loads(json.dumps(run))
    for panel in older["panels"]:
        panel["measures"] = [
            m for m in panel["measures"] if not m["name"].startswith("Pick is no worse")
        ]
    text = ev.render_comparison(older, run, "Heading")
    assert "not measured in this run" in text


def test_every_comparison_measure_exists_in_a_real_table(tmp_path: Path) -> None:
    report = ev.run_evaluation(
        _request(tmp_path, sample=30, synthetic_seeds=2), fake_backends()
    )
    names = {m.name for p in report.panels for m in p.measures}
    assert not set(ev.COMPARISON_MEASURES) - names


def test_the_command_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    results = ["--results-dir", str(tmp_path), "--workers", "1"]
    empty = ev.Backends(missing=("app.negotiation.dot.sample_rows",))
    monkeypatch.setattr(ev, "load_backends", lambda: empty)
    assert evaluate_command.main(results) == evaluate_command.EXIT_OK
    incomplete = evaluate_command.main(["--sample", "5", *results])
    assert incomplete == evaluate_command.EXIT_INCOMPLETE
    assert evaluate_command.main(["--sample", "-1", *results]) == (
        evaluate_command.EXIT_REFUSED
    )
    assert "Evaluation results" in capsys.readouterr().out

    def clean(scenario: Scenario, mode: str, **_: Any) -> FakeNegotiation:
        return FakeNegotiation(decide(scenario), ev.PATH_FALLBACK, 0, (), 0)

    broken = replace(fake_backends(), run_negotiation=clean)
    monkeypatch.setattr(ev, "load_backends", lambda: broken)
    failed = evaluate_command.main(results)
    assert failed == evaluate_command.EXIT_CONTROL_FAILED


def test_stratified_rows_are_balanced_and_unique() -> None:
    rows = ev.stratified_rows(40, 1, fake_backends())
    assert Counter(c for c, _ in rows) == {
        ev.CAUSE_WEATHER: 20,
        ev.CAUSE_LATE_AIRCRAFT: 20,
    }
    assert len({ev.row_key(r) for _, r in rows}) == 40
