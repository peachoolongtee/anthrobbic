"""The single table of every numeric rule value, with its source and status.

Nothing numeric that bears on legality or on which packages are considered may
be hardcoded outside this file. Update a value here when research confirms it
and change its status at the same time.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from app.negotiation.contracts import AircraftSize, WakeCategory


class Status(StrEnum):
    CONFIRMED = "confirmed"  # read from the primary source
    WORKBOOK = "organiser_workbook"  # challenge workbook: synthetic, not a regulation
    SECONDARY = "secondary"  # from a published study, not a rule
    UNVERIFIED = "unverified"
    ASSUMPTION = "assumption"  # our own demo default
    POLICY = "policy"  # our demo policy, shaped on a regulation


class RuleValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    value: int
    unit: str
    source: str
    status: Status


# Wake separation is the challenge workbook's wake_separation sheet, which the
# organisers describe as simplified from FAA JO 7110.65. The FAA citation is kept
# beside it. The workbook's pairs match the legacy-class minima in JO 7110.65BB
# para 5-5-4, which that order lists under en route and which we apply to
# arrivals as a simplification. The current order's terminal tables use wake
# categories A to I, which we simplify away; real terminals use RECAT. Every
# pair is checked on one runway and the leader is on approach, so the values for
# "small behind heavy/large on the same runway" apply, and behind a super the
# low-and-slow values apply. Super behind super is not listed in the workbook
# ("any other pair"), so it takes the 3 NM default. The workbook's min_time_s
# column is for same-runway departures and is not used, because this system
# sequences arrivals only. Small behind a B757 is not modelled.
_WAKE_SOURCE = (
    "Challenge workbook, sheet wake_separation (synthetic planning limits, not a "
    "regulation), simplified from FAA JO 7110.65. FAA citation: JO 7110.65BB "
    "para 5-5-4, current order not the 2015 text; the legacy minima are listed "
    "there under en route and are applied here to arrivals as a simplification. "
    "The current order's terminal tables use wake categories A to I, which we "
    "simplify away; real terminals use RECAT"
)
_WORKBOOK = "Challenge workbook (synthetic planning limits, not a regulation)"
_ASSUMED = "assumption: demo default, not from a regulation"

WAKE_DEFAULT_KEY = "wake_sep_nm.default"
FUEL_RESERVE_MIN = "fuel_reserve_min"
FUEL_CONTINGENCY_PCT = "fuel_contingency_pct"
FUEL_SPARE_ON_ARRIVAL_MIN = "fuel_spare_on_arrival_min"
HOLD_BURN_NARROW_KG_PER_H = "hold_burn_kg_per_h.narrow_body"
HOLD_BURN_WIDE_KG_PER_H = "hold_burn_kg_per_h.wide_body"
CREW_MAX_DUTY_MIN = "crew_max_duty_min"
GROUND_SHIFT_MIN = "ground_shift_min"
GROUND_OVERTIME_PCT = "ground_overtime_pct"
GATE_CHANGE_NOTICE_MIN = "gate_change_notice_min"
PERCENT_BASE = "percent_base"
AIRPORT_OPS_KEY = "airport_ops_per_hour"
AIRPORT_TURNAROUND_KEY = "airport_min_turnaround_min"
ALTERNATE_WINDOW_MIN = "alternate_window_min"
ALTERNATE_MIN_CEILING_FT = "alternate_min_ceiling_ft"
ALTERNATE_MIN_VISIBILITY_TENTH_MI = "alternate_min_visibility_tenth_mi"
MINUTES_PER_HOUR = "minutes_per_hour"
GATE_BUFFER_MIN = "gate_buffer_min"
APPROACH_GROUND_SPEED_KT = "approach_ground_speed_kt"  # every class but small
APPROACH_GROUND_SPEED_SMALL_KT = "approach_ground_speed_kt.small"
MIN_CONNECTION_MIN = "min_connection_min"
SLOT_STEP_MIN = "slot_step_min"
MAX_PACKAGES = "max_packages"

# Leader, follower, nautical miles. Pairs not listed use WAKE_DEFAULT_KEY.
_WAKE_LISTED: tuple[tuple[WakeCategory, WakeCategory, int], ...] = (
    (WakeCategory.HEAVY, WakeCategory.HEAVY, 4),
    (WakeCategory.HEAVY, WakeCategory.LARGE, 5),
    (WakeCategory.HEAVY, WakeCategory.SMALL, 6),
    (WakeCategory.LARGE, WakeCategory.SMALL, 4),
    (WakeCategory.SUPER, WakeCategory.HEAVY, 6),
    (WakeCategory.SUPER, WakeCategory.LARGE, 7),
    (WakeCategory.SUPER, WakeCategory.SMALL, 8),
)


def _wake_key(leader: WakeCategory, follower: WakeCategory) -> str:
    return f"wake_sep_nm.{leader.value}>{follower.value}"


def _assumption(key: str, value: int, unit: str, note: str = "") -> RuleValue:
    source = f"{_ASSUMED}; {note}" if note else _ASSUMED
    return RuleValue(
        key=key, value=value, unit=unit, source=source, status=Status.ASSUMPTION
    )


def _workbook(key: str, value: int, unit: str, note: str = "") -> RuleValue:
    source = f"{_WORKBOOK}; {note}" if note else _WORKBOOK
    return RuleValue(
        key=key, value=value, unit=unit, source=source, status=Status.WORKBOOK
    )


def _build() -> Mapping[str, RuleValue]:
    values: list[RuleValue] = [
        RuleValue(
            key=_wake_key(leader, follower),
            value=nm,
            unit="nautical miles",
            source=_WAKE_SOURCE,
            status=Status.WORKBOOK,
        )
        for leader, follower, nm in _WAKE_LISTED
    ]
    values += [
        RuleValue(
            key=WAKE_DEFAULT_KEY,
            value=3,
            unit="nautical miles",
            source=f"{_WAKE_SOURCE}; the workbook's 'any other pair'",
            status=Status.WORKBOOK,
        ),
        _workbook(
            FUEL_RESERVE_MIN,
            30,
            "minutes of holding fuel",
            "sheet fuel_and_crew, final fuel reserve",
        ),
        _workbook(
            FUEL_CONTINGENCY_PCT,
            5,
            "percent of trip fuel",
            "sheet fuel_and_crew, contingency fuel",
        ),
        _workbook(
            FUEL_SPARE_ON_ARRIVAL_MIN,
            45,
            "minutes of holding fuel",
            "sheet fuel_and_crew, assumed spare fuel on arrival unless the team "
            "states otherwise",
        ),
        _workbook(
            HOLD_BURN_NARROW_KG_PER_H,
            2400,
            "kg per hour",
            "sheet fuel_and_crew, A320/737 class; also used for regional jets",
        ),
        _workbook(
            HOLD_BURN_WIDE_KG_PER_H,
            6500,
            "kg per hour",
            "sheet fuel_and_crew, A330/777 class",
        ),
        _workbook(
            CREW_MAX_DUTY_MIN,
            780,
            "minutes from report time (13 hours)",
            "sheet fuel_and_crew, flight crew max duty, simplified FAA Part 117",
        ),
        _workbook(
            GROUND_SHIFT_MIN,
            480,
            "minutes (8 hours)",
            "sheet fuel_and_crew, ground crew shift",
        ),
        _workbook(
            GROUND_OVERTIME_PCT,
            150,
            "percent of the ordinary crew-minute cost",
            "sheet fuel_and_crew, overtime costs 1.5x after the shift",
        ),
        _workbook(
            GATE_CHANGE_NOTICE_MIN,
            20,
            "minutes before arrival",
            "sheet fuel_and_crew, gate change notice",
        ),
        RuleValue(
            key=PERCENT_BASE,
            value=100,
            unit="percent",
            source="unit conversion",
            status=Status.CONFIRMED,
        ),
        RuleValue(
            key=ALTERNATE_WINDOW_MIN,
            value=60,
            unit="minutes either side of ETA",
            source="shaped on 14 CFR 121.619(a), a dispatch rule",
            status=Status.POLICY,
        ),
        RuleValue(
            key=ALTERNATE_MIN_CEILING_FT,
            value=2000,
            unit="feet; no alternate needed at or above",
            source="shaped on 14 CFR 121.619(a), a dispatch rule",
            status=Status.POLICY,
        ),
        RuleValue(
            key=ALTERNATE_MIN_VISIBILITY_TENTH_MI,
            value=30,
            unit="tenths of a statute mile; no alternate needed at or above",
            source="shaped on 14 CFR 121.619(a), a dispatch rule",
            status=Status.POLICY,
        ),
        RuleValue(
            key=MINUTES_PER_HOUR,
            value=60,
            unit="minutes",
            source="unit conversion",
            status=Status.CONFIRMED,
        ),
        _assumption(GATE_BUFFER_MIN, 15, "minutes between gate occupancies"),
        _assumption(
            APPROACH_GROUND_SPEED_KT,
            130,
            "knots",
            "final approach speed for every class but small; converts miles of "
            "separation to minutes",
        ),
        _assumption(
            APPROACH_GROUND_SPEED_SMALL_KT,
            100,
            "knots",
            "final approach speed for a small follower",
        ),
        _assumption(
            MIN_CONNECTION_MIN,
            30,
            "minutes from gate-in to connecting departure",
            "soft cost only",
        ),
        _assumption(
            SLOT_STEP_MIN,
            5,
            "minutes between candidate arrival slots",
            "enumeration grid",
        ),
        _assumption(MAX_PACKAGES, 2000, "packages", "hard bound on enumeration"),
    ]
    keys = [v.key for v in values]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate rule value key")
    return MappingProxyType({v.key: v for v in values})


RULE_VALUES: Mapping[str, RuleValue] = _build()


def rule_value(key: str) -> RuleValue:
    return RULE_VALUES[key]


def reference(value: RuleValue) -> str:
    """A violation source string that carries the value's current status."""
    head = f"{value.key}={value.value} {value.unit}"
    return f"{head} [{value.status.value}]: {value.source}"


