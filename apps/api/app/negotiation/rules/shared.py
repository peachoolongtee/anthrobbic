"""Lookups several rules share. Pure, and they decide nothing on their own."""

from collections.abc import Iterable, Sequence

from app.negotiation import rule_values as rv
from app.negotiation.contracts import FlightRules, Gate, Runway, WeatherPeriod


def gates_with_id(gates: Sequence[Gate], gate_id: str) -> tuple[Gate, ...]:
    """Every gate entry with this ID. More than one is a data fault."""
    return tuple(g for g in gates if g.gate_id == gate_id)


def runway_group(runways: Sequence[Runway], runway_id: str) -> frozenset[str]:
    """The runway IDs that count as this runway: itself plus every runway that
    shares a parallel group with it. A runway with no group stands alone."""
    groups = {
        r.parallel_group
        for r in runways
        if r.runway_id == runway_id and r.parallel_group is not None
    }
    members = {runway_id}
    members.update(r.runway_id for r in runways if r.parallel_group in groups)
    return frozenset(members)


def is_poor(period: WeatherPeriod) -> bool:
    """Below the ceiling or visibility minimum that lets an alternate be skipped."""
    ceiling = rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value
    visibility = rv.rule_value(rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI).value
    return period.ceiling_ft < ceiling or period.visibility_tenth_mi < visibility


def poor_or_unknown_at(forecast: Sequence[WeatherPeriod] | None, time_min: int) -> bool:
    """True when the forecast is missing, does not cover this minute, or any
    period covering it is poor. Periods are closed intervals."""
    if forecast is None:
        return True
    covering = [p for p in forecast if p.start_min <= time_min <= p.end_min]
    return not covering or any(is_poor(p) for p in covering)


def airport_conditions(
    forecast: Sequence[WeatherPeriod] | None, time_min: int
) -> FlightRules:
    """The conditions that set the runway cap at this minute: IFR when the
    forecast is poor or unknown there, otherwise VFR. The throughput rule and
    the card both read the cap through this one function."""
    return (
        FlightRules.IFR if poor_or_unknown_at(forecast, time_min) else FlightRules.VFR
    )


def own_flight_is_ambiguous(flight_ids: Iterable[str], own_id: str | None) -> bool:
    """True when more than one row carries the scenario's own flight ID.

    One such row is the flight itself and is skipped. Two or more cannot be told
    apart from other traffic, so none is skipped and the rule fails closed.
    """
    return own_id is not None and sum(1 for f in flight_ids if f == own_id) > 1
