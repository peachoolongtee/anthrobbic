"""The pilot agent. It sees fuel and forecast, never traffic or gate occupancy."""

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
from app.negotiation.rules.pilot import project_fuel
from app.negotiation.utility import compute_cost


class PilotReason(StrEnum):
    NO_OBJECTION = "no_objection"
    LOW_FUEL_BURN = "low_fuel_burn"
    THIN_FUEL_MARGIN = "thin_fuel_margin"
    CREW_FATIGUE = "crew_fatigue"
    CREW_NOTE = "crew_note"
    ACTION_UNSUITABLE = "action_unsuitable"


class PilotReply(AgentReply[PilotReason]):
    pass


# Fuel and crew state are private, so declines surface only as coarse classes.
_PUBLIC_REASONS: Mapping[str, PublicReason] = MappingProxyType(
    {
        PilotReason.NO_OBJECTION.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        PilotReason.LOW_FUEL_BURN.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        PilotReason.THIN_FUEL_MARGIN.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        PilotReason.CREW_FATIGUE.value: PublicReason.SCHEDULE_LIMIT,
        PilotReason.CREW_NOTE.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        PilotReason.ACTION_UNSUITABLE.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
    }
)

_ROLE_PROMPT = """\
You are the agent speaking for the pilot in command of one disrupted arrival. You \
care about fuel margin at landing, avoiding needless airborne delay, and what the \
crew has told you. The pilot in command keeps their own fuel and safety authority, \
and nothing you answer takes it away.

Your brief holds fuel state and the destination forecast. Your notes are crew \
remarks. Each offered package carries your_figures, computed by code: the delay, \
extra burn, projected landing fuel, margin above the required reserve, whether an \
alternate is required, and your soft cost. Do not recompute them. Prefer healthy \
margins and little extra burn, and let a clear crew note move your ranking or your \
acceptable set."""


def _facts(scenario: Scenario, package: Package) -> Mapping[str, JsonValue]:
    projection = project_fuel(scenario, package)
    soft_cost = compute_cost(scenario, package).by_domain.pilot
    if projection is None:
        return {"soft_cost": soft_cost}
    return {
        "delay_min": projection.delay_min,
        "extra_burn_kg": projection.extra_burn_kg,
        "landing_fuel_kg": projection.landing_fuel_kg,
        "fuel_margin_kg": projection.landing_fuel_kg - projection.required_kg,
        "alternate_required": projection.alternate_required,
        "soft_cost": soft_cost,
    }


PILOT_SPEC = AgentSpec(
    domain=Domain.PILOT,
    system_prompt=compose_system_prompt(_ROLE_PROMPT),
    view_fields=(
        *COMMON_VIEW_FIELDS,
        "flight_rules",
        "fuel_on_board_kg",
        "trip_fuel_kg",
        "cruise_burn_kg_per_min",
        "hold_burn_kg_per_min",
        "alternate_fuel_kg",
        "destination_forecast",
    ),
    reply_model=PilotReply,
    public_reasons=_PUBLIC_REASONS,
    package_facts=_facts,
)
