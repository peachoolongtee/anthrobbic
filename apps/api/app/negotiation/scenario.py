"""Turn a DOT row into a `Scenario`, with a provenance label on every field.

Provenance, per field (also in `FIELD_NOTES`):

- real: the flight's identity and schedule.
- derived: computed from the file, such as the tail's next departure, the
  airport's typical taxi-in, and the earliest arrival (schedule plus a delay
  signal, below).
- synthetic: invented, seeded per flight, from `GeneratorParams`.

No hindsight. Nothing here reads this row's ARRIVAL_TIME, ARRIVAL_DELAY,
WHEELS_ON, WHEELS_OFF, DEPARTURE_TIME, DEPARTURE_DELAY, AIR_TIME, ELAPSED_TIME,
TAXI_IN or the size of any delay cause. Those are returned only by
`outcome_of`. The one other-row outcome used is the inbound leg's lateness,
below, and only when it was knowable.

Earliest arrival is the scheduled arrival plus a delay signal:

- Weather row: a floor of 15 minutes, the eligibility threshold. It uses no
  observed delay and deliberately understates long delays.
- Late-aircraft row: the larger of the floor (20 minutes) and the inbound
  leg's propagated lateness. The inbound leg is the same tail's immediately
  previous flight (`dot.inbound_leg`). Its lateness is the previous flight's
  ARRIVAL_DELAY, counted only if that flight had landed, or was due to land,
  by this flight's scheduled departure plus `INBOUND_KNOWN_MARGIN_MIN`, which
  is when an operations centre tracking the inbound aircraft knows it. The
  lateness that carries over is that lateness less the recovery allowance:
  the scheduled turnaround above a minimum turnaround of
  the origin airport's workbook minimum turnaround, floored
  at zero. The margin of 30 minutes is our assumption. With no usable inbound
  leg the floor applies, and `earliest_basis` says so.

Airport limits (runways, spare gates, throughput, minimum turnaround) come from
the challenge workbook's airport_capacity table (`airport_limits`), which the
organisers label synthetic. A destination with no row in it gets a scenario with
those fields unknown, so the rules fail closed and the result is a visible
system fault; no default is ever substituted.

Either way the planning window is a fixed 60 minutes after earliest, and the
as-flown arrival is kept apart for the evaluation to compare against.

Decision point, by cause: a late-aircraft delay comes from the inbound leg, so
it is known before departure and only a ground delay is possible (PRE_DEPARTURE).
A weather delay shows up at the destination while the aircraft is flying, so
only hold or vector is possible (AIRBORNE). A row over both thresholds is
treated as weather, as in `dot.cause_of`.
"""

import math
import os
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from app.negotiation import dot
from app.negotiation import rule_values as rv
from app.negotiation.airport_limits import AirportLimits, find_limits
from app.negotiation.contracts import (
    AircraftSize,
    Connection,
    DecisionPoint,
    FlightRules,
    Gate,
    GateOccupancy,
    OtherArrival,
    Provenance,
    Runway,
    Scenario,
    Sourced,
    Taxiway,
    WakeCategory,
    WeatherPeriod,
)
from app.negotiation.dot import MINUTES_PER_DAY, Cause, DotRow, NextLeg

INBOUND_KNOWN_MARGIN_MIN: Final = 30  # assumption: inbound ETA is tracked

REAL: Final = Provenance.REAL
DERIVED: Final = Provenance.DERIVED
SYNTHETIC: Final = Provenance.SYNTHETIC

