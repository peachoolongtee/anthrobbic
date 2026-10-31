"""Ground rules. Each is pure and returns every violation."""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    Domain,
    Package,
    PublicReason,
    Rule,
    Scenario,
    Violation,
)
from app.negotiation.rules.shared import gates_with_id

GATE_OVERLAP = "GND-GATE-OVERLAP"
GATE_SIZE = "GND-GATE-SIZE"
TURNAROUND = "GND-TURNAROUND"


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
        domain=Domain.GROUND,
        message=message,
        source=source,
        observed=observed,
        limit=limit,
        unit=unit,
    )


def _missing(
    rule_id: str, name: str, source: str, reason: str = "unknown"
) -> Violation:
    return Violation.missing_data(rule_id, Domain.GROUND, name, source, reason)


def taxi_problem(scenario: Scenario) -> str | None:
    """ "unknown" or "invalid" (negative) when taxi-in cannot be used, else None."""
    taxi = scenario.taxi_in_min.value
    if taxi is None:
        return "unknown"
    return "invalid" if taxi < 0 else None


def gate_in_min(scenario: Scenario, package: Package) -> int | None:
    """When the aircraft reaches the gate: landing slot plus taxi-in. None if
    taxi-in is unknown or invalid."""
    taxi = scenario.taxi_in_min.value
    if taxi is None or taxi < 0:
        return None
    return package.slot.time_min + taxi


def turnaround_min(scenario: Scenario) -> rv.RuleValue | None:
    """Minimum turnaround for this aircraft's size class."""
    size = scenario.aircraft_size.value
    return None if size is None else rv.turnaround(size)


def gate_stay_end_min(scenario: Scenario, package: Package) -> int | None:
    """When the aircraft frees its gate.

    No tow is modelled, so it holds the gate until its next departure when that
    is known and later than gate-in plus the minimum turnaround; otherwise it
    holds it for the minimum turnaround.
    """
    start = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    if start is None or stay is None:
        return None
    end = start + stay.value
    depart = scenario.next_departure_min.value
    return end if depart is None or depart <= end else depart


def check_gate_overlap(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The aircraft's gate stay, plus buffer, must not touch another's.

    The scenario's own flight is skipped. An occupancy that names a gate the
    scenario does not list is a missing-data violation, never dropped.
    `observed` is the clear gap in minutes between the two stays (negative when
    they overlap) and `limit` is the buffer.
    """
    buffer = rv.rule_value(rv.GATE_BUFFER_MIN)
    source = rv.reference(buffer)
    start = gate_in_min(scenario, package)
    end = gate_stay_end_min(scenario, package)
    stay = turnaround_min(scenario)
    occupancies = scenario.gate_occupancies.value
    gates = scenario.gates.value
    own_id = scenario.flight_id.value
    missing: list[Violation] = []
    taxi = taxi_problem(scenario)
    if taxi is not None:
        missing.append(_missing(GATE_OVERLAP, "taxi-in time", source, taxi))
    if stay is None:
        missing.append(_missing(GATE_OVERLAP, "aircraft size", source))
    if occupancies is None:
        missing.append(_missing(GATE_OVERLAP, "gate occupancies", source))
    if gates is None:
        missing.append(_missing(GATE_OVERLAP, "gate map", source))
    if (
        start is None
        or end is None
        or stay is None
        or occupancies is None
        or gates is None
    ):
        return tuple(missing)

    known = {g.gate_id for g in gates}
    found: list[Violation] = []
    for other in occupancies:
        if own_id is not None and other.flight_id == own_id:
            continue
        if other.gate_id not in known:
            found.append(
                _missing(
                    GATE_OVERLAP,
                    f"gate {other.gate_id} of occupancy {other.flight_id}",
                    source,
                )
            )
            continue
        if other.gate_id != package.gate_id:
            continue
        clear_min = max(start - other.end_min, other.start_min - end)
        if clear_min < buffer.value:
            found.append(
                _violation(
                    GATE_OVERLAP,
                    f"gate {package.gate_id} stay {start}-{end} is {clear_min} min "
                    f"clear of {other.flight_id} at {other.start_min}-"
                    f"{other.end_min}; buffer is {buffer.value} min",
                    source,
                    clear_min,
                    buffer.value,
                    "min",
                )
            )
    return tuple(found)


def check_gate_size(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The gate must be known, listed once, and large enough for the aircraft.

    `observed` is the aircraft's size class and `limit` the gate's maximum.
    """
    source = f"scenario.gates ({scenario.gates.provenance.value})"
    size = scenario.aircraft_size.value
    gates = scenario.gates.value
    missing: list[Violation] = []
    if size is None:
        missing.append(_missing(GATE_SIZE, "aircraft size", source))
    if gates is None:
        missing.append(_missing(GATE_SIZE, "gate map", source))
    if size is None or gates is None:
        return tuple(missing)

    listed = gates_with_id(gates, package.gate_id)
    if not listed:
        return (_missing(GATE_SIZE, f"gate {package.gate_id}", source),)
    if len(listed) > 1:
        return (
            _missing(
                GATE_SIZE,
                f"gate {package.gate_id} (listed more than once)",
                source,
                "ambiguous",
            ),
        )
    gate = listed[0]
    if size > gate.max_size:
        return (
            _violation(
                GATE_SIZE,
                f"{size.name} aircraft does not fit gate {gate.gate_id} "
                f"(max {gate.max_size.name})",
                source,
                int(size),
                int(gate.max_size),
                "size class",
            ),
        )
    return ()


def check_turnaround(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """Where the next leg is a hard constraint, the turnaround must fit.

    An unknown hardness is treated as hard. `observed` is the minutes between
    gate-in and the next departure and `limit` the minimum turnaround.
    """
    if scenario.next_leg_turnaround_hard.value is False:
        return ()
    depart_source = scenario.next_departure_min.provenance.value
    source = f"scenario.next_departure_min ({depart_source})"
    depart = scenario.next_departure_min.value
    start = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    missing: list[Violation] = []
    if depart is None:
        missing.append(_missing(TURNAROUND, "next departure", source))
    taxi = taxi_problem(scenario)
    if taxi is not None:
        missing.append(_missing(TURNAROUND, "taxi-in time", source, taxi))
    if stay is None:
        missing.append(_missing(TURNAROUND, "aircraft size", source))
    if depart is None or start is None or stay is None:
        return tuple(missing)

    available = depart - start
    if available < stay.value:
        return (
            _violation(
                TURNAROUND,
                f"{available} min between gate-in and next departure; "
                f"minimum turnaround is {stay.value} min",
                rv.reference(stay),
                available,
                stay.value,
                "min",
            ),
        )
    return ()


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id=GATE_OVERLAP,
        domain=Domain.GROUND,
        source="rule_values.gate_buffer_min",
        description="Gate occupancy must not overlap another flight, with buffer",
        public_reason=PublicReason.RESOURCE_CONFLICT,
        check=check_gate_overlap,
    ),
    Rule(
        rule_id=GATE_SIZE,
        domain=Domain.GROUND,
        source="scenario.gates",
        description="The aircraft must fit the gate",
        public_reason=PublicReason.EQUIPMENT_MISMATCH,
        check=check_gate_size,
    ),
    Rule(
        rule_id=TURNAROUND,
        domain=Domain.GROUND,
        source="rule_values.turnaround_min",
        description="Minimum turnaround before a hard next leg",
        public_reason=PublicReason.SCHEDULE_LIMIT,
        check=check_turnaround,
    ),
)
