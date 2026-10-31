"""Ground rules. Each is pure and returns every violation."""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import Domain, Package, Rule, Scenario, Violation

GATE_OVERLAP = "GND-GATE-OVERLAP"
GATE_SIZE = "GND-GATE-SIZE"
TURNAROUND = "GND-TURNAROUND"


def _violation(rule_id: str, message: str, source: str) -> Violation:
    return Violation(
        rule_id=rule_id, domain=Domain.GROUND, message=message, source=source
    )


def gate_in_min(scenario: Scenario, package: Package) -> int | None:
    """When the aircraft reaches the gate: landing slot plus taxi-in."""
    taxi = scenario.taxi_in_min.value
    return None if taxi is None else package.slot.time_min + taxi


def turnaround_min(scenario: Scenario) -> rv.RuleValue | None:
    """Minimum turnaround for this aircraft's size class."""
    size = scenario.aircraft_size.value
    return None if size is None else rv.turnaround(size)


def check_gate_overlap(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The aircraft's gate stay, plus buffer, must not touch another's."""
    buffer = rv.rule_value(rv.GATE_BUFFER_MIN)
    source = rv.reference(buffer)
    start = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    occupancies = scenario.gate_occupancies.value
    missing: list[Violation] = []
    if start is None:
        missing.append(_violation(GATE_OVERLAP, "taxi-in time unknown", source))
    if stay is None:
        missing.append(_violation(GATE_OVERLAP, "aircraft size unknown", source))
    if occupancies is None:
        missing.append(_violation(GATE_OVERLAP, "gate occupancies unknown", source))
    if start is None or stay is None or occupancies is None:
        return tuple(missing)

    end = start + stay.value
    found: list[Violation] = []
    for other in occupancies:
        if other.gate_id != package.gate_id:
            continue
        if (
            start < other.end_min + buffer.value
            and other.start_min < end + buffer.value
        ):
            found.append(
                _violation(
                    GATE_OVERLAP,
                    f"gate {package.gate_id} stay {start}-{end} is within "
                    f"{buffer.value} min of {other.flight_id} at "
                    f"{other.start_min}-{other.end_min}",
                    source,
                )
            )
    return tuple(found)


def check_gate_size(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The gate must be known and large enough for the aircraft."""
    source = f"scenario.gates ({scenario.gates.provenance.value})"
    size = scenario.aircraft_size.value
    gates = scenario.gates.value
    missing: list[Violation] = []
    if size is None:
        missing.append(_violation(GATE_SIZE, "aircraft size unknown", source))
    if gates is None:
        missing.append(_violation(GATE_SIZE, "gate map unknown", source))
    if size is None or gates is None:
        return tuple(missing)

    gate = next((g for g in gates if g.gate_id == package.gate_id), None)
    if gate is None:
        return (
            _violation(
                GATE_SIZE, f"gate {package.gate_id} is not in the scenario", source
            ),
        )
    if size > gate.max_size:
        return (
            _violation(
                GATE_SIZE,
                f"{size.name} aircraft does not fit gate {gate.gate_id} "
                f"(max {gate.max_size.name})",
                source,
            ),
        )
    return ()


def check_turnaround(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """Where the next leg is a hard constraint, the turnaround must fit.

    An unknown hardness is treated as hard.
    """
    if scenario.next_leg_turnaround_hard.value is False:
        return ()
    source = (
        f"scenario.next_departure_min ({scenario.next_departure_min.provenance.value})"
    )
    depart = scenario.next_departure_min.value
    start = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    missing: list[Violation] = []
    if depart is None:
        missing.append(_violation(TURNAROUND, "next departure unknown", source))
    if start is None:
        missing.append(_violation(TURNAROUND, "taxi-in time unknown", source))
    if stay is None:
        missing.append(_violation(TURNAROUND, "aircraft size unknown", source))
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
            ),
        )
    return ()


RULES: tuple[Rule, ...] = (
    Rule(
        GATE_OVERLAP,
        Domain.GROUND,
        "rule_values.gate_buffer_min",
        "Gate occupancy must not overlap another flight, allowing the buffer",
        check_gate_overlap,
    ),
    Rule(
        GATE_SIZE,
        Domain.GROUND,
        "scenario.gates",
        "The aircraft must fit the gate",
        check_gate_size,
    ),
    Rule(
        TURNAROUND,
        Domain.GROUND,
        "rule_values.turnaround_min",
        "Minimum turnaround before a hard next leg",
        check_turnaround,
    ),
)
