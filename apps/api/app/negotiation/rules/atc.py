"""Air traffic control rules. Each is pure and returns every violation."""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    Domain,
    Package,
    PublicReason,
    Rule,
    Scenario,
    Violation,
)

WAKE_SEPARATION = "ATC-WAKE-SEP"
RUNWAY_CLOSED = "ATC-RWY-CLOSED"
TAXIWAY_CLOSED = "ATC-TWY-CLOSED"
RUNWAY_THROUGHPUT = "ATC-RWY-THROUGHPUT"


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


def _missing(rule_id: str, name: str, source: str) -> Violation:
    return Violation.missing_data(rule_id, Domain.ATC, name, source)


def required_separation_min(leader_nm: int) -> int:
    """Minutes needed to fly `leader_nm` at the approach speed, rounded up."""
    speed_kt = rv.rule_value(rv.APPROACH_GROUND_SPEED_KT).value
    per_hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    return (leader_nm * per_hour + speed_kt - 1) // speed_kt


def check_wake_separation(
    scenario: Scenario, package: Package
) -> tuple[Violation, ...]:
    """In-trail separation against every other arrival on the same runway.

    `observed` is the gap in minutes and `limit` the minimum gap.
    """
    source = "scenario.other_arrivals, scenario.wake_category"
    wake = scenario.wake_category.value
    arrivals = scenario.other_arrivals.value
    missing: list[Violation] = []
    if wake is None:
        missing.append(_missing(WAKE_SEPARATION, "own wake category", source))
    if arrivals is None:
        missing.append(_missing(WAKE_SEPARATION, "other arrivals", source))
    if wake is None or arrivals is None:
        return tuple(missing)

    found: list[Violation] = []
    for other in arrivals:
        if other.runway_id != package.slot.runway_id:
            continue
        # At equal times the other flight is treated as the leader; either
        # order fails because the required gap is positive.
        other_leads = other.time_min <= package.slot.time_min
        leader, follower = (
            (other.wake_category, wake) if other_leads else (wake, other.wake_category)
        )
        sep = rv.wake_separation(leader, follower)
        need_min = required_separation_min(sep.value)
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
    """The runway must be known and open. A closed runway is 1 against a limit of 0."""
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
    """The taxiway serving the gate must be known and open."""
    source = f"scenario.gates, scenario.taxiways ({scenario.taxiways.provenance.value})"
    gates = scenario.gates.value
    taxiways = scenario.taxiways.value
    if gates is None or taxiways is None:
        return (_missing(TAXIWAY_CLOSED, "gate or taxiway map", source),)
    gate = next((g for g in gates if g.gate_id == package.gate_id), None)
    if gate is None:
        return (_missing(TAXIWAY_CLOSED, f"gate {package.gate_id}", source),)
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
    """No rolling hour containing this arrival may exceed the runway cap."""
    arrivals = scenario.other_arrivals.value
    flight_rules = scenario.flight_rules.value
    source = "scenario.other_arrivals, scenario.flight_rules"
    missing: list[Violation] = []
    if arrivals is None:
        missing.append(_missing(RUNWAY_THROUGHPUT, "other arrivals", source))
    if flight_rules is None:
        missing.append(_missing(RUNWAY_THROUGHPUT, "flight rules", source))
    if arrivals is None or flight_rules is None:
        return tuple(missing)
    cap = rv.runway_hourly_arrivals(flight_rules)

    hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    runway_id = package.slot.runway_id
    mine = package.slot.time_min
    times = [a.time_min for a in arrivals if a.runway_id == runway_id]
    times.append(mine)
    # The busiest hour containing this arrival starts at some arrival that is
    # no later than this one and less than an hour before it.
    worst = max(
        sum(1 for t in times if start <= t < start + hour)
        for start in times
        if start <= mine < start + hour
    )
    if worst > cap.value:
        return (
            _violation(
                RUNWAY_THROUGHPUT,
                f"{worst} arrivals within an hour on runway {runway_id}; "
                f"cap is {cap.value} under {flight_rules.value.upper()}",
                rv.reference(cap),
                worst,
                cap.value,
                "arrivals per hour",
            ),
        )
    return ()


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
        source="rule_values.runway_hourly_arrivals (IFR/VFR)",
        description="Arrivals per rolling hour on the runway must not exceed the cap",
        public_reason=PublicReason.CAPACITY_LIMIT,
        check=check_runway_throughput,
    ),
)
