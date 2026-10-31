"""Air traffic control rules. Each is pure and returns every violation."""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    Domain,
    Package,
    PublicReason,
    Rule,
    Scenario,
    Violation,
    WakeCategory,
)
from app.negotiation.rules.shared import (
    gates_with_id,
    own_flight_is_ambiguous,
    runway_group,
)

WAKE_SEPARATION = "ATC-WAKE-SEP"
RUNWAY_CLOSED = "ATC-RWY-CLOSED"
TAXIWAY_CLOSED = "ATC-TWY-CLOSED"
RUNWAY_THROUGHPUT = "ATC-RWY-THROUGHPUT"
SLOT_WINDOW = "ATC-SLOT-WINDOW"


def _violation(
    rule_id: str,
    message: str,
    source: str,
    observed: int,
    limit: int,
    unit: str,
) -> Violation:
    return Violation(
        rule_id=rule_id,
        domain=Domain.ATC,
        message=message,
        source=source,
        observed=observed,
        limit=limit,
        unit=unit,
    )


def _missing(
    rule_id: str, name: str, source: str, reason: str = "unknown"
) -> Violation:
    return Violation.missing_data(rule_id, Domain.ATC, name, source, reason)


def required_separation_min(leader_nm: int, follower: WakeCategory) -> int:
    """Minutes needed to fly `leader_nm` at the follower's approach speed,
    rounded up."""
    speed_kt = rv.approach_speed(follower).value
    per_hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    return (leader_nm * per_hour + speed_kt - 1) // speed_kt


def check_wake_separation(
    scenario: Scenario, package: Package
) -> tuple[Violation, ...]:
    """In-trail separation against every other arrival on the same runway.

    Parallel runways in one group count as one runway. The scenario's own
    flight is skipped. An arrival that names a runway the scenario does not
    list is a missing-data violation, never dropped. `observed` is the gap in
    minutes and `limit` the minimum gap.
    """
    source = "scenario.other_arrivals, scenario.wake_category, scenario.runways"
    wake = scenario.wake_category.value
    arrivals = scenario.other_arrivals.value
    runways = scenario.runways.value
    own_id = scenario.flight_id.value
    missing: list[Violation] = []
    if wake is None:
        missing.append(_missing(WAKE_SEPARATION, "own wake category", source))
    if arrivals is None:
        missing.append(_missing(WAKE_SEPARATION, "other arrivals", source))
    if runways is None:
        missing.append(_missing(WAKE_SEPARATION, "runway list", source))
    if wake is None or arrivals is None or runways is None:
        return tuple(missing)

    known = {r.runway_id for r in runways}
    same_runway = runway_group(runways, package.slot.runway_id)
    found: list[Violation] = []
    ambiguous = own_flight_is_ambiguous((a.flight_id for a in arrivals), own_id)
    if ambiguous:
        found.append(
            _missing(WAKE_SEPARATION, f"flight id {own_id}", source, "ambiguous")
        )
    for other in arrivals:
        if not ambiguous and own_id is not None and other.flight_id == own_id:
            continue
        if other.runway_id not in known:
            found.append(
                _missing(
                    WAKE_SEPARATION,
                    f"runway {other.runway_id} of arrival {other.flight_id}",
                    source,
                )
            )
            continue
        if other.runway_id not in same_runway:
            continue
        # At equal times the other flight is treated as the leader; either
        # order fails because the required gap is positive.
        other_leads = other.time_min <= package.slot.time_min
        leader, follower = (
            (other.wake_category, wake) if other_leads else (wake, other.wake_category)
        )
        sep = rv.wake_separation(leader, follower)
        need_min = required_separation_min(sep.value, follower)
        gap_min = abs(package.slot.time_min - other.time_min)
        if gap_min < need_min:
            found.append(
                _violation(
                    WAKE_SEPARATION,
                    f"{gap_min} min apart from {other.flight_id} on runway "
                    f"{other.runway_id}; {leader.value} then {follower.value} "
                    f"needs {sep.value} nm = {need_min} min",
                    rv.reference(sep),
                    gap_min,
                    need_min,
                    "min",
                )
            )
    return tuple(found)


