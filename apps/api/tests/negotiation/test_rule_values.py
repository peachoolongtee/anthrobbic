import ast
from pathlib import Path

import pytest

from app.negotiation import rule_values as rv
from app.negotiation.contracts import AircraftSize, WakeCategory
from app.negotiation.rule_values import RULE_VALUES, Status

NEGOTIATION = Path(__file__).resolve().parents[2] / "app" / "negotiation"


def test_every_entry_is_complete() -> None:
    assert RULE_VALUES
    for key, entry in RULE_VALUES.items():
        assert entry.key == key
        assert entry.unit.strip()
        assert entry.source.strip()
        assert isinstance(entry.status, Status)


def test_statuses_cover_the_six_kinds() -> None:
    assert {s.value for s in Status} == {
        "confirmed",
        "organiser_workbook",
        "secondary",
        "unverified",
        "assumption",
        "policy",
    }


def test_table_is_read_only() -> None:
    with pytest.raises(TypeError):
        RULE_VALUES["x"] = RULE_VALUES[rv.GATE_BUFFER_MIN]  # type: ignore[index]
    with pytest.raises(Exception):  # noqa: B017  frozen pydantic model
        RULE_VALUES[rv.GATE_BUFFER_MIN].value = 1  # type: ignore[misc]


WORKBOOK_FUEL_AND_CREW = {
    rv.FUEL_RESERVE_MIN: 30,  # minutes of holding fuel
    rv.FUEL_CONTINGENCY_PCT: 5,  # percent of trip fuel
    rv.FUEL_SPARE_ON_ARRIVAL_MIN: 45,  # minutes of holding fuel
    rv.HOLD_BURN_NARROW_KG_PER_H: 2400,
    rv.HOLD_BURN_WIDE_KG_PER_H: 6500,
    rv.CREW_MAX_DUTY_MIN: 13 * 60,
    rv.GROUND_SHIFT_MIN: 8 * 60,
    rv.GROUND_OVERTIME_PCT: 150,
    rv.GATE_CHANGE_NOTICE_MIN: 20,
}


def test_fuel_and_crew_limits_are_the_workbooks() -> None:
    for key, value in WORKBOOK_FUEL_AND_CREW.items():
        entry = rv.rule_value(key)
        assert entry.value == value, key
        assert entry.status is Status.WORKBOOK, key
        assert "Challenge workbook" in entry.source
        assert "not a regulation" in entry.source
        assert "policy" not in entry.source.lower().replace("synthetic planning", "")


def test_fuel_reserve_is_no_longer_called_our_policy() -> None:
    entry = rv.rule_value(rv.FUEL_RESERVE_MIN)
    assert entry.unit == "minutes of holding fuel"
    assert "our demo policy" not in entry.source
    assert "121.639" not in entry.source


def test_hold_burn_per_minute_is_rounded_up_from_the_workbook_hourly_figure() -> None:
    # 2,400 kg/h is exactly 40 kg/min; 6,500 kg/h is 108.33, so 109.
    assert rv.hold_burn_kg_per_min(AircraftSize.NARROW_BODY) == 40
    assert rv.hold_burn_kg_per_min(AircraftSize.REGIONAL) == 40
    assert rv.hold_burn_kg_per_min(AircraftSize.WIDE_BODY) == 109


def test_alternate_minimums_are_policy_shaped_on_121_619() -> None:
    for key, value in (
        (rv.ALTERNATE_MIN_CEILING_FT, 2000),
        (rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI, 30),
        (rv.ALTERNATE_WINDOW_MIN, 60),
    ):
        entry = rv.rule_value(key)
        assert (entry.value, entry.status) == (value, Status.POLICY)
        assert entry.source == "shaped on 14 CFR 121.619(a), a dispatch rule"


def test_planning_values() -> None:
    # Per-airport limits are built from the workbook table, not stored here.
    cap = rv.airport_ops_per_hour(36)
    stay = rv.airport_min_turnaround(35)
    for entry in (cap, stay):
        assert entry.status is Status.WORKBOOK
        assert "Challenge workbook" in entry.source
    assert cap.value == 36 and stay.value == 35
    assert "read as an airport total" in cap.source
    # The old per-runway and per-size figures are gone.
    assert not any(k.startswith("runway_hourly_arrivals") for k in RULE_VALUES)
    assert not any(k.startswith("turnaround_min") for k in RULE_VALUES)
    for key, value in (
        (rv.APPROACH_GROUND_SPEED_KT, 130),
        (rv.APPROACH_GROUND_SPEED_SMALL_KT, 100),
        (rv.GATE_BUFFER_MIN, 15),
    ):
        assert rv.rule_value(key).value == value
        assert rv.rule_value(key).status is Status.ASSUMPTION


def test_wake_values_are_the_workbooks_and_keep_the_faa_citation() -> None:
    for leader in WakeCategory:
        for follower in WakeCategory:
            entry = rv.wake_separation(leader, follower)
            assert entry.status is Status.WORKBOOK
            assert entry.unit == "nautical miles"
            assert "Challenge workbook" in entry.source
            assert "wake_separation" in entry.source
            # The FAA citation stays beside the workbook source.
            assert "7110.65BB" in entry.source
            assert "RECAT" in entry.source
            assert "en route" in entry.source
            assert "simplification" in entry.source
    # Super behind super is not a workbook pair, so it takes the 3 NM default.
    assert rv.wake_separation(WakeCategory.SUPER, WakeCategory.SUPER).value == 3


# Files whose numbers must come from rule_values. Only 0 and 1 are allowed as
# structural constants. utility.py is excluded: its weights are in one object.
GUARDED = [
    *sorted((NEGOTIATION / "rules").glob("*.py")),
    NEGOTIATION / "options.py",
    NEGOTIATION / "fallback.py",
]


@pytest.mark.parametrize("path", GUARDED, ids=lambda p: p.name)
def test_no_numeric_literals_outside_rule_values(path: Path) -> None:
    tree = ast.parse(path.read_text())
    offenders = [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
        and node.value not in (0, 1)
    ]
    assert offenders == []
