"""The three independent agents. Each is one model call with its own prompt."""

from app.negotiation.agents.atc import ATC_SPEC
from app.negotiation.agents.base import AgentSpec
from app.negotiation.agents.ground import GROUND_SPEC
from app.negotiation.agents.pilot import PILOT_SPEC
from app.negotiation.contracts import Domain

AGENT_SPECS: dict[Domain, AgentSpec] = {
    Domain.ATC: ATC_SPEC,
    Domain.PILOT: PILOT_SPEC,
    Domain.GROUND: GROUND_SPEC,
}
