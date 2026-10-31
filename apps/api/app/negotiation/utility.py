"""Soft costs per domain, in integer units.

Costs only rank packages that already pass every rule. They never decide
legality. All weights live in `DEFAULT_WEIGHTS`.

Domain split: the pilot bears fuel burn, ATC bears arrival delay and the
connections it puts at risk, and ground bears gate moves, overtime and
turnaround delay.

Turbulence is not costed. It reaches the decision only through the agents'
notes; no number here stands for it.
"""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    CostBreakdown,
    Deal,
    DomainCosts,
    FrozenModel,
    Package,
    Scenario,
)
from app.negotiation.rules.ground import gate_in_min, turnaround_min
from app.negotiation.rules.pilot import extra_burn_kg


class CostWeights(FrozenModel):
    fuel_per_kg: int
    per_passenger_at_risk: int
    per_gate_move: int
    overtime_per_min: int
    turnaround_delay_per_min: int
    # Charged to ATC for each minute the arrival lands after the earliest slot.
    # The default keeps older call sites that omit it working.
    arrival_delay_per_min: int = 10


# Demo assumptions, not calibrated against any airline's costs. Ten units a
# minute means five minutes of delay costs as much as one gate move.
DEFAULT_WEIGHTS = CostWeights(
    fuel_per_kg=2,
    per_passenger_at_risk=100,
    per_gate_move=50,
    overtime_per_min=20,
    turnaround_delay_per_min=30,
    arrival_delay_per_min=10,
)


def _connections_at_risk(
    scenario: Scenario, gate_in: int | None, unknown: list[str]
) -> int:
    connections = scenario.connections.value
    if connections is None:
        unknown.append("connections")
        return 0
    if gate_in is None:
        unknown.append("taxi_in_min")
        return 0
    min_connect = rv.rule_value(rv.MIN_CONNECTION_MIN).value
    return sum(
        c.passengers for c in connections if gate_in + min_connect > c.departure_min
    )


def _overtime_min(scenario: Scenario, gate_in: int | None, unknown: list[str]) -> int:
    shift_end = scenario.ground_shift_end_min.value
    stay = turnaround_min(scenario)
    if shift_end is None:
        unknown.append("ground_shift_end_min")
        return 0
    if gate_in is None or stay is None:
        unknown.append("taxi_in_min" if gate_in is None else "aircraft_size")
        return 0
    return max(0, gate_in + stay.value - shift_end)


def _turnaround_delay_min(
    scenario: Scenario, gate_in: int | None, unknown: list[str]
) -> int:
    depart = scenario.next_departure_min.value
    stay = turnaround_min(scenario)
    if depart is None:
        unknown.append("next_departure_min")
        return 0
    if gate_in is None or stay is None:
        unknown.append("taxi_in_min" if gate_in is None else "aircraft_size")
        return 0
    return max(0, gate_in + stay.value - depart)


def compute_cost(
    scenario: Scenario,
    package: Package,
    weights: CostWeights = DEFAULT_WEIGHTS,
) -> CostBreakdown:
    """Weighted soft cost of one package. Unknown inputs are listed, not hidden."""
    unknown: list[str] = []
    gate_in = gate_in_min(scenario, package)

    burn = extra_burn_kg(scenario, package)
    if burn is None:
        unknown.append("fuel inputs")
        burn = 0
    fuel_cost = burn * weights.fuel_per_kg

    passengers = _connections_at_risk(scenario, gate_in, unknown)
    connection_cost = passengers * weights.per_passenger_at_risk

    planned = scenario.planned_gate.value
    if planned is None:
        unknown.append("planned_gate")
    moved = planned is None or planned != package.gate_id
    move_cost = weights.per_gate_move if moved else 0

    overtime_cost = _overtime_min(scenario, gate_in, unknown) * weights.overtime_per_min
    delay_cost = (
        _turnaround_delay_min(scenario, gate_in, unknown)
        * weights.turnaround_delay_per_min
    )

    earliest = scenario.earliest_arrival_min.value
    if earliest is None:
        unknown.append("earliest_arrival_min")
    delay_min = 0 if earliest is None else max(0, package.slot.time_min - earliest)
    arrival_delay_cost = delay_min * weights.arrival_delay_per_min

    by_domain = DomainCosts(
        pilot=fuel_cost,
        atc=connection_cost + arrival_delay_cost,
        ground=move_cost + overtime_cost + delay_cost,
    )
    return CostBreakdown(
        fuel_burn=fuel_cost,
        connections_at_risk=connection_cost,
        gate_moves=move_cost,
        overtime=overtime_cost,
        turnaround_delay=delay_cost,
        arrival_delay=arrival_delay_cost,
        by_domain=by_domain,
        total=by_domain.pilot + by_domain.atc + by_domain.ground,
        unknown_inputs=tuple(sorted(set(unknown))),
    )


class WeightSensitivity(FrozenModel):
    """Whether different weights would change which package the fallback picks.

    A package is None when the fallback returns `NoDeal`, which no weights can
    change: weights only rank packages that already pass every rule.
    """

    default_package: Package | None
    alternate_package: Package | None
    changed: bool


def weight_sensitivity(
    scenario: Scenario,
    alternate: CostWeights,
    default: CostWeights = DEFAULT_WEIGHTS,
) -> WeightSensitivity:
    """Run the fallback under both weight sets and compare the chosen packages.

    Build `alternate` with `DEFAULT_WEIGHTS.model_copy(update={...})`.
    """
    # Imported here because the fallback itself depends on this module.
    from app.negotiation.fallback import decide

    def chosen(weights: CostWeights) -> Package | None:
        decision = decide(scenario, weights)
        return decision.package if isinstance(decision, Deal) else None

    before = chosen(default)
    after = chosen(alternate)
    return WeightSensitivity(
        default_package=before, alternate_package=after, changed=before != after
    )
