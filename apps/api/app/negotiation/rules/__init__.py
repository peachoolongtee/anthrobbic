"""Hard rules, grouped by domain. `ALL_RULES` is the one registry."""

from app.negotiation.contracts import Package, Rule, Scenario, Violation
from app.negotiation.rules import atc, ground, pilot

ALL_RULES: tuple[Rule, ...] = atc.RULES + pilot.RULES + ground.RULES


def _check_unique() -> None:
    ids = [rule.rule_id for rule in ALL_RULES]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate rule ID")


_check_unique()


def rule_ids() -> tuple[str, ...]:
    return tuple(rule.rule_id for rule in ALL_RULES)


def check_package(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """Run every rule and return all violations, in registry order."""
    return tuple(v for rule in ALL_RULES for v in rule.check(scenario, package))
