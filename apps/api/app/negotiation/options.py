"""Deterministic enumeration of candidate packages.

Order is stable: arrival time, then runway ID, then gate ID, then flight plan
action in declaration order. Closed runways and gates are enumerated on
purpose, so the rules, not the enumerator, explain why a package is out.
"""

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    ArrivalSlot,
    DecisionPoint,
    FlightPlanAction,
    Package,
    Scenario,
)
from app.negotiation.rules.pilot import ALLOWED_ACTIONS


class PackageBoundError(ValueError):
    """Raised when the full candidate set would exceed the package bound."""


def enumeration_gaps(scenario: Scenario) -> tuple[str, ...]:
    """Scenario fields that are unknown and so prevent enumeration."""
    fields = (
        ("earliest_arrival_min", scenario.earliest_arrival_min.value),
        ("latest_arrival_min", scenario.latest_arrival_min.value),
        ("runways", scenario.runways.value),
        ("gates", scenario.gates.value),
    )
    return tuple(name for name, value in fields if value is None)


def slot_times(scenario: Scenario) -> tuple[int, ...]:
    """Candidate arrival minutes, from the earliest on a fixed grid."""
    earliest = scenario.earliest_arrival_min.value
    latest = scenario.latest_arrival_min.value
    if earliest is None or latest is None:
        return ()
    step = rv.rule_value(rv.SLOT_STEP_MIN).value
    return tuple(range(earliest, latest + 1, step))


def _actions_for(
    delay_min: int, decision_point: DecisionPoint | None
) -> tuple[FlightPlanAction, ...]:
    """Only a zero delay can be flown as filed; any other delay must be absorbed
    in a way the decision point allows.

    With an unknown decision point every absorbing action is enumerated, so the
    fuel rule rejects them all by name instead of the enumerator hiding why.
    """
    if delay_min == 0:
        return (FlightPlanAction.DIRECT,)
    return tuple(
        action
        for action in FlightPlanAction
        if action is not FlightPlanAction.DIRECT
        and (decision_point is None or action in ALLOWED_ACTIONS[decision_point])
    )


def enumerate_packages(scenario: Scenario) -> tuple[Package, ...]:
    """Every coherent package, in stable order.

    Raises `PackageBoundError` rather than truncating: a silently dropped
    package could turn a legal deal into a false `NoDeal`.
    """
    earliest = scenario.earliest_arrival_min.value
    runways = scenario.runways.value
    gates = scenario.gates.value
    decision_point = scenario.decision_point.value
    if (
        enumeration_gaps(scenario)
        or earliest is None
        or runways is None
        or gates is None
    ):
        return ()

    runway_ids = sorted({r.runway_id for r in runways})
    gate_ids = sorted({g.gate_id for g in gates})
    times = slot_times(scenario)

    limit = rv.rule_value(rv.MAX_PACKAGES).value
    total = sum(len(_actions_for(t - earliest, decision_point)) for t in times)
    total *= len(runway_ids) * len(gate_ids)
    if total > limit:
        raise PackageBoundError(f"{total} packages exceeds the bound of {limit}")

    return tuple(
        Package(
            slot=ArrivalSlot(runway_id=runway_id, time_min=time_min),
            gate_id=gate_id,
            action=action,
        )
        for time_min in times
        for runway_id in runway_ids
        for gate_id in gate_ids
        for action in _actions_for(time_min - earliest, decision_point)
    )
