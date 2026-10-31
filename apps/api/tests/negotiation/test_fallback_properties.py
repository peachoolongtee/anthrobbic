"""Property-style checks on seeded random scenarios.

These show the fallback is self-consistent with the rules: it never returns an
illegal package, and it breaks ties the same way every time. They cannot show
the rules or costs are right; the worked scenarios do that.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.negotiation.contracts import (
    ArrivalSlot,
    Deal,
    FlightPlanAction,
    NoDeal,
    NoDealReason,
    Package,
    Scenario,
)
from app.negotiation.fallback import decide
from app.negotiation.options import enumerate_packages
from app.negotiation.rules import check_package, rule_ids
from app.negotiation.utility import compute_cost
from tests.negotiation.factories import make_scenario, random_scenario

API_ROOT = Path(__file__).resolve().parents[2]
BIG_SEEDS = range(300)
SMALL_SEEDS = range(60)


def test_random_scenarios_are_a_meaningful_sample() -> None:
    results = [decide(random_scenario(seed)) for seed in BIG_SEEDS]
    deals = [r for r in results if isinstance(r, Deal)]
    no_deals = [r for r in results if isinstance(r, NoDeal)]
    assert len(deals) >= 50
    assert len(no_deals) >= 20
    # Both kinds of NoDeal occur, so both paths are exercised.
    assert {r.reason_type for r in no_deals} == set(NoDealReason)


@pytest.mark.parametrize("seed", BIG_SEEDS)
def test_decision_is_consistent_with_the_rules(seed: int) -> None:
    scenario = random_scenario(seed)
    result = decide(scenario)
    packages = enumerate_packages(scenario)
    known = set(rule_ids())
    for package in packages:
        assert {v.rule_id for v in check_package(scenario, package)} <= known
    if isinstance(result, Deal):
        assert check_package(scenario, result.package) == ()
        assert result.package in packages
        assert result.packages_considered == len(packages)
    else:
        assert result.packages_considered == len(packages)
        if packages:
            assert all(check_package(scenario, p) for p in packages)
            assert result.nearest_package in packages
            assert result.nearest_violations == check_package(
                scenario, result.nearest_package
            )
            assert set(result.binding_rule_ids) <= known


# Written out here so the check does not lean on the module under test.
ACTION_RANK = {"direct": 0, "hold": 1, "vector": 2, "ground_delay": 3}


def every_coherent_package(scenario: Scenario) -> list[tuple[int, str, str, str]]:
    """All (time, runway, gate, action) for the scenario, built from scratch."""
    earliest = scenario.earliest_arrival_min.value
    latest = scenario.latest_arrival_min.value
    runways = scenario.runways.value
    gates = scenario.gates.value
    if earliest is None or latest is None or runways is None or gates is None:
        return []
    found = []
    for time_min in range(earliest, latest + 1, 5):
        for runway in sorted({r.runway_id for r in runways}):
            for gate in sorted({g.gate_id for g in gates}):
                for action in ACTION_RANK:
                    if (action == "direct") != (time_min == earliest):
                        continue
                    found.append((time_min, runway, gate, action))
    return found


@pytest.mark.parametrize("seed", SMALL_SEEDS)
def test_tie_break_picks_the_minimum_over_an_independent_exhaustive_scan(
    seed: int,
) -> None:
    scenario = random_scenario(seed, small=True)
    result = decide(scenario)
    candidates = every_coherent_package(scenario)
    # The scan and the enumerator agree up to actions the decision point rules
    # out; those fail the fuel rule, so they cannot be chosen either way.
    legal = []
    for time_min, runway, gate, action in candidates:
        package = Package(
            slot=ArrivalSlot(runway_id=runway, time_min=time_min),
            gate_id=gate,
            action=FlightPlanAction(action),
        )
        if not check_package(scenario, package):
            total = compute_cost(scenario, package).total
            legal.append(
                ((total, time_min, runway, gate, ACTION_RANK[action]), package)
            )

    if not legal:
        assert isinstance(result, NoDeal)
        return
    assert isinstance(result, Deal)
    best_key, best_package = min(legal, key=lambda item: item[0])
    assert result.package == best_package
    assert result.cost.total == best_key[0]
    assert result.packages_legal == len(legal)


def test_small_sample_has_both_outcomes_and_real_ties() -> None:
    outcomes = [decide(random_scenario(s, small=True)) for s in SMALL_SEEDS]
    assert any(isinstance(o, Deal) for o in outcomes)
    assert any(isinstance(o, NoDeal) for o in outcomes)
    ties = 0
    for seed in SMALL_SEEDS:
        scenario = random_scenario(seed, small=True)
        result = decide(scenario)
        if isinstance(result, Deal):
            totals = [
                compute_cost(scenario, p).total
                for p in enumerate_packages(scenario)
                if not check_package(scenario, p)
            ]
            ties += totals.count(result.cost.total) > 1
    assert ties >= 5, "the tie-break should actually be exercised"


def test_same_scenario_gives_byte_identical_results() -> None:
    for seed in range(40):
        first = decide(random_scenario(seed)).model_dump_json()
        second = decide(random_scenario(seed)).model_dump_json()
        scenario = random_scenario(seed)
        assert first == second == decide(scenario).model_dump_json()
        assert decide(scenario).model_dump_json() == decide(scenario).model_dump_json()


def test_serialisation_does_not_depend_on_hash_seed() -> None:
    script = (
        "from tests.negotiation.factories import random_scenario\n"
        "from app.negotiation.fallback import decide\n"
        "print(''.join(decide(random_scenario(s)).model_dump_json() "
        "for s in range(40)))\n"
    )
    outputs = []
    for hash_seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(API_ROOT)}
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            cwd=API_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].strip()


def test_irrelevant_change_leaves_the_decision_alone() -> None:
    base = make_scenario()
    renamed = make_scenario(flight_id="ZZ999", scenario_id="other")
    assert decide(base) == decide(renamed)