FIELD_NOTES: Final[dict[str, str]] = {
    "scenario_id": "derived: built from the row's date, flight, route and the seed",
    "flight_id": "real: airline code and flight number",
    "decision_point": "derived: late-aircraft is pre-departure, weather is airborne",
    "flight_rules": "synthetic: instrument rules iff the synthetic forecast is poor",
    "wake_category": "synthetic: no aircraft type in the data",
    "aircraft_size": "synthetic: from the real airline and distance",
    "earliest_arrival_min": (
        "derived: scheduled arrival plus the disruption floor, or for late-aircraft "
        "rows the larger of that and the inbound leg's propagated lateness"
    ),
    "latest_arrival_min": "derived: earliest plus the planning window",
    "taxi_in_min": "derived: the destination's median TAXI_IN over the whole file",
    "fuel_on_board_kg": (
        "synthetic: trip fuel plus the workbook's 45 minutes of holding fuel, "
        "varied by a seeded draw, plus any alternate"
    ),
    "trip_fuel_kg": "synthetic: real block time times a synthetic burn rate",
    "cruise_burn_kg_per_min": "synthetic",
    "hold_burn_kg_per_min": "workbook: 2,400 kg/h narrow-body, 6,500 kg/h wide-body",
    "alternate_fuel_kg": "synthetic",
    "destination_forecast": "synthetic",
    "runways": (
        "synthetic: count is the workbook's active_runways for the airport; "
        "consecutive pairs are close parallels (one shared parallel_group) with a "
        "seeded probability"
    ),
    "taxiways": "synthetic",
    "gates": (
        "synthetic: the planned gate plus the workbook's spare_gates_at_any_time "
        "spare gates, all big enough for this aircraft and unoccupied during the "
        "decision window (the workbook gives gate counts, not sizes)"
    ),
    "other_arrivals": (
        "synthetic as a field: flight IDs and scheduled arrival times are real "
        "DOT rows, but each one's wake category and runway are synthetic"
    ),
    "gate_occupancies": (
        "synthetic, including on a seeded share of flights a stay on the planned "
        "gate just after its scheduled use, as if reassigned during the disruption"
    ),
    "planned_gate": (
        "synthetic: deliberately legal at schedule, free through the gate stay the "
        "rule imposes (next departure if later than the minimum turnaround)"
    ),
    "next_departure_min": "derived: the same tail's next scheduled departure",
    "next_leg_turnaround_hard": (
        "synthetic (a seeded draw) when a next leg exists; derived false when "
        "none does, since there is nothing to hold"
    ),
    "ground_shift_end_min": "synthetic: an 8-hour shift (workbook), seeded start",
    "decision_time_min": (
        "derived: late-aircraft rows, the scheduled departure plus the inbound "
        "margin; weather rows, one hour before scheduled arrival"
    ),
    "crew_report_min": (
        "synthetic: seeded from the scheduled departure only, never from what happened"
    ),
    "airport_ops_per_hour": "synthetic: the workbook's cap for the airport",
    "min_turnaround_min": "synthetic: the workbook's minimum for the airport",
    "connections": "synthetic: anchored on the real scheduled gate-in",
}


@dataclass(frozen=True, slots=True)
class EarliestBasis:
    """How the earliest arrival was set, for display and the evaluation.

    `basis` is "inbound_leg" when the inbound leg's propagated lateness set
    the delay, and "disruption_floor" otherwise (weather rows, no usable
    inbound leg, or an inbound leg that carried less than the floor).
    `usable_inbound` is whether a knowable inbound leg existed at all.
    """

    basis: Literal["inbound_leg", "disruption_floor"]
    delay_min: int
    floor_min: int
    usable_inbound: bool
    inbound_flight_id: str | None
    inbound_lateness_min: int | None
    recovery_allowance_min: int | None


def earliest_basis(
    row: DotRow, path: str | os.PathLike[str] | None = None
) -> EarliestBasis:
    """The delay added to the scheduled arrival to get the earliest arrival."""
    cause = dot.cause_of(row)
    floor = (
        dot.WEATHER_THRESHOLD_MIN
        if cause == "weather"
        else dot.LATE_AIRCRAFT_THRESHOLD_MIN
    )
    inbound = (
        dot.inbound_leg(row, INBOUND_KNOWN_MARGIN_MIN, path)
        if cause == "late_aircraft"
        else None
    )
    origin = find_limits(row.origin_airport)
    if inbound is None or origin is None:
        # No inbound leg, or no workbook minimum turnaround for the origin to
        # say how much lateness the turn recovers: the floor applies.
        return EarliestBasis("disruption_floor", floor, floor, False, None, None, None)
    allowance = max(0, inbound.scheduled_turn_min - origin.min_turnaround_min)
    carried = max(0, inbound.arrival_delay_min - allowance)
    return EarliestBasis(
        basis="inbound_leg" if carried > floor else "disruption_floor",
        delay_min=max(floor, carried),
        floor_min=floor,
        usable_inbound=True,
        inbound_flight_id=inbound.flight_id,
        inbound_lateness_min=inbound.arrival_delay_min,
        recovery_allowance_min=allowance,
    )


@dataclass(frozen=True, slots=True)
class AsFlownOutcome:
    """What actually happened. Agents must never see this.

    `arrival_min` is the as-flown arrival on the scenario's clock: scheduled
    arrival plus ARRIVAL_DELAY, or None when the delay is blank.
    """

    arrival_time: int | None  # HHMM
    arrival_delay: int | None
    arrival_min: int | None
    wheels_on: int | None
    taxi_in: int | None
    air_system_delay: int | None
    security_delay: int | None
    airline_delay: int | None
    late_aircraft_delay: int | None
    weather_delay: int | None


