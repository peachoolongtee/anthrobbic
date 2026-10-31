import ast
from pathlib import Path

import pytest

from app.negotiation import rule_values as rv
from app.negotiation.contracts import AircraftSize, FlightRules, WakeCategory
from app.negotiation.rule_values import RULE_VALUES, Status

NEGOTIATION = Path(__file__).resolve().parents[2] / "app" / "negotiation"


def test_every_entry_is_complete() -> None:
    assert RULE_VALUES
    for key, entry in RULE_VALUES.items():
        assert entry.key == key
        assert entry.unit.strip()
        assert entry.source.strip()
        assert isinstance(entry.status, Status)


def test_statuses_cover_the_five_kinds() -> None:
    assert {s.value for s in Status} == {
        "confirmed",
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


def test_fuel_reserve_is_labelled_as_policy() -> None:
    entry = rv.rule_value(rv.FUEL_RESERVE_MIN)
    assert entry.value == 45
    assert entry.status is Status.POLICY
    assert "our demo policy" in entry.source
    assert "14 CFR 121.639" in entry.source
    assert "FAA InFO 08004" in entry.source


def test_alternate_minimums_come_from_121_619() -> None:
    for key, value in (
        (rv.ALTERNATE_MIN_CEILING_FT, 2000),
        (rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI, 30),
        (rv.ALTERNATE_WINDOW_MIN, 60),
    ):
        entry = rv.rule_value(key)
        assert (entry.value, entry.status) == (value, Status.CONFIRMED)
        assert "121.619(a)" in entry.source


def test_planning_values() -> None:
    assert rv.runway_hourly_arrivals(FlightRules.IFR).value == 30
    assert rv.runway_hourly_arrivals(FlightRules.VFR).value == 40
    assert rv.runway_hourly_arrivals(FlightRules.IFR).status is Status.CONFIRMED
    assert rv.turnaround(AircraftSize.NARROW_BODY).value == 25
    assert rv.turnaround(AircraftSize.WIDE_BODY).value == 60
    for size in (AircraftSize.NARROW_BODY, AircraftSize.WIDE_BODY):
        assert rv.turnaround(size).status is Status.SECONDARY
        assert "EUROCONTROL" in rv.turnaround(size).source
    for key, value in ((rv.APPROACH_GROUND_SPEED_KT, 130), (rv.GATE_BUFFER_MIN, 15)):
        assert rv.rule_value(key).value == value
        assert rv.rule_value(key).status is Status.ASSUMPTION


def test_wake_values_are_confirmed_and_state_the_simplification() -> None:
    for leader in WakeCategory:
        for follower in WakeCategory:
            entry = rv.wake_separation(leader, follower)
            assert entry.status is Status.CONFIRMED
            assert "7110.65BB" in entry.source
            assert "RECAT" in entry.source


def test_every_aircraft_size_has_a_turnaround() -> None:
    for size in AircraftSize:
        assert rv.turnaround(size).value > 0


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
