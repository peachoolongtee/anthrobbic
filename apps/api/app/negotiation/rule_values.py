"""The single table of every numeric rule value, with its source and status.

Nothing numeric that bears on legality or on which packages are considered may
be hardcoded outside this file. Update a value here when research confirms it
and change its status at the same time.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from app.negotiation.contracts import AircraftSize, FlightRules, WakeCategory


class Status(StrEnum):
    CONFIRMED = "confirmed"  # read from the primary source
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


# Wake separation uses the legacy classes, not RECAT, and the current order
# rather than the 2015 text. In that order the legacy-class minima are listed
# under en route and are applied here to arrivals as a simplification. Every
# pair is checked on one runway and the leader is on approach, so the values for
# "small behind heavy/large on the same runway" apply, and behind a super the
# low-and-slow values apply (at or below FL240 and under 250 kt). Small behind
# a B757 (4 NM) is not modelled because there is no B757 category.
_WAKE_SOURCE = (
    "FAA JO 7110.65BB para 5-5-4, current order not the 2015 text. The legacy "
    "minima are listed there under en route and are applied here to arrivals "
    "as a simplification; real terminals use RECAT. Leader on approach, so the "
    "low-slow behind-super values apply"
)
_ASSUMED = "assumption: demo default, not from a regulation"

WAKE_DEFAULT_KEY = "wake_sep_nm.default"
FUEL_RESERVE_MIN = "fuel_reserve_min"
ALTERNATE_WINDOW_MIN = "alternate_window_min"
ALTERNATE_MIN_CEILING_FT = "alternate_min_ceiling_ft"
ALTERNATE_MIN_VISIBILITY_TENTH_MI = "alternate_min_visibility_tenth_mi"
RUNWAY_HOURLY_ARRIVALS_IFR = "runway_hourly_arrivals.ifr"
RUNWAY_HOURLY_ARRIVALS_VFR = "runway_hourly_arrivals.vfr"
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
    (WakeCategory.SUPER, WakeCategory.SUPER, 5),
    (WakeCategory.SUPER, WakeCategory.HEAVY, 6),
    (WakeCategory.SUPER, WakeCategory.LARGE, 7),
    (WakeCategory.SUPER, WakeCategory.SMALL, 8),
)


def _wake_key(leader: WakeCategory, follower: WakeCategory) -> str:
    return f"wake_sep_nm.{leader.value}>{follower.value}"


def turnaround_key(size: AircraftSize) -> str:
    return f"turnaround_min.{size.name.lower()}"


def _assumption(key: str, value: int, unit: str, note: str = "") -> RuleValue:
    source = f"{_ASSUMED}; {note}" if note else _ASSUMED
    return RuleValue(
        key=key, value=value, unit=unit, source=source, status=Status.ASSUMPTION
    )


def _secondary(key: str, value: int) -> RuleValue:
    return RuleValue(
        key=key,
        value=value,
        unit="minutes",
        source="EUROCONTROL Europe 2022, 10th-percentile scheduled turnaround",
        status=Status.SECONDARY,
    )


def _build() -> Mapping[str, RuleValue]:
    values: list[RuleValue] = [
        RuleValue(
            key=_wake_key(leader, follower),
            value=nm,
            unit="nautical miles",
            source=_WAKE_SOURCE,
            status=Status.SECONDARY,
        )
        for leader, follower, nm in _WAKE_LISTED
    ]
    values += [
        RuleValue(
            key=WAKE_DEFAULT_KEY,
            value=3,
            unit="nautical miles",
            source=f"{_WAKE_SOURCE}; radar minimum for pairs not listed",
            status=Status.SECONDARY,
        ),
        RuleValue(
            key=FUEL_RESERVE_MIN,
            value=45,
            unit="minutes at normal cruise",
            source=(
                "our demo policy, shaped on 14 CFR 121.639 and FAA InFO 08004; "
                "121.639 is a dispatch and takeoff test and does not bind in flight"
            ),
            status=Status.POLICY,
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
        RuleValue(
            key=RUNWAY_HOURLY_ARRIVALS_IFR,
            value=30,
            unit="arrivals per runway per rolling hour",
            source="FAA rule-of-thumb slides, 2006",
            status=Status.ASSUMPTION,
        ),
        RuleValue(
            key=RUNWAY_HOURLY_ARRIVALS_VFR,
            value=40,
            unit="arrivals per runway per rolling hour",
            source="FAA rule-of-thumb slides, 2006",
            status=Status.ASSUMPTION,
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
            turnaround_key(AircraftSize.REGIONAL),
            20,
            "minutes",
            "no research value; set below narrow-body",
        ),
        _secondary(turnaround_key(AircraftSize.NARROW_BODY), 25),
        _secondary(turnaround_key(AircraftSize.WIDE_BODY), 60),
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


def runway_hourly_arrivals(rules: FlightRules) -> RuleValue:
    key = (
        RUNWAY_HOURLY_ARRIVALS_IFR
        if rules is FlightRules.IFR
        else RUNWAY_HOURLY_ARRIVALS_VFR
    )
    return RULE_VALUES[key]


def approach_speed(follower: WakeCategory) -> RuleValue:
    """Final approach speed of the following aircraft, which sets how many
    minutes a mile of separation takes."""
    key = (
        APPROACH_GROUND_SPEED_SMALL_KT
        if follower is WakeCategory.SMALL
        else APPROACH_GROUND_SPEED_KT
    )
    return RULE_VALUES[key]


def turnaround(size: AircraftSize) -> RuleValue:
    return RULE_VALUES[turnaround_key(size)]