def check_runway_closed(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The runway must be known and open. A closed runway is 1 against a limit of 0.

    If the ID is listed more than once, any closed entry closes it.
    """
    source = f"scenario.runways ({scenario.runways.provenance.value})"
    runways = scenario.runways.value
    if runways is None:
        return (_missing(RUNWAY_CLOSED, "runway status", source),)
    runway_id = package.slot.runway_id
    matches = [r for r in runways if r.runway_id == runway_id]
    if not matches:
        return (_missing(RUNWAY_CLOSED, f"runway {runway_id}", source),)
    if any(r.closed for r in matches):
        return (
            _violation(
                RUNWAY_CLOSED,
                f"runway {runway_id} is closed",
                source,
                1,
                0,
                "closed runways",
            ),
        )
    return ()


def check_taxiway_closed(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The taxiway serving the gate must be known and open.

    A gate listed twice is a missing-data violation. If a taxiway ID is listed
    more than once, any closed entry closes it.
    """
    source = f"scenario.gates, scenario.taxiways ({scenario.taxiways.provenance.value})"
    gates = scenario.gates.value
    taxiways = scenario.taxiways.value
    if gates is None or taxiways is None:
        return (_missing(TAXIWAY_CLOSED, "gate or taxiway map", source),)
    listed = gates_with_id(gates, package.gate_id)
    if not listed:
        return (_missing(TAXIWAY_CLOSED, f"gate {package.gate_id}", source),)
    if len(listed) > 1:
        return (
            _missing(
                TAXIWAY_CLOSED,
                f"gate {package.gate_id} (listed more than once)",
                source,
                "ambiguous",
            ),
        )
    gate = listed[0]
    routes = [t for t in taxiways if t.taxiway_id == gate.taxiway_id]
    if not routes:
        return (_missing(TAXIWAY_CLOSED, f"taxiway {gate.taxiway_id}", source),)
    if any(t.closed for t in routes):
        return (
            _violation(
                TAXIWAY_CLOSED,
                f"taxiway {gate.taxiway_id} serving gate {gate.gate_id} is closed",
                source,
                1,
                0,
                "closed taxiways",
            ),
        )
    return ()


def check_runway_throughput(
    scenario: Scenario, package: Package
) -> tuple[Violation, ...]:
    """No rolling hour containing this arrival may exceed the airport's cap.

    The cap is the workbook's `max_runway_ops_per_hour`, read as an airport
    total, so arrivals on every runway count together. Only arrivals are
    counted, because the scenario holds no departures: the rule therefore
    understates movements and is the more lenient side of the workbook limit.
    The scenario's own flight is skipped; an arrival naming an unlisted runway
    is a missing-data violation; an unknown or non-positive cap fails closed.
    """
    arrivals = scenario.other_arrivals.value
    runways = scenario.runways.value
    cap_value = scenario.airport_ops_per_hour.value
    own_id = scenario.flight_id.value
    source = "scenario.other_arrivals, scenario.runways, scenario.airport_ops_per_hour"
    missing: list[Violation] = []
    if arrivals is None:
        missing.append(_missing(RUNWAY_THROUGHPUT, "other arrivals", source))
    if runways is None:
        missing.append(_missing(RUNWAY_THROUGHPUT, "runway list", source))
    if cap_value is None:
        missing.append(_missing(RUNWAY_THROUGHPUT, "airport movement cap", source))
    elif cap_value <= 0:
        missing.append(
            _missing(RUNWAY_THROUGHPUT, "airport movement cap", source, "invalid")
        )
    if arrivals is None or runways is None or cap_value is None or cap_value <= 0:
        return tuple(missing)
    cap = rv.airport_ops_per_hour(cap_value)

    hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    mine = package.slot.time_min
    known = {r.runway_id for r in runways}
    found: list[Violation] = []
    times: list[int] = []
    ambiguous = own_flight_is_ambiguous((a.flight_id for a in arrivals), own_id)
    if ambiguous:
        found.append(
            _missing(RUNWAY_THROUGHPUT, f"flight id {own_id}", source, "ambiguous")
        )
    for other in arrivals:
        if not ambiguous and own_id is not None and other.flight_id == own_id:
            continue
        if other.runway_id not in known:
            found.append(
                _missing(
                    RUNWAY_THROUGHPUT,
                    f"runway {other.runway_id} of arrival {other.flight_id}",
                    source,
                )
            )
        else:
            times.append(other.time_min)
    times.append(mine)
    # The busiest hour containing this arrival starts at some arrival that is
    # no later than this one and less than an hour before it.
    worst = max(
        sum(1 for t in times if start <= t < start + hour)
        for start in times
        if start <= mine < start + hour
    )
    if worst > cap.value:
        found.append(
            _violation(
                RUNWAY_THROUGHPUT,
                f"{worst} arrivals within an hour at the airport; the workbook "
                f"cap is {cap.value} movements an hour (arrivals only counted)",
                rv.reference(cap),
                worst,
                cap.value,
                "arrivals per hour",
            )
        )
    return tuple(found)


def check_slot_window(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The slot must lie inside the planning window and on its grid.

    Fails closed on unknown window bounds. The grid starts at the earliest
    arrival and steps by the slot step.
    """
    source = "scenario.earliest_arrival_min, scenario.latest_arrival_min"
    earliest = scenario.earliest_arrival_min.value
    latest = scenario.latest_arrival_min.value
    missing: list[Violation] = []
    if earliest is None:
        missing.append(_missing(SLOT_WINDOW, "earliest arrival", source))
    if latest is None:
        missing.append(_missing(SLOT_WINDOW, "latest arrival", source))
    if earliest is None or latest is None:
        return tuple(missing)

    slot = package.slot.time_min
    found: list[Violation] = []
    if slot < earliest:
        found.append(
            _violation(
                SLOT_WINDOW,
                f"slot {slot} is before the earliest arrival {earliest}",
                source,
                slot,
                earliest,
                "min",
            )
        )
    if slot > latest:
        found.append(
            _violation(
                SLOT_WINDOW,
                f"slot {slot} is after the latest arrival {latest}",
                source,
                slot,
                latest,
                "min",
            )
        )
    step = rv.rule_value(rv.SLOT_STEP_MIN)
    off_grid = (slot - earliest) % step.value
    if off_grid != 0:
        found.append(
            _violation(
                SLOT_WINDOW,
                f"slot {slot} is {off_grid} min off the {step.value} min grid",
                rv.reference(step),
                off_grid,
                0,
                "min off grid",
            )
        )
    return tuple(found)


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id=WAKE_SEPARATION,
        domain=Domain.ATC,
        source="FAA JO 7110.65BB para 5-5-4",
        description="Wake in-trail separation against other arrivals on the runway",
        public_reason=PublicReason.SAFETY_MARGIN,
        check=check_wake_separation,
    ),
    Rule(
        rule_id=RUNWAY_CLOSED,
        domain=Domain.ATC,
        source="scenario.runways",
        description="The arrival runway must be known and open",
        public_reason=PublicReason.RESOURCE_CLOSED,
        check=check_runway_closed,
    ),
    Rule(
        rule_id=TAXIWAY_CLOSED,
        domain=Domain.ATC,
        source="scenario.taxiways",
        description="The taxiway serving the gate must be known and open",
        public_reason=PublicReason.RESOURCE_CLOSED,
        check=check_taxiway_closed,
    ),
    Rule(
        rule_id=RUNWAY_THROUGHPUT,
        domain=Domain.ATC,
        source="challenge workbook: max_runway_ops_per_hour, per airport",
        description="Arrivals per rolling hour at the airport must not exceed "
        "the workbook cap",
        public_reason=PublicReason.CAPACITY_LIMIT,
        check=check_runway_throughput,
    ),
    Rule(
        rule_id=SLOT_WINDOW,
        domain=Domain.ATC,
        source="scenario.earliest_arrival_min, scenario.latest_arrival_min",
        description="The arrival slot must be inside the planning window and on "
        "the slot grid",
        public_reason=PublicReason.SCHEDULE_LIMIT,
        check=check_slot_window,
    ),
)