def outcome_of(row: DotRow) -> AsFlownOutcome:
    delay = row.arrival_delay
    return AsFlownOutcome(
        arrival_time=row.arrival_time,
        arrival_delay=delay,
        arrival_min=None if delay is None else dot.scheduled_arrival_min(row) + delay,
        wheels_on=row.wheels_on,
        taxi_in=row.taxi_in,
        air_system_delay=row.air_system_delay,
        security_delay=row.security_delay,
        airline_delay=row.airline_delay,
        late_aircraft_delay=row.late_aircraft_delay,
        weather_delay=row.weather_delay,
    )


def next_leg_of(
    row: DotRow, path: str | os.PathLike[str] | None = None
) -> NextLeg | None:
    """The same tail's next departure on the same day, from the data."""
    return dot.next_leg(row, path)


# --- the synthetic generator: every tunable number is here ------------------


@dataclass(frozen=True, slots=True)
class GeneratorParams:
    """All synthetic parameters. Plausible, not calibrated to any airline."""

    plan_window_min: int = 60  # latest minus earliest arrival
    window_margin_min: int = 60  # traffic taken either side of the window

    # Runways come from the workbook's active_runways for the airport.
    # Chance each consecutive runway pair (R1+R2, R3+R4) is closely spaced, so
    # the pair counts as one runway for wake separation and throughput.
    p_close_parallel_pair: float = 0.4
    p_runway_closed: tuple[float, float] = (0.25, 0.03)  # weather, late-aircraft
    p_taxiway_closed: tuple[float, float] = (0.15, 0.05)

    # Gates: the planned gate plus the workbook's spare gates (not the total).
    gate_size_weights: tuple[float, float, float] = (0.25, 0.55, 0.20)
    gate_stay_min: tuple[int, int] = (25, 120)  # synthetic occupant stays
    gate_util_base: float = 0.35  # share of time a gate is occupied
    gate_util_span: float = 0.35  # added at 900+ arrivals a day
    gate_util_full_at: int = 900

    # A gate reassigned during the disruption: on this share of flights, another
    # aircraft is put on the planned gate just after its scheduled use, so the
    # flight can move gate or wait. Added after a run showed that without it no
    # package ever traded one cost against another. Fixed before any model output,
    # and not to be tuned against results. See `PARAMETER_STATUS`.
    p_planned_gate_conflict: float = 0.5
    planned_gate_conflict_lead_min: tuple[int, int] = (0, 15)  # before earliest gate-in
    planned_gate_conflict_stay_min: tuple[int, int] = (10, 25)  # short, so it clears

    # Other arrivals' wake mix: super, heavy, small; the rest are large.
    other_wake_weights: tuple[float, float, float] = (0.01, 0.12, 0.04)

    # Aircraft: burn kg per minute at cruise, by size. Holding burn is the
    # workbook's, by size class (see `rule_values.hold_burn_kg_per_min`).
    cruise_burn: tuple[int, int, int] = (28, 45, 105)  # regional, narrow, wide
    burn_jitter: float = 0.10
    alternate_min: tuple[int, int] = (15, 35)  # alternate trip, minutes of cruise
    airborne_remaining: tuple[float, float] = (0.30, 0.90)  # share of block left

    # Variation around the workbook's default spare fuel on arrival (45 minutes
    # of holding fuel), in minutes of holding fuel, for an airborne aircraft:
    # (probability, low, high). The pre-workbook tiers (surplus above a 45-minute
    # cruise reserve: -8..0, 0..20, 20..50, 50..100) shifted down by 9 minutes,
    # the typical gap between the 45-minute default and the 30-minute reserve plus
    # contingency, so the share starting below the reserve stays near 4%.
    surplus_tiers: tuple[tuple[float, int, int], ...] = (
        (0.04, -17, -9),  # already below the reserve
        (0.30, -9, 11),
        (0.40, 11, 41),
        (0.26, 41, 91),
    )
    # The same, before departure (can refuel on the ground): old (30, 90) less 9.
    surplus_pre_departure_min: tuple[int, int] = (21, 81)

    # Forecast shape probabilities for (weather, late-aircraft) rows:
    # all poor, poor then clears, good then deteriorates, all good.
    forecast_shapes: tuple[tuple[float, float, float, float], ...] = (
        (0.45, 0.20, 0.15, 0.20),
        (0.07, 0.03, 0.02, 0.88),
    )
    poor_ceiling_ft: tuple[int, int] = (300, 1900)
    poor_visibility_tenth_mi: tuple[int, int] = (5, 29)
    good_ceiling_ft: tuple[int, int] = (2500, 6000)
    good_visibility_tenth_mi: tuple[int, int] = (40, 100)

    # Chance a next leg cannot be held (crew duty, curfew, a slot).
    p_next_leg_hard: float = 0.35

    # Connections: count weights for 0..4, passengers by size, minutes after gate-in.
    connection_count_weights: tuple[float, ...] = (0.15, 0.30, 0.30, 0.15, 0.10)
    connection_passengers: tuple[tuple[int, int], ...] = (
        (4, 30),
        (10, 80),
        (40, 200),
    )
    connection_gap_min: tuple[int, int] = (35, 180)
    # Minutes of the 8-hour ground shift already worked at the scheduled gate-in.
    # The shift end falls 240 to 30 minutes after it, as before.
    shift_elapsed_at_gate_in_min: tuple[int, int] = (240, 450)

    # Flight crew duty starts (report time) this long before the scheduled
    # departure: most are on their first flight of the duty, some are late in it.
    p_crew_late_in_duty: float = 0.30
    crew_report_lead_min: tuple[int, int] = (60, 120)
    crew_report_late_lead_min: tuple[int, int] = (300, 600)

    # Aircraft size by airline and distance.
    regional_airlines: tuple[str, ...] = ("EV", "OO", "MQ")
    widebody_airlines: tuple[str, ...] = ("AA", "UA", "DL", "HA")
    p_regional_if_regional_airline: float = 0.90
    p_regional_short_haul: float = 0.15
    short_haul_miles: int = 400
    long_haul_miles: int = 1800
    p_widebody_long_haul: float = 0.25
    p_super_given_widebody: float = 0.03
    p_small_given_regional: float = 0.20
    default_block_min: int = 120
    min_block_min: int = 15  # floor on the scheduled block time


