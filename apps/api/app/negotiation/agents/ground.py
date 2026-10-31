"""The ground agent. It sees gates and the next leg, never fuel or traffic."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import JsonValue

from app.negotiation.agents.base import (
    COMMON_VIEW_FIELDS,
    AgentReply,
    AgentSpec,
    compose_system_prompt,
)
from app.negotiation.contracts import Domain, Package, PublicReason, Scenario
from app.negotiation.rules.ground import gate_in_min, turnaround_min
from app.negotiation.utility import compute_cost


class GroundReason(StrEnum):
    NO_OBJECTION = "no_objection"
    KEEPS_PLANNED_GATE = "keeps_planned_gate"
    GATE_MOVE = "gate_move"
    OVERTIME = "overtime"
    TIGHT_TURNAROUND = "tight_turnaround"
    RAMP_NOTE = "ramp_note"


class GroundReply(AgentReply[GroundReason]):
    pass


_PUBLIC_REASONS: Mapping[str, PublicReason] = MappingProxyType(
    {
        GroundReason.NO_OBJECTION.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        GroundReason.KEEPS_PLANNED_GATE.value: PublicReason.RESOURCE_CONFLICT,
        GroundReason.GATE_MOVE.value: PublicReason.RESOURCE_CONFLICT,
        GroundReason.OVERTIME.value: PublicReason.SCHEDULE_LIMIT,
        GroundReason.TIGHT_TURNAROUND.value: PublicReason.SCHEDULE_LIMIT,
        GroundReason.RAMP_NOTE.value: PublicReason.RESOURCE_CONFLICT,
    }
)

_ROLE_PROMPT = """\
You are the ramp and gate agent for one disrupted arrival. You care about keeping \
the planned gate where you can, finishing within the ground shift, and turning the \
aircraft round in time for its next departure. The gate is the airline's own \
decision, so your view carries real weight there.

Your brief holds the gate map, occupancy, the planned gate and the next leg. Your \
notes are ramp remarks. Each offered package carries your_figures, computed by \
code: gate-in time, whether the planned gate is kept, spare turnaround minutes, \
overtime minutes, and your soft cost. Prefer fewer gate moves and spare turnaround \
time, and apply your ramp notes as described below."""


def _facts(scenario: Scenario, package: Package) -> Mapping[str, JsonValue]:
    gate_in = gate_in_min(scenario, package)
    stay = turnaround_min(scenario)
    depart = scenario.next_departure_min.value
    shift_end = scenario.ground_shift_end_min.value
    ready = None if gate_in is None or stay is None else gate_in + stay.value
    return {
        "gate_in_min": gate_in,
        "keeps_planned_gate": package.gate_id == scenario.planned_gate.value,
        "spare_turnaround_min": (
            None if ready is None or depart is None else depart - ready
        ),
        "overtime_min": (
            None if ready is None or shift_end is None else max(0, ready - shift_end)
        ),
        "soft_cost": compute_cost(scenario, package).by_domain.ground,
    }


GROUND_SPEC = AgentSpec(
    domain=Domain.GROUND,
    system_prompt=compose_system_prompt(_ROLE_PROMPT),
    view_fields=(
        *COMMON_VIEW_FIELDS,
        "taxi_in_min",
        "aircraft_size",
        "gates",
        "gate_occupancies",
        "planned_gate",
        "next_departure_min",
        "next_leg_turnaround_hard",
        "ground_shift_end_min",
        "decision_time_min",
        "min_turnaround_min",
    ),
    reply_model=GroundReply,
    public_reasons=_PUBLIC_REASONS,
    package_facts=_facts,
)
