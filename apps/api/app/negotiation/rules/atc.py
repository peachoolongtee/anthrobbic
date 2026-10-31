"""Air traffic control rules. Each is pure and returns every violation."""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import Domain, Package, Rule, Scenario, Violation

WAKE_SEPARATION = "ATC-WAKE-SEP"
RUNWAY_CLOSED = "ATC-RWY-CLOSED"
TAXIWAY_CLOSED = "ATC-TWY-CLOSED"
RUNWAY_THROUGHPUT = "ATC-RWY-THROUGHPUT"


def _violation(rule_id: str, message: str, source: str) -> Violation:
    return Violation(rule_id=rule_id, domain=Domain.ATC, message=message, source=source)


def required_separation_min(leader_nm: int) -> int:
    """Minutes needed to fly `leader_nm` at the approach speed, rounded up."""
    speed_kt = rv.rule_value(rv.APPROACH_GROUND_SPEED_KT).value
    per_hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    return (leader_nm * per_hour + speed_kt - 1) // speed_kt


def check_wake_separation(
    scenario: Scenario, package: Package
) -> tuple[Violation, ...]:
    """In-trail separation against every other arrival on the same runway."""
    source = "scenario.other_arrivals, scenario.wake_category"
    wake = scenario.wake_category.value
    arrivals = scenario.other_arrivals.value
    missing: list[Violation] = []
    if wake is None:
        missing.append(_violation(WAKE_SEPARATION, "own wake category unknown", source))
    if arrivals is None:
        missing.append(_violation(WAKE_SEPARATION, "other arrivals unknown", source))
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
                )
            )
    return tuple(found)


def check_runway_closed(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The runway must be known and open."""
    source = f"scenario.runways ({scenario.runways.provenance.value})"
    runways = scenario.runways.value
    if runways is None:
        return (_violation(RUNWAY_CLOSED, "runway status unknown", source),)
    runway_id = package.slot.runway_id
    matches = [r for r in runways if r.runway_id == runway_id]
    if not matches:
        return (
            _violation(
                RUNWAY_CLOSED, f"runway {runway_id} is not in the scenario", source
            ),
        )
    if any(r.closed for r in matches):
        return (_violation(RUNWAY_CLOSED, f"runway {runway_id} is closed", source),)
    return ()


def check_taxiway_closed(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The taxiway serving the gate must be known and open."""
    source = f"scenario.gates, scenario.taxiways ({scenario.taxiways.provenance.value})"
    gates = scenario.gates.value
    taxiways = scenario.taxiways.value
    if gates is None or taxiways is None:
        return (_violation(TAXIWAY_CLOSED, "gate or taxiway map unknown", source),)
    gate = next((g for g in gates if g.gate_id == package.gate_id), None)
    if gate is None:
        return (
            _violation(
                TAXIWAY_CLOSED, f"gate {package.gate_id} is not in the scenario", source
            ),
        )
    routes = [t for t in taxiways if t.taxiway_id == gate.taxiway_id]
    if not routes:
        return (
            _violation(
                TAXIWAY_CLOSED,
                f"taxiway {gate.taxiway_id} for gate {gate.gate_id} is not in the "
                "scenario",
                source,
            ),
        )
    if any(t.closed for t in routes):
        return (
            _violation(
                TAXIWAY_CLOSED,
                f"taxiway {gate.taxiway_id} serving gate {gate.gate_id} is closed",
                source,
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
        missing.append(_violation(RUNWAY_THROUGHPUT, "other arrivals unknown", source))
    if flight_rules is None:
        missing.append(_violation(RUNWAY_THROUGHPUT, "flight rules unknown", source))
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
            ),
        )
    return ()


RULES: tuple[Rule, ...] = (
    Rule(
        WAKE_SEPARATION,
        Domain.ATC,
        "FAA JO 7110.65 5-5-4",
        "Wake in-trail separation against other arrivals on the runway",
        check_wake_separation,
    ),
    Rule(
        RUNWAY_CLOSED,
        Domain.ATC,
        "scenario.runways",
        "The arrival runway must be known and open",
        check_runway_closed,
    ),
    Rule(
        TAXIWAY_CLOSED,
        Domain.ATC,
        "scenario.taxiways",
        "The taxiway serving the gate must be known and open",
        check_taxiway_closed,
    ),
    Rule(
        RUNWAY_THROUGHPUT,
        Domain.ATC,
        "rule_values.runway_hourly_arrivals (IFR/VFR)",
        "Arrivals per rolling hour on the runway must not exceed the cap",
        check_runway_throughput,
    ),
)