def wake_separation(leader: WakeCategory, follower: WakeCategory) -> RuleValue:
    """Required in-trail separation for `follower` behind `leader`."""
    return RULE_VALUES.get(
        _wake_key(leader, follower),
        RULE_VALUES[WAKE_DEFAULT_KEY],
    )


def airport_ops_per_hour(value: int) -> RuleValue:
    """An airport's cap, from the workbook table via the scenario."""
    return RuleValue(
        key=AIRPORT_OPS_KEY,
        value=value,
        unit="runway movements per airport per rolling hour (arrivals only counted)",
        source=f"{_WORKBOOK}; sheet airport_capacity, max_runway_ops_per_hour, "
        "read as an airport total",
        status=Status.WORKBOOK,
    )


def airport_min_turnaround(value: int) -> RuleValue:
    """An airport's minimum turnaround, from the workbook table via the scenario."""
    return RuleValue(
        key=AIRPORT_TURNAROUND_KEY,
        value=value,
        unit="minutes",
        source=f"{_WORKBOOK}; sheet airport_capacity, min_turnaround_min",
        status=Status.WORKBOOK,
    )


def hold_burn_kg_per_min(size: AircraftSize) -> int:
    """Workbook holding burn for a size class, in whole kg per minute, rounded
    up: 2,400 kg/h is 40; 6,500 kg/h is 108.3, so 109."""
    key = (
        HOLD_BURN_WIDE_KG_PER_H
        if size is AircraftSize.WIDE_BODY
        else HOLD_BURN_NARROW_KG_PER_H
    )
    per_hour = RULE_VALUES[MINUTES_PER_HOUR].value
    return (RULE_VALUES[key].value + per_hour - 1) // per_hour


def approach_speed(follower: WakeCategory) -> RuleValue:
    """Final approach speed of the following aircraft, which sets how many
    minutes a mile of separation takes."""
    key = (
        APPROACH_GROUND_SPEED_SMALL_KT
        if follower is WakeCategory.SMALL
        else APPROACH_GROUND_SPEED_KT
    )
    return RULE_VALUES[key]
