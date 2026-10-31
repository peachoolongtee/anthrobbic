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
from app.negotiation.options import (
    PackageBoundError,
    enumerate_packages,
    enumeration_gaps,
)
from app.negotiation.rules import check_package
from app.negotiation.utility import DEFAULT_WEIGHTS, CostWeights, compute_cost


def _fault(reason: str, packages_considered: int = 0) -> NoDeal:
    return NoDeal(
        reason_type=NoDealReason.SYSTEM_FAULT,
        binding_rule_ids=(),
        eliminations=(),
        packages_considered=packages_considered,
        nearest_package=None,
        nearest_violations=(),
        reason=reason,
    )


def _representative(
    rule_id: str, failures: list[tuple[Package, tuple[Violation, ...]]]
) -> Violation | None:
    """The first violation of this rule in package order, preferring one that
    carries an observed value and a limit over a missing-data one."""
    fallback: Violation | None = None
    for _, violations in failures:
        for violation in violations:
            if violation.rule_id != rule_id:
                continue
            if violation.cause is ViolationCause.CONSTRAINT:
                return violation
            fallback = fallback or violation
    return fallback


def decide(scenario: Scenario, weights: CostWeights = DEFAULT_WEIGHTS) -> Decision:
    """Pick the cheapest package that passes every rule, else `NoDeal`.

    Never raises for a bad scenario. If nothing could be enumerated, or the
    candidate set exceeds the package bound, the result is
    `NoDeal(SYSTEM_FAULT)`: an empty or inconsistent input is a fault, not a
    verdict that nothing is legal.
    """
    try:
        packages = enumerate_packages(scenario)
    except PackageBoundError as error:
        return _fault(f"too many candidate packages: {error}")
    if not packages:
        gaps = enumeration_gaps(scenario)
        return _fault(
            "no candidate packages: unknown " + ", ".join(gaps)
            if gaps
            else "no candidate packages: the runway list, gate list or planning "
            "window is empty or inconsistent"
        )

    best: tuple[tuple[int, tuple[int, str, str, int]], Package] | None = None
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
        rank = (cost, package.sort_key)
        if best is None or rank < best[0]:
            best = (rank, package)

    if best is not None:
        chosen = best[1]
        return Deal(
            package=chosen,
            cost=compute_cost(scenario, chosen, weights),
            packages_considered=len(packages),
            packages_legal=legal,
        )

    failures.sort(key=lambda f: f[0].sort_key)
    ranked = sorted(eliminated.items(), key=lambda item: (-item[1], item[0]))
    top = ranked[0][1]
    binding = tuple(rule_id for rule_id, n in ranked if n == top)
    binding_violations = tuple(
        v
        for rule_id in binding
        if (v := _representative(rule_id, failures)) is not None
    )
    # Nearest: fewest distinct rules broken, then fewest violations, then the
    # code tie-break, so the choice never depends on iteration accident.
    nearest, nearest_violations = min(
        failures,
        key=lambda f: (len({v.rule_id for v in f[1]}), len(f[1]), f[0].sort_key),
    )
    # A fault, not a verdict, when any package is blocked only by missing data:
    # supplying the data might make it legal.
    faulted = any(
        all(v.cause is ViolationCause.MISSING_DATA for v in violations)
        for _, violations in failures
    )
    return NoDeal(
        reason_type=NoDealReason.SYSTEM_FAULT
        if faulted
        else NoDealReason.NOTHING_LEGAL,
        binding_rule_ids=binding,
        eliminations=tuple(
            RuleElimination(rule_id=rule_id, packages_eliminated=n)
            for rule_id, n in ranked
        ),
        packages_considered=len(packages),
        nearest_package=nearest,
        nearest_violations=nearest_violations,
        reason=(
            "a candidate package is blocked only by missing or invalid data"
            if faulted
            else "every candidate package breaks at least one hard rule"
        ),
        binding_violations=binding_violations,
    )