PARAMS: Final = GeneratorParams()

# Generator values with a stated status, in the terms `rule_values` uses.
PARAMETER_STATUS: Final[dict[str, rv.Status]] = {
    "p_planned_gate_conflict": rv.Status.ASSUMPTION,
    "planned_gate_conflict_lead_min": rv.Status.ASSUMPTION,
    "planned_gate_conflict_stay_min": rv.Status.ASSUMPTION,
}
_SIZES: Final = tuple(AircraftSize)
_DEFAULT_TAXI_IN_MIN: Final = 15  # only to place synthetic times when unknown


def _seed_key(row: DotRow, seed: int) -> str:
    """Identifies a flight by its schedule columns only."""
    return (
        f"{row.year}-{row.month}-{row.day}|{row.flight_id}|{row.origin_airport}|"
        f"{row.destination_airport}|{row.tail_number}|{row.scheduled_departure}|{seed}"
    )


def _rng(key: str, stage: str) -> random.Random:
    """One stream per stage, so changing one stage cannot shift another."""
    return random.Random(f"{key}|{stage}")


def _weighted(rng: random.Random, weights: Sequence[float]) -> int:
    return rng.choices(range(len(weights)), weights=weights)[0]


def _sourced[T](value: T | None, provenance: Provenance) -> Sourced[T]:
    return Sourced(value=value, provenance=provenance)


def _parallel_groups(
    rng: random.Random, runway_ids: Sequence[str], p: GeneratorParams
) -> dict[str, str]:
    """Group consecutive runway pairs that are closely spaced parallels."""
    groups: dict[str, str] = {}
    for i in range(0, len(runway_ids) - 1, 2):
        if rng.random() < p.p_close_parallel_pair:
            name = f"PG{i // 2 + 1}"
            groups[runway_ids[i]] = name
            groups[runway_ids[i + 1]] = name
    return groups


def _aircraft_size(row: DotRow, seed: int, params: GeneratorParams) -> AircraftSize:
    rng = _rng(_seed_key(row, seed), "size")
    miles = row.distance
    if row.airline in params.regional_airlines:
        regional = rng.random() < params.p_regional_if_regional_airline
        return AircraftSize.REGIONAL if regional else AircraftSize.NARROW_BODY
    if miles is not None and miles < params.short_haul_miles:
        regional = rng.random() < params.p_regional_short_haul
        return AircraftSize.REGIONAL if regional else AircraftSize.NARROW_BODY
    if (
        miles is not None
        and miles >= params.long_haul_miles
        and row.airline in params.widebody_airlines
        and rng.random() < params.p_widebody_long_haul
    ):
        return AircraftSize.WIDE_BODY
    return AircraftSize.NARROW_BODY


