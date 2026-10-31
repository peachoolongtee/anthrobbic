"""The air traffic flow agent. It sees traffic and airfield state, never fuel."""

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
from app.negotiation.rules.pilot import delay_min
from app.negotiation.utility import compute_cost


class AtcReason(StrEnum):
    NO_OBJECTION = "no_objection"
    LOW_OWN_COST = "low_own_cost"
    SEQUENCE_PRESSURE = "sequence_pressure"
    WEATHER_NOTE = "weather_note"
    RUNWAY_UNSUITABLE = "runway_unsuitable"
    CONNECTION_RISK = "connection_risk"


class AtcReply(AgentReply[AtcReason]):
    pass


_PUBLIC_REASONS: Mapping[str, PublicReason] = MappingProxyType(
    {
        AtcReason.NO_OBJECTION.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        AtcReason.LOW_OWN_COST.value: PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        AtcReason.SEQUENCE_PRESSURE.value: PublicReason.CAPACITY_LIMIT,
        AtcReason.WEATHER_NOTE.value: PublicReason.SAFETY_MARGIN,
        AtcReason.RUNWAY_UNSUITABLE.value: PublicReason.SAFETY_MARGIN,
        AtcReason.CONNECTION_RISK.value: PublicReason.SCHEDULE_LIMIT,
    }
)

_ROLE_PROMPT = """\
You are the air traffic flow agent for one disrupted arrival. You care about an \
orderly arrival sequence, runway use in the conditions reported to you, and how \
much delay this flight's connecting passengers carry. You can only request a slot \
or routing; you do not command the airline or the pilot in command.

Your brief holds the traffic and airfield picture and the connection list. Your \
notes are weather and flow remarks. Each offered package carries your_figures, \
computed by code: delay against the earliest arrival, the smallest gap to other \
traffic on that runway, and your soft cost. Favour a calm sequence and low delay, \
and apply your weather notes as described below."""


def _facts(scenario: Scenario, package: Package) -> Mapping[str, JsonValue]:
    arrivals = scenario.other_arrivals.value or ()
    gaps = [
        abs(package.slot.time_min - other.time_min)
        for other in arrivals
        if other.runway_id == package.slot.runway_id
    ]
    return {
        "delay_min": delay_min(scenario, package),
        "smallest_traffic_gap_min": min(gaps) if gaps else None,
        "soft_cost": compute_cost(scenario, package).by_domain.atc,
    }


ATC_SPEC = AgentSpec(
    domain=Domain.ATC,
    system_prompt=compose_system_prompt(_ROLE_PROMPT),
    view_fields=(
        *COMMON_VIEW_FIELDS,
        "flight_rules",
        "wake_category",
        "runways",
        "taxiways",
        "other_arrivals",
        "connections",
        "airport_ops_per_hour",
    ),
    reply_model=AtcReply,
    public_reasons=_PUBLIC_REASONS,
    package_facts=_facts,
)
