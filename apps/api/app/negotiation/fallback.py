"""The deterministic decision: lowest-cost legal package, or `NoDeal`.

This is what runs when agents fail to agree, and it is the only authority on
which package is allowed. Same scenario in, identical result out.
"""

from collections import Counter

from app.negotiation.contracts import (
    Deal,
    Decision,
    NoDeal,
    NoDealReason,
    Package,
    RuleElimination,
    Scenario,
    Violation,
    ViolationCause,
)
from app.negotiation.options import enumerate_packages, enumeration_gaps
from app.negotiation.rules import check_package
from app.negotiation.utility import DEFAULT_WEIGHTS, CostWeights, compute_cost


def decide(scenario: Scenario, weights: CostWeights = DEFAULT_WEIGHTS) -> Decision:
    """Pick the cheapest package that passes every rule, else `NoDeal`.

    Raises `PackageBoundError` if the candidate set exceeds the bound.
    """
    packages = enumerate_packages(scenario)
    if not packages:
        gaps = enumeration_gaps(scenario)
        return NoDeal(
            reason_type=(
                NoDealReason.SYSTEM_FAULT if gaps else NoDealReason.NOTHING_LEGAL
            ),
            binding_rule_ids=(),
            eliminations=(),
            packages_considered=0,
            nearest_package=None,
            nearest_violations=(),
            reason=(
                "no candidate packages: unknown " + ", ".join(gaps)
                if gaps
                else "no candidate packages in the planning window"
            ),
        )

    best: tuple[int, tuple[int, str, str, int], Package] | None = None
    legal = 0
    eliminated: Counter[str] = Counter()
    failures: list[tuple[Package, tuple[Violation, ...]]] = []
    for package in packages:
        violations = check_package(scenario, package)
        if violations:
            eliminated.update({v.rule_id for v in violations})
            failures.append((package, violations))
            continue
        legal += 1
        cost = compute_cost(scenario, package, weights).total
        candidate = (cost, package.sort_key, package)
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
    # Nearest: fewest distinct rules broken, then fewest violations, then the
    # code tie-break, so the choice never depends on iteration accident.
    nearest, nearest_violations = min(
        failures,
        key=lambda f: (len({v.rule_id for v in f[1]}), len(f[1]), f[0].sort_key),
    )
    # A fault, not a verdict, when missing data is behind every package's failure.
    faulted = all(
        any(v.cause is ViolationCause.MISSING_DATA for v in violations)
        for _, violations in failures
    )
    return NoDeal(
        reason_type=NoDealReason.SYSTEM_FAULT
        if faulted
        else NoDealReason.NOTHING_LEGAL,
        binding_rule_ids=tuple(rule_id for rule_id, n in ranked if n == top),
        eliminations=tuple(
            RuleElimination(rule_id=rule_id, packages_eliminated=n)
            for rule_id, n in ranked
        ),
        packages_considered=len(packages),
        nearest_package=nearest,
        nearest_violations=nearest_violations,
        reason=(
            "missing data breaks every candidate package"
            if faulted
            else "every candidate package breaks at least one hard rule"
        ),
    )