def _wake_of(
    size: AircraftSize, rng: random.Random, p: GeneratorParams
) -> WakeCategory:
    if size is AircraftSize.WIDE_BODY:
        if rng.random() < p.p_super_given_widebody:
            return WakeCategory.SUPER
        return WakeCategory.HEAVY
    if size is AircraftSize.REGIONAL and rng.random() < p.p_small_given_regional:
        return WakeCategory.SMALL
    return WakeCategory.LARGE


def _other_wake(rng: random.Random, p: GeneratorParams) -> WakeCategory:
    roll = rng.random()
    super_p, heavy_p, small_p = p.other_wake_weights
    if roll < super_p:
        return WakeCategory.SUPER
    if roll < super_p + heavy_p:
        return WakeCategory.HEAVY
    if roll < super_p + heavy_p + small_p:
        return WakeCategory.SMALL
    return WakeCategory.LARGE


def _forecast(
    rng: random.Random,
    cause: Cause,
    earliest: int,
    latest: int,
    p: GeneratorParams,
) -> tuple[WeatherPeriod, ...]:
    """Complete coverage of the window in one to two periods."""
    start = earliest - p.window_margin_min * 3
    end = latest + p.window_margin_min * 3
    shape = _weighted(rng, p.forecast_shapes[0 if cause == "weather" else 1])

    def period(lo: int, hi: int, poor: bool) -> WeatherPeriod:
        ceilings = p.poor_ceiling_ft if poor else p.good_ceiling_ft
        visibility = p.poor_visibility_tenth_mi if poor else p.good_visibility_tenth_mi
        return WeatherPeriod(
            start_min=lo,
            end_min=hi,
            ceiling_ft=rng.randint(*ceilings),
            visibility_tenth_mi=rng.randint(*visibility),
        )

    change = earliest + rng.randint(0, p.plan_window_min)
    match shape:
        case 0:
            return (period(start, end, True),)
        case 1:  # poor, then clears
            return (period(start, change, True), period(change + 1, end, False))
        case 2:  # good, then deteriorates
            return (period(start, change, False), period(change + 1, end, True))
        case _:
            return (period(start, end, False),)


def _is_poor(period: WeatherPeriod) -> bool:
    return (
        period.ceiling_ft < rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value
        or period.visibility_tenth_mi
        < rv.rule_value(rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI).value
    )


def _poor_between(forecast: Sequence[WeatherPeriod], lo: int, hi: int) -> bool:
    return any(_is_poor(f) for f in forecast if f.end_min >= lo and f.start_min <= hi)


def _gates(
    rng: random.Random, spare: int, size: AircraftSize, p: GeneratorParams
) -> tuple[Gate, ...]:
    """The planned gate's pool: one gate for the flight plus the spares.

    The workbook gives gate counts but no gate sizes, so any size here is ours.
    Every candidate gate fits this aircraft: a spare gate that cannot take it
    would not be spare for this flight. Sizes above the aircraft's still vary."""
    count = 1 + spare
    taxiways = max(2, math.ceil(count / 4))
    drawn = [_SIZES[_weighted(rng, p.gate_size_weights)] for _ in range(count)]
    sizes = [max(size, d) for d in drawn]
    return tuple(
        Gate(gate_id=f"G{i + 1}", taxiway_id=f"T{i % taxiways + 1}", max_size=s)
        for i, s in enumerate(sizes)
    )


def _occupancies(
    rng: random.Random,
    gates: Sequence[Gate],
    daily: int,
    lo: int,
    hi: int,
    p: GeneratorParams,
) -> list[GateOccupancy]:
    """Stays of other aircraft on each gate, at a utilisation set by traffic."""
    util = p.gate_util_base + p.gate_util_span * min(1.0, daily / p.gate_util_full_at)
    low, high = p.gate_stay_min
    mean_stay = (low + high) / 2
    mean_gap = mean_stay * (1 - util) / util
    found: list[GateOccupancy] = []
    for gate in gates:
        clock = lo - rng.randint(0, high)
        number = 0
        while clock < hi:
            clock += round(rng.expovariate(1 / mean_gap))
            stay = rng.randint(low, high)
            number += 1
            if clock + stay > lo:
                found.append(
                    GateOccupancy(
                        gate_id=gate.gate_id,
                        flight_id=f"OCC-{gate.gate_id}-{number}",
                        start_min=clock,
                        end_min=clock + stay,
                    )
                )
            clock += stay
    return found


