"""Delay spread: how a late arrival carries down the same aircraft's day.

Everything here comes from the schedule columns and the workbook's minimum
turnarounds. It is a projection of what the schedule implies, not of what the
aircraft did, so no as-flown column is read (see `dot.later_legs`).

Each leg's earliest departure is the previous arrival plus the minimum turnaround
at the airport it leaves from. The knock-on is how far that passes the scheduled
departure, and the whole of it is carried to the leg's arrival: nothing is
recovered in the air or on the ground beyond the gaps the schedule already has.
"""

import os
from collections.abc import Sequence
from typing import Final

from app.api import adapter
from app.api.wire import DelaySpread, LegProjection, SpreadLeg
from app.negotiation import dot
from app.negotiation.airport_limits import find_limits
from app.negotiation.contracts import Provenance
from app.negotiation.dot import MINUTES_PER_DAY, DotRow, LaterLeg

NOTE: Final = (
    "This is a scheduled projection, not what actually happened. It carries the "
    "plan's arrival down the aircraft's later flights using the schedule and each "
    "airport's minimum turnaround (a synthetic organiser limit), with no recovery "
    "beyond the gaps already in the schedule."
)
NO_PLAN: Final = "No plan was chosen, so there is no arrival to project from."

type Projected = tuple[LegProjection | None, str | None]


def stamp(minute: int) -> str:
    """A clock time, marked when the minute falls on the next day."""
    text = adapter.clock(minute)
    return f"{text} next day" if minute >= MINUTES_PER_DAY else text


def project(
    plan_arrival_min: int, airport: str, legs: Sequence[LaterLeg]
) -> list[Projected]:
    """A projection, or the reason there is none, for each leg in order.

    The aircraft starts at `airport` at `plan_arrival_min`. Once a leg cannot be
    carried (it leaves from somewhere else, or its airport has no workbook
    turnaround) no later leg can either, because its input is unknown.
    """
    out: list[Projected] = []
    arrival = plan_arrival_min
    at = airport
    stopped: str | None = None
    for leg in legs:
        limits = find_limits(leg.origin)
        if stopped is None and leg.origin != at:
            stopped = (
                f"The aircraft is at {at} but this flight leaves from "
                f"{leg.origin}, so the delay is not carried to it."
            )
        if stopped is None and limits is None:
            stopped = (
                f"No minimum turnaround is on file for {leg.origin}, so the "
                "delay cannot be carried past it."
            )
        if stopped is not None or limits is None:
            out.append((None, stopped))
            continue
        earliest = arrival + limits.min_turnaround_min
        knock_on = max(0, earliest - leg.scheduled_departure_min)
        arrival = leg.scheduled_arrival_min + knock_on
        at = leg.destination
        out.append(
            (
                LegProjection(
                    earliest_departure=stamp(earliest),
                    turnaround_min=limits.min_turnaround_min,
                    turnaround_provenance=Provenance.SYNTHETIC,
                    knock_on_min=knock_on,
                    projected_arrival=stamp(arrival),
                    provenance=Provenance.DERIVED,
                ),
                None,
            )
        )
    return out


def delay_spread(
    row: DotRow,
    plan_arrival_min: int | None,
    path: str | os.PathLike[str] | None = None,
) -> DelaySpread:
    """The row's tail's later flights that day, projected from `plan_arrival_min`
    (minutes from the departure date's midnight, destination clock) when given.
    With None the chain is listed from the schedule alone."""
    legs = dot.later_legs(row, path)
    projected: list[Projected] = (
        [(None, NO_PLAN)] * len(legs)
        if plan_arrival_min is None
        else project(plan_arrival_min, row.destination_airport, legs)
    )
    return DelaySpread(
        flight_id=row.flight_id,
        route=adapter.route(row.origin_airport, row.destination_airport),
        tail_number=row.tail_number,
        scheduled_arrival=stamp(dot.scheduled_arrival_min(row)),
        plan_arrival=None if plan_arrival_min is None else stamp(plan_arrival_min),
        plan_arrival_provenance=(
            None if plan_arrival_min is None else Provenance.DERIVED
        ),
        legs=tuple(
            SpreadLeg(
                flight_id=leg.flight_id,
                route=adapter.route(leg.origin, leg.destination),
                scheduled_departure=stamp(leg.scheduled_departure_min),
                scheduled_arrival=stamp(leg.scheduled_arrival_min),
                provenance=Provenance.REAL,
                projection=projection,
                unprojected_reason=reason,
            )
            for leg, (projection, reason) in zip(legs, projected, strict=True)
        ),
        note=NOTE,
    )
