"""Typed, immutable messages and results for the negotiation core.

No logic that decides legality lives here. Times are whole minutes from a
scenario-local reference instant and quantities are integers, so every result
is exact and serialises identically on every run.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Provenance(StrEnum):
    REAL = "real"
    DERIVED = "derived"
    SYNTHETIC = "synthetic"


class Domain(StrEnum):
    ATC = "atc"
    PILOT = "pilot"
    GROUND = "ground"


class WakeCategory(StrEnum):
    SUPER = "super"
    HEAVY = "heavy"
    LARGE = "large"
    SMALL = "small"


class AircraftSize(IntEnum):
    """Gate size class. A larger value needs a larger gate."""

    REGIONAL = 1
    NARROW_BODY = 2
    WIDE_BODY = 3


class FlightPlanAction(StrEnum):
    """How the delay between earliest and assigned arrival is absorbed.

    Declaration order is the tie-break order.
    """

    DIRECT = "direct"  # proceed as filed; only coherent with zero delay
    HOLD = "hold"  # hold at a fix; burns at the aircraft's hold rate
    VECTOR = "vector"  # path stretch; burns at the aircraft's cruise rate
    GROUND_DELAY = "ground_delay"  # wait before departure; burns no airborne fuel


class DecisionPoint(StrEnum):
    """Where the aircraft is when the disruption is handled."""

    PRE_DEPARTURE = "pre_departure"  # an airborne hold is not possible
    AIRBORNE = "airborne"  # a ground delay is not possible


class FlightRules(StrEnum):
    IFR = "ifr"
    VFR = "vfr"


class Sourced[T](FrozenModel):
    """A scenario value with its provenance. `value=None` means unknown."""

    value: T | None
    provenance: Provenance


class Runway(FrozenModel):
    runway_id: str
    closed: bool


class Taxiway(FrozenModel):
    taxiway_id: str
    closed: bool


class Gate(FrozenModel):
    gate_id: str
    taxiway_id: str
    max_size: AircraftSize


class OtherArrival(FrozenModel):
    flight_id: str
    wake_category: WakeCategory
    runway_id: str
    time_min: int


class GateOccupancy(FrozenModel):
    gate_id: str
    flight_id: str
    start_min: int
    end_min: int

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_min <= self.start_min:
            raise ValueError("occupancy must end after it starts")
        return self


class WeatherPeriod(FrozenModel):
    """Forecast conditions at the destination over a closed time interval."""

    start_min: int
    end_min: int
    ceiling_ft: int
    visibility_tenth_mi: int  # tenths of a statute mile

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_min < self.start_min:
            raise ValueError("weather period must not end before it starts")
        return self


class Connection(FrozenModel):
    """Passengers who connect onto a later departure."""

    passengers: int = Field(ge=0)
    departure_min: int


class Scenario(FrozenModel):
    """One disrupted arrival and everything the rules need to judge packages.

    Every field is `Sourced`, so it names its provenance. A `None` value is
    unknown and makes any rule that needs it fail closed.
    """

    scenario_id: Sourced[str]
    flight_id: Sourced[str]
    decision_point: Sourced[DecisionPoint]
    flight_rules: Sourced[FlightRules]
    wake_category: Sourced[WakeCategory]
    aircraft_size: Sourced[AircraftSize]
    # Planning window for the arrival slot, in minutes.
    earliest_arrival_min: Sourced[int]
    latest_arrival_min: Sourced[int]
    taxi_in_min: Sourced[int]
    # Fuel, in kg and kg per minute.
    fuel_on_board_kg: Sourced[int]
    trip_fuel_kg: Sourced[int]  # fuel to land at the earliest arrival
    cruise_burn_kg_per_min: Sourced[int]
    hold_burn_kg_per_min: Sourced[int]
    # Fuel to reach the alternate, counted only when an alternate is required.
    alternate_fuel_kg: Sourced[int]
    # Destination forecast; missing or incomplete coverage means an alternate
    # is required.
    destination_forecast: Sourced[tuple[WeatherPeriod, ...]]
    # Airport state.
    runways: Sourced[tuple[Runway, ...]]
    taxiways: Sourced[tuple[Taxiway, ...]]
    gates: Sourced[tuple[Gate, ...]]
    other_arrivals: Sourced[tuple[OtherArrival, ...]]
    gate_occupancies: Sourced[tuple[GateOccupancy, ...]]
    # Ground and downstream.
    planned_gate: Sourced[str]
    next_departure_min: Sourced[int]
    next_leg_turnaround_hard: Sourced[bool]
    ground_shift_end_min: Sourced[int]
    connections: Sourced[tuple[Connection, ...]]


class ArrivalSlot(FrozenModel):
    runway_id: str
    time_min: int


class Package(FrozenModel):
    slot: ArrivalSlot
    gate_id: str
    action: FlightPlanAction


class Violation(FrozenModel):
    rule_id: str
    domain: Domain
    message: str
    source: str


class DomainCosts(FrozenModel):
    """Soft costs in weighted integer units. Never consulted for legality."""

    pilot: int
    atc: int
    ground: int


class CostBreakdown(FrozenModel):
    fuel_burn: int
    connections_at_risk: int
    gate_moves: int
    overtime: int
    turnaround_delay: int
    by_domain: DomainCosts
    total: int
    # Soft inputs that were unknown and so contributed nothing (or, for the
    # planned gate, the worst case).
    unknown_inputs: tuple[str, ...]


class Proposal(FrozenModel):
    turn: int = Field(ge=1)
    author: Domain
    package: Package
    reason: str


class ResponseKind(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    COUNTER = "counter"


class Response(FrozenModel):
    turn: int = Field(ge=1)
    responder: Domain
    kind: ResponseKind
    package: Package  # the package responded to
    counter: Package | None = None
    reason: str

    @model_validator(mode="after")
    def _counter_matches_kind(self) -> Self:
        if (self.kind is ResponseKind.COUNTER) != (self.counter is not None):
            raise ValueError("a counter package is required exactly for COUNTER")
        return self


class Consensus(FrozenModel):
    """All three domains accepted one package and every rule passed."""

    turn: int = Field(ge=1)
    package: Package
    accepted_by: tuple[Domain, ...]
    rules_checked: tuple[str, ...]

    @model_validator(mode="after")
    def _all_domains_accepted(self) -> Self:
        accepted = sorted(self.accepted_by)
        if accepted != sorted(Domain):
            raise ValueError("every domain must accept exactly once")
        return self


class Deal(FrozenModel):
    kind: Literal["DEAL"] = "DEAL"
    package: Package
    cost: CostBreakdown
    packages_considered: int
    packages_legal: int


class RuleElimination(FrozenModel):
    rule_id: str
    packages_eliminated: int


class NoDeal(FrozenModel):
    """No package passed every rule. Escalate to the duty manager."""

    kind: Literal["NO_DEAL"] = "NO_DEAL"
    binding_rule_ids: tuple[str, ...]
    eliminations: tuple[RuleElimination, ...]
    packages_considered: int
    reason: str


type Decision = Deal | NoDeal


@dataclass(frozen=True, slots=True)
class Rule:
    """A hard rule: a stable ID, its domain and source, and a pure check."""

    rule_id: str
    domain: Domain
    source: str
    description: str
    check: Callable[[Scenario, Package], tuple[Violation, ...]]
