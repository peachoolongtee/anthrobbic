"""The deterministic decision: lowest-cost legal package, or `NoDeal`.

This is what runs when agents fail to agree, and it is the only authority on
which package is allowed. Same scenario in, identical result out.
"""

from collections import Counter

from app.negotiation.contracts import (
    Deal,
    Decision,
    FlightPlanAction,
    NoDeal,
    Package,
    RuleElimination,
    Scenario,
)
from app.negotiation.options import enumerate_packages, enumeration_gaps
from app.negotiation.rules import check_package
from app.negotiation.utility import CostWeights, DEFAULT_WEIGHTS, compute_cost

_ACTION_RANK = {action: rank for rank, action in enumerate(FlightPlanAction)}


def tie_break_key(package: Package) -> tuple[int, str, str, int]:
    """Order among equal-cost packages: earliest, then runway, gate, action."""
    return (
        package.slot.time_min,
        package.slot.runway_id,
        package.gate_id,
        _ACTION_RANK[package.action],
    )


def decide(scenario: Scenario, weights: CostWeights = DEFAULT_WEIGHTS) -> Decision:
    """Pick the cheapest package that passes every rule, else `NoDeal`.

    Raises `PackageBoundError` if the candidate set exceeds the bound.
    """
    packages = enumerate_packages(scenario)
    if not packages:
        gaps = enumeration_gaps(scenario)
        reason = (
            "no candidate packages: unknown " + ", ".join(gaps)
            if gaps
            else "no candidate packages in the planning window"
        )
        return NoDeal(
            binding_rule_ids=(),
            eliminations=(),
            packages_considered=0,
            reason=reason,
        )

    best: tuple[int, tuple[int, str, str, int], Package] | None = None
    legal = 0
    eliminated: Counter[str] = Counter()
    for package in packages:
        violations = check_package(scenario, package)
        if violations:
            eliminated.update({v.rule_id for v in violations})
            continue
        legal += 1
        cost = compute_cost(scenario, package, weights).total
        candidate = (cost, tie_break_key(package), package)
        if best is None or candidate[:2] < best[:2]:
            best = candidate

    if best is not None:
        chosen = best[2]
        return Deal(
            package=chosen,
            cost=compute_cost(scenario, chosen, weights),
            packages_considered=len(packages),
            packages_legal=legal,
        )

    ranked = sorted(eliminated.items(), key=lambda item: (-item[1], item[0]))
    top = ranked[0][1]
    return NoDeal(
        binding_rule_ids=tuple(rule_id for rule_id, n in ranked if n == top),
        eliminations=tuple(
            RuleElimination(rule_id=rule_id, packages_eliminated=n)
            for rule_id, n in ranked
        ),
        packages_considered=len(packages),
        reason="every candidate package breaks at least one hard rule",
    )