def _with_planned_gate_conflict(
    rng: random.Random,
    occupancies: list[GateOccupancy],
    planned_gate_id: str,
    earliest_gate_in: int,
    free_until: int,
    p: GeneratorParams,
) -> list[GateOccupancy]:
    """On a seeded share of flights, put another stay on the planned gate.

    It starts near the earliest gate-in but never before `free_until`, so the gate
    stays legal at the scheduled time. It has its own random stream, so it shifts no
    other field, and any stay it would overlap on that gate gives way to it.
    """
    if rng.random() >= p.p_planned_gate_conflict:
        return occupancies
    start = max(
        free_until,
        earliest_gate_in - rng.randint(*p.planned_gate_conflict_lead_min),
    )
    end = start + rng.randint(*p.planned_gate_conflict_stay_min)
    kept = [
        o
        for o in occupancies
        if not (
            o.gate_id == planned_gate_id and o.start_min < end and o.end_min > start
        )
    ]
    conflict = GateOccupancy(
        gate_id=planned_gate_id,
        flight_id=f"REASSIGNED-{planned_gate_id}",
        start_min=start,
        end_min=end,
    )
    return [*kept, conflict]


def build_scenario(
    row: DotRow,
    seed: int = 0,
    path: str | os.PathLike[str] | None = None,
    params: GeneratorParams = PARAMS,
) -> Scenario:
    """Build the scenario for one row. Same row and seed give the same result.

    `path` selects the CSV whose cache supplies traffic and the next leg.
    """
    p = params
    key = _seed_key(row, seed)
    cause = dot.cause_of(row)
    decision_point = (
        DecisionPoint.AIRBORNE if cause == "weather" else DecisionPoint.PRE_DEPARTURE
    )
    cause_index = 0 if cause == "weather" else 1

    # Times, on the departure date's clock, destination-local.
    scheduled_arrival = dot.scheduled_arrival_min(row)
    earliest = scheduled_arrival + earliest_basis(row, path).delay_min
    latest = earliest + p.plan_window_min
    taxi_in = dot.typical_taxi_in(row.destination_airport, path)
    scheduled_gate_in = scheduled_arrival + (
        _DEFAULT_TAXI_IN_MIN if taxi_in is None else taxi_in
    )

    # The aircraft.
    size = _aircraft_size(row, seed, p)
    rng_air = _rng(key, "aircraft")
    wake = _wake_of(size, rng_air, p)

    # The airport, from the workbook. With no row for the destination the
    # airport fields below are replaced by "unknown" before returning, so the
    # rules fail closed and the fault is visible; nothing is defaulted.
    workbook = find_limits(row.destination_airport)
    airport_known = workbook is not None
    limits = workbook or AirportLimits(row.destination_airport, "", 1, 0, 1, 1, 0)
    daily = dot.daily_arrivals(row, path)
    rng_airport = _rng(key, "airport")
    runway_ids = [f"R{i + 1}" for i in range(limits.active_runways)]
    closed_runways = {
        r
        for r in runway_ids
        if len(runway_ids) > 1 and rng_airport.random() < p.p_runway_closed[cause_index]
    }
    if len(closed_runways) == len(runway_ids):  # keep the airport open
        closed_runways.discard(runway_ids[-1])
    parallel_groups = _parallel_groups(_rng(key, "runway-groups"), runway_ids, p)
    gates = _gates(rng_airport, limits.spare_gates_at_any_time, size, p)
    taxiway_ids = sorted({g.taxiway_id for g in gates})
    closed_taxiways = {
        t for t in taxiway_ids if rng_airport.random() < p.p_taxiway_closed[cause_index]
    }
    if len(closed_taxiways) == len(taxiway_ids):
        closed_taxiways.discard(taxiway_ids[-1])

    forecast = _forecast(_rng(key, "forecast"), cause, earliest, latest, p)
    poor_in_window = _poor_between(
        forecast, earliest - p.window_margin_min, latest + p.window_margin_min
    )
    flight_rules = FlightRules.IFR if poor_in_window else FlightRules.VFR

    # Real scheduled traffic into the destination, with synthetic wake and runway.
    open_runways = [r for r in runway_ids if r not in closed_runways]
    others = _other_arrivals(
        dot.traffic_near(
            row, earliest - p.window_margin_min, latest + p.window_margin_min, path
        ),
        open_runways,
        key,
        p,
    )

    # Gates: a planned gate that fit at the scheduled time, others in use around it.
    rng_gate = _rng(key, "gates")
    stay = limits.min_turnaround_min
    buffer = rv.rule_value(rv.GATE_BUFFER_MIN).value
    occupancies = _occupancies(
        rng_gate,
        gates,
        daily,
        scheduled_gate_in - 120,
        latest + (_DEFAULT_TAXI_IN_MIN if taxi_in is None else taxi_in) + 240,
        p,
    )
    fitting = [g for g in gates if g.max_size >= size]
    planned = rng_gate.choice(fitting)
    # The planned gate is deliberately legal at schedule: free through the whole
    # stay the gate rule imposes (the next departure, when later than the
    # minimum turnaround), plus the buffer. That is a modelling choice; without
    # it, gate conflicts would be inflated by a plan that was never feasible.
    leg = dot.next_leg(row, path)
    hold_end = scheduled_gate_in + stay
    if leg is not None:
        hold_end = max(hold_end, leg.scheduled_departure_min)
    plan_lo, plan_hi = scheduled_gate_in - buffer, hold_end + buffer
    occupancies = [
        o
        for o in occupancies
        if not (
            o.gate_id == planned.gate_id
            and o.start_min < plan_hi
            and o.end_min > plan_lo
        )
    ]
    # Spare gates are spare: no generated occupant sits on one anywhere in the
    # decision window, from the scheduled gate-in to the end of the longest stay
    # the latest slot can need (gate-in plus the minimum turnaround, or the next
    # departure if later), plus the buffer. The workbook says these gates are
    # free "at any time". Only the planned gate keeps occupants, including the
    # seeded planned-gate conflict below.
    last_gate_in = latest + (_DEFAULT_TAXI_IN_MIN if taxi_in is None else taxi_in)
    window_hi = last_gate_in + stay
    if leg is not None:
        window_hi = max(window_hi, leg.scheduled_departure_min)
    window_lo, window_hi = scheduled_gate_in - buffer, window_hi + buffer
    occupancies = [
        o
        for o in occupancies
        if o.gate_id == planned.gate_id
        or not (o.start_min < window_hi and o.end_min > window_lo)
    ]
    occupancies = _with_planned_gate_conflict(
        _rng(key, "gate-conflict"),
        occupancies,
        planned.gate_id,
        earliest + (_DEFAULT_TAXI_IN_MIN if taxi_in is None else taxi_in),
        plan_hi,
        p,
    )

    # Fuel. Holding burn is the workbook's. On arrival the aircraft carries the
    # workbook's 45 minutes of holding fuel, varied by a seeded draw (see
    # `surplus_tiers`), on top of the trip fuel and any alternate.
    rng_fuel = _rng(key, "fuel")
    cruise = max(
        1,
        round(
            p.cruise_burn[size.value - 1]
            * (1 + rng_fuel.uniform(-p.burn_jitter, p.burn_jitter))
        ),
    )
    hold = rv.hold_burn_kg_per_min(size)
    alternate = round(cruise * rng_fuel.uniform(*p.alternate_min))
    block = row.scheduled_time
    if block is None:
        block = (
            round(row.distance / 7.5) + 30
            if row.distance is not None
            else p.default_block_min
        )
    block = max(block, p.min_block_min)  # a zero or negative block is bad data
    if decision_point is DecisionPoint.AIRBORNE:
        remaining = block * rng_fuel.uniform(*p.airborne_remaining)
        tier = p.surplus_tiers[_weighted(rng_fuel, [t[0] for t in p.surplus_tiers])]
        variation_min = rng_fuel.uniform(tier[1], tier[2])
        needs_alternate = _poor_between(forecast, earliest - 60, earliest + 60)
    else:
        remaining = float(block)
        variation_min = rng_fuel.uniform(*p.surplus_pre_departure_min)
        needs_alternate = True  # loaded on the ground for any forecast
    trip = max(1, round(remaining * cruise))
    spare_min = rv.rule_value(rv.FUEL_SPARE_ON_ARRIVAL_MIN).value
    on_board = trip + round((spare_min + variation_min) * hold)
    if needs_alternate:
        on_board += alternate

    # The next leg is real; whether it can be held is synthetic.
    next_departure: Sourced[int]
    hard: Sourced[bool]
    if leg is None:
        next_departure = _sourced(None, DERIVED)
        hard = _sourced(False, DERIVED)
    else:
        next_departure = _sourced(leg.scheduled_departure_min, DERIVED)
        hard = _sourced(_rng(key, "next-leg").random() < p.p_next_leg_hard, SYNTHETIC)

    rng_ops = _rng(key, "ops")
    connections = tuple(
        Connection(
            passengers=rng_ops.randint(*p.connection_passengers[size.value - 1]),
            departure_min=scheduled_gate_in + rng_ops.randint(*p.connection_gap_min),
        )
        for _ in range(_weighted(rng_ops, p.connection_count_weights))
    )
    # An 8-hour shift (workbook); the seeded part is how much of it has run.
    shift_end = (
        scheduled_gate_in
        - rng_ops.randint(*p.shift_elapsed_at_gate_in_min)
        + rv.rule_value(rv.GROUND_SHIFT_MIN).value
    )

    # Decision time and crew duty start: from the schedule only, no hindsight.
    departure_min = dot.hhmm_to_min(row.scheduled_departure)
    if cause == "weather":
        decision_time = scheduled_arrival - p.window_margin_min
    else:
        decision_time = departure_min + INBOUND_KNOWN_MARGIN_MIN
    rng_crew = _rng(key, "crew")
    late_in_duty = rng_crew.random() < p.p_crew_late_in_duty
    crew_report = departure_min - rng_crew.randint(
        *(p.crew_report_late_lead_min if late_in_duty else p.crew_report_lead_min)
    )

    def known[T](value: T) -> Sourced[T]:
        """A synthetic airport field, unknown when the workbook has no row."""
        return _sourced(value if airport_known else None, SYNTHETIC)

    return Scenario(
        scenario_id=_sourced(
            f"DOT-{row.year}{row.month:02d}{row.day:02d}-{row.flight_id}-"
            f"{row.origin_airport}{row.destination_airport}-s{seed}",
            DERIVED,
        ),
        flight_id=_sourced(row.flight_id, REAL),
        decision_point=_sourced(decision_point, DERIVED),
        flight_rules=_sourced(flight_rules, SYNTHETIC),
        wake_category=_sourced(wake, SYNTHETIC),
        aircraft_size=_sourced(size, SYNTHETIC),
        earliest_arrival_min=_sourced(earliest, DERIVED),
        latest_arrival_min=_sourced(latest, DERIVED),
        taxi_in_min=_sourced(taxi_in, DERIVED),
        fuel_on_board_kg=_sourced(on_board, SYNTHETIC),
        trip_fuel_kg=_sourced(trip, SYNTHETIC),
        cruise_burn_kg_per_min=_sourced(cruise, SYNTHETIC),
        hold_burn_kg_per_min=_sourced(hold, SYNTHETIC),
        alternate_fuel_kg=_sourced(alternate, SYNTHETIC),
        destination_forecast=_sourced(forecast, SYNTHETIC),
        runways=known(
            tuple(
                Runway(
                    runway_id=r,
                    closed=r in closed_runways,
                    parallel_group=parallel_groups.get(r),
                )
                for r in runway_ids
            )
        ),
        taxiways=known(
            tuple(
                Taxiway(taxiway_id=t, closed=t in closed_taxiways) for t in taxiway_ids
            )
        ),
        gates=known(gates),
        other_arrivals=_sourced(others, SYNTHETIC),
        gate_occupancies=known(tuple(occupancies)),
        planned_gate=known(planned.gate_id),
        next_departure_min=next_departure,
        next_leg_turnaround_hard=hard,
        ground_shift_end_min=_sourced(shift_end, SYNTHETIC),
        connections=_sourced(connections, SYNTHETIC),
        decision_time_min=_sourced(decision_time, DERIVED),
        crew_report_min=_sourced(crew_report, SYNTHETIC),
        airport_ops_per_hour=known(limits.max_runway_ops_per_hour),
        min_turnaround_min=known(limits.min_turnaround_min),
    )


