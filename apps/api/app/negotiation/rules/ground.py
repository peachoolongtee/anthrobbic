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


def _missing(rule_id: str, name: str, source: str) -> Violation:
    return Violation.missing_data(rule_id, Domain.GROUND, name, source)


def gate_in_min(scenario: Scenario, package: Package) -> int | None:
    """When the aircraft reaches the gate: landing slot plus taxi-in."""
    taxi = scenario.taxi_in_min.value
    return None if taxi is None else package.slot.time_min + taxi


def turnaround_min(scenario: Scenario) -> rv.RuleValue | None:
    """Minimum turnaround for this aircraft's size class."""
    size = scenario.aircraft_size.value
    return None if size is None else rv.turnaround(size)


def check_gate_overlap(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The aircraft's gate stay, plus buffer, must not touch another's.

    `observed` is the clear gap in minutes between the two stays (negative when
    they overlap) and `limit` is the buffer.
    """
    buffer = rv.rule_value(rv.GATE_BUFFER_MIN)
    source = rv.reference(buffer)
    start = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    occupancies = scenario.gate_occupancies.value
    missing: list[Violation] = []
    if start is None:
        missing.append(_missing(GATE_OVERLAP, "taxi-in time", source))
    if stay is None:
        missing.append(_missing(GATE_OVERLAP, "aircraft size", source))
    if occupancies is None:
        missing.append(_missing(GATE_OVERLAP, "gate occupancies", source))
    if start is None or stay is None or occupancies is None:
        return tuple(missing)

    end = start + stay.value
    found: list[Violation] = []
    for other in occupancies:
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
    """The gate must be known and large enough for the aircraft.

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

    gate = next((g for g in gates if g.gate_id == package.gate_id), None)
    if gate is None:
        return (_missing(GATE_SIZE, f"gate {package.gate_id}", source),)
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
    if start is None:
        missing.append(_missing(TURNAROUND, "taxi-in time", source))
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
