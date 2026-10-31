"""What a duty manager gets without the negotiation, for comparison.

Two baselines, both scored with the real rules so that neither ignores safety
silently:

- `first_come_first_served` has no coordination at all. It lands at the earliest
  time on the first runway at the nearest gate and checks nothing, so it breaks
  rules, and its low delay means little on the rows where it does.
- `human_heuristic` consults the rules for every step, which is generous: a
  person on the phone sees less. Its violation count is zero by construction and
  is no evidence that a human would be safe.

The scenario has no airport geometry, so "nearest gate" is a stated proxy: the
lowest gate ID for the first baseline, and gates on the planned gate's taxiway
first for the second.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.negotiation.contracts import (
    ArrivalSlot,
    FlightPlanAction,
    Gate,
    Package,
    Scenario,
)
from app.negotiation.harm import HarmReport, inspect_package
from app.negotiation.options import slot_times
from app.negotiation.rules import check_package
from app.negotiation.rules.pilot import project_fuel
from app.negotiation.utility import CostWeights, compute_cost

# With every weight at 1, each cost component reads in its natural unit: kg,
# passengers, moves, minutes.
NATURAL_UNITS = CostWeights(**dict.fromkeys(CostWeights.model_fields, 1))

# Ground delay first, then a hold, then a path stretch, as an operator would try.
_DELAY_ACTION_ORDER = (
    FlightPlanAction.GROUND_DELAY,
    FlightPlanAction.HOLD,
    FlightPlanAction.VECTOR,
)


class BaselineName(StrEnum):
    FIRST_COME_FIRST_SERVED = "first_come_first_served"
    HUMAN_HEURISTIC = "human_heuristic"


@dataclass(frozen=True, slots=True)
class PackageMetrics:
    """One package's outcome in natural units. None means an input was unknown."""

    delay_min: int | None
    fuel_margin_kg: int | None
    connection_passengers_at_risk: int
    overtime_min: int
    turnaround_delay_min: int
    gate_moves: int
    fuel_burn_kg: int


@dataclass(frozen=True, slots=True)
class BaselineOutcome:
    """What a baseline did. `package` is None when it found nothing to do."""

    name: BaselineName
    package: Package | None
    violated_rule_ids: tuple[str, ...]
    harm: HarmReport | None
    metrics: PackageMetrics | None

    @property
    def broke_a_rule(self) -> bool:
        return bool(self.violated_rule_ids)


def package_metrics(scenario: Scenario, package: Package) -> PackageMetrics:
    natural = compute_cost(scenario, package, NATURAL_UNITS)
    projection = project_fuel(scenario, package)
    earliest = scenario.earliest_arrival_min.value
    return PackageMetrics(
        delay_min=None if earliest is None else package.slot.time_min - earliest,
        fuel_margin_kg=(
            None
            if projection is None
            else projection.landing_fuel_kg - projection.required_kg
        ),
        connection_passengers_at_risk=natural.connections_at_risk,
        overtime_min=natural.overtime,
        turnaround_delay_min=natural.turnaround_delay,
        gate_moves=natural.gate_moves,
        fuel_burn_kg=natural.fuel_burn,
    )


def first_come_first_served(scenario: Scenario) -> Package | None:
    """Earliest time, first runway, lowest gate ID, flown as filed. Checks nothing.

    None only when the scenario lacks a time, a runway or a gate to name.
    """
    earliest = scenario.earliest_arrival_min.value
    runways = scenario.runways.value
    gates = scenario.gates.value
    if earliest is None or not runways or not gates:
        return None
    return Package(
        slot=ArrivalSlot(
            runway_id=min(r.runway_id for r in runways), time_min=earliest
        ),
        gate_id=min(g.gate_id for g in gates),
        action=FlightPlanAction.DIRECT,
    )


def _gates_by_closeness(scenario: Scenario, gates: tuple[Gate, ...]) -> list[str]:
    """Planned gate first, then its taxiway's other gates, then the rest."""
    planned = scenario.planned_gate.value
    planned_taxiways = {g.taxiway_id for g in gates if g.gate_id == planned}

    def closeness(gate: Gate) -> tuple[int, str]:
        if gate.gate_id == planned:
            return (0, gate.gate_id)
        return (1 if gate.taxiway_id in planned_taxiways else 2, gate.gate_id)

    ordered = sorted(gates, key=closeness)
    return list(dict.fromkeys(g.gate_id for g in ordered))


def human_heuristic(scenario: Scenario) -> Package | None:
    """The earliest legal slot, keeping the planned gate if it is legal then,
    else the closest gate that is. None means the human escalates.

    Gates are chosen slot by slot, so this will move gate rather than wait for
    the planned one. It does not weigh connections, overtime or next-leg cost.
    """
    earliest = scenario.earliest_arrival_min.value
    runways = scenario.runways.value
    gates = scenario.gates.value
    if earliest is None or not runways or not gates:
        return None
    gate_ids = _gates_by_closeness(scenario, gates)
    runway_ids = sorted({r.runway_id for r in runways})
    for time_min in slot_times(scenario):
        actions = (
            (FlightPlanAction.DIRECT,) if time_min == earliest else _DELAY_ACTION_ORDER
        )
        for gate_id in gate_ids:
            for runway_id in runway_ids:
                for action in actions:
                    package = Package(
                        slot=ArrivalSlot(runway_id=runway_id, time_min=time_min),
                        gate_id=gate_id,
                        action=action,
                    )
                    if not check_package(scenario, package):
                        return package
    return None


def _outcome(
    name: BaselineName, scenario: Scenario, package: Package | None
) -> BaselineOutcome:
    if package is None:
        return BaselineOutcome(
            name=name, package=None, violated_rule_ids=(), harm=None, metrics=None
        )
    violations = check_package(scenario, package)
    return BaselineOutcome(
        name=name,
        package=package,
        violated_rule_ids=tuple(sorted({v.rule_id for v in violations})),
        harm=inspect_package(scenario, package),
        metrics=package_metrics(scenario, package),
    )


def run_baselines(scenario: Scenario) -> tuple[BaselineOutcome, BaselineOutcome]:
    """Both baselines, each scored against the rules and the harm check."""
    return (
        _outcome(
            BaselineName.FIRST_COME_FIRST_SERVED,
            scenario,
            first_come_first_served(scenario),
        ),
        _outcome(BaselineName.HUMAN_HEURISTIC, scenario, human_heuristic(scenario)),
    )