def _other_arrivals(
    arrivals: Sequence[dot.ScheduledArrival],
    open_runways: Sequence[str],
    key: str,
    p: GeneratorParams,
) -> tuple[OtherArrival, ...]:
    """Real scheduled flights with a synthetic wake class and open runway.

    Each ID is the flight, its origin and its scheduled departure time, with a
    counter if the file still repeats one, so IDs are unique within the
    scenario and never equal the scenario's own flight ID (which has no
    suffix). Wake and runway are seeded by ID and time, so they are stable
    however the window moves.
    """
    seen: Counter[str] = Counter()
    found: list[OtherArrival] = []
    for arrival in arrivals:
        hour, minute = divmod(arrival.departure_min % MINUTES_PER_DAY, 60)
        flight_id = f"{arrival.flight_id}-{arrival.origin}-{hour:02d}{minute:02d}"
        seen[flight_id] += 1
        if seen[flight_id] > 1:
            flight_id = f"{flight_id}#{seen[flight_id]}"
        rng = _rng(key, f"other|{flight_id}|{arrival.arrival_min}")
        found.append(
            OtherArrival(
                flight_id=flight_id,
                wake_category=_other_wake(rng, p),
                runway_id=rng.choice(open_runways),
                time_min=arrival.arrival_min,
            )
        )
    return tuple(found)
