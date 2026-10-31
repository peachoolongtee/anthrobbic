import re

import pytest

from app.negotiation.contracts import PublicReason
from app.negotiation.rules import ALL_RULES, public_reason, rule_ids


@pytest.mark.parametrize("rule_id", rule_ids())
def test_every_rule_has_a_public_reason_class(rule_id: str) -> None:
    assert isinstance(public_reason(rule_id), PublicReason)


def test_the_mapping_is_exactly_this() -> None:
    assert {r.rule_id: r.public_reason.value for r in ALL_RULES} == {
        "ATC-WAKE-SEP": "safety_margin",
        "ATC-RWY-CLOSED": "resource_closed",
        "ATC-TWY-CLOSED": "resource_closed",
        "ATC-RWY-THROUGHPUT": "capacity_limit",
        "ATC-SLOT-WINDOW": "schedule_limit",
        "PLT-FUEL-POLICY": "infeasible_for_another_domain",
        "GND-GATE-OVERLAP": "resource_conflict",
        "GND-GATE-SIZE": "equipment_mismatch",
        "GND-TURNAROUND": "schedule_limit",
    }


def test_classes_expose_no_numbers_or_identifiers() -> None:
    for reason in PublicReason:
        assert re.fullmatch(r"[a-z_]+", reason.value)


def test_unknown_rule_raises() -> None:
    with pytest.raises(KeyError):
        public_reason("NOPE")
