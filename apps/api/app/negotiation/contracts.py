"""Typed, immutable messages and results for the negotiation core.

No logic that decides legality lives here. Times are whole minutes from a
scenario-local reference instant and quantities are integers, so every result
is exact and serialises identically on every run.
"""

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import ClassVar, Literal, Self

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
    """A runway. Runways sharing a `parallel_group` are treated as one runway
    for wake separation and throughput (FAA JO 7110.65: parallel runways less
    than 2,500 ft apart count as a single runway).

    `parallel_group` has no default on purpose: an omitted value would silently
    mean "independent", which removes wake and throughput limits. Say `None`
    explicitly for a runway that is independent."""

    runway_id: str
    closed: bool
    parallel_group: str | None


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


_ACTION_RANK = {action: rank for rank, action in enumerate(FlightPlanAction)}


class Package(FrozenModel):
    """The decision terms: where and when to land, which gate, how to absorb delay.

    The authority labels are metadata only and change no behaviour. Next-leg
    handling is the airline's too, but is not a term of this package.
    """

    AUTHORITY: ClassVar[Mapping[str, tuple[str, ...]]] = {
        "airline_decides": ("gate_id",),
        "requires_request": ("slot", "action"),
    }

    slot: ArrivalSlot = Field(json_schema_extra={"authority": "requires_request"})
    gate_id: str = Field(json_schema_extra={"authority": "airline_decides"})
    action: FlightPlanAction = Field(
        json_schema_extra={"authority": "requires_request"}
    )

    @property
    def terms_hash(self) -> str:
        """SHA-256 of the decision terms only, as canonical JSON.

        Nothing but the slot, gate and action is hashed, so explanations,
        provenance and reasons cannot change it.
        """
        terms = {
            "runway_id": self.slot.runway_id,
            "time_min": self.slot.time_min,
            "gate_id": self.gate_id,
            "action": self.action.value,
        }
        canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def sort_key(self) -> tuple[int, str, str, int]:
        """Code tie-break order: earliest, then runway, gate, action."""
        return (
            self.slot.time_min,
            self.slot.runway_id,
            self.gate_id,
            _ACTION_RANK[self.action],
        )


class ViolationCause(StrEnum):
    CONSTRAINT = "constraint"  # a real limit was exceeded
    MISSING_DATA = "missing_data"  # an input was unknown, so the rule failed closed


class PublicReason(StrEnum):
    """Coarse reason classes that may be shown to other domains.

    They carry no private value; the detail stays on `Violation`.
    """

    INFEASIBLE_FOR_ANOTHER_DOMAIN = "infeasible_for_another_domain"
    SAFETY_MARGIN = "safety_margin"
    RESOURCE_CLOSED = "resource_closed"
    CAPACITY_LIMIT = "capacity_limit"
    RESOURCE_CONFLICT = "resource_conflict"
    EQUIPMENT_MISMATCH = "equipment_mismatch"
    SCHEDULE_LIMIT = "schedule_limit"


class Violation(FrozenModel):
    """One broken rule. `observed` against `limit` is in `unit`.

    For a missing-data violation `observed` is None.
    """

    rule_id: str
    domain: Domain
    message: str
    source: str
    observed: int | None
    limit: int | None
    unit: str
    cause: ViolationCause = ViolationCause.CONSTRAINT

    @classmethod
    def missing_data(
        cls,
        rule_id: str,
        domain: Domain,
        name: str,
        source: str,
        reason: str = "unknown",
    ) -> Self:
        """A fail-closed violation. `reason` is "unknown" for an absent value
        and "invalid" for one that cannot be real, such as a negative fuel
        quantity."""
        return cls(
            rule_id=rule_id,
            domain=domain,
            message=f"{name} {reason}, so the rule fails closed",
            source=source,
            observed=None,
            limit=None,
            unit="",
            cause=ViolationCause.MISSING_DATA,
        )


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
    arrival_delay: int = 0
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


class Response(FrozenModel):
    """A domain's answer: every package it would accept, best first.

    An empty `acceptable_package_ids` is a refusal. IDs are `terms_hash`.
    """

    turn: int = Field(ge=1)
    responder: Domain
    acceptable_package_ids: tuple[str, ...]
    ranking: tuple[str, ...]
    reason: str

    @model_validator(mode="after")
    def _ranking_covers_acceptable(self) -> Self:
        if len(set(self.acceptable_package_ids)) != len(self.acceptable_package_ids):
            raise ValueError("acceptable package IDs must be unique")
        if sorted(self.ranking) != sorted(self.acceptable_package_ids):
            raise ValueError("ranking must order exactly the acceptable packages")
        return self


def intersect_responses(
    responses: Sequence[Response], packages: Iterable[Package]
) -> tuple[Package, ...]:
    """Packages that all three domains accept, in code tie-break order.

    Fails closed: with a domain missing there is no intersection. Two responses
    from one domain is a protocol error. IDs that match no given package are
    dropped, since they cannot be enacted.
    """
    by_domain: dict[Domain, Response] = {}
    for response in responses:
        if response.responder in by_domain:
            raise ValueError(f"two responses from {response.responder.value}")
        by_domain[response.responder] = response
    if set(by_domain) != set(Domain):
        return ()
    common = set.intersection(
        *(set(r.acceptable_package_ids) for r in by_domain.values())
    )
    unique = {p.terms_hash: p for p in packages if p.terms_hash in common}
    return tuple(sorted(unique.values(), key=lambda p: p.sort_key))


class Consensus(FrozenModel):
    """All three domains accepted one package and every rule passed.

    This is a record of what the domains said, not proof. Constructing one
    checks only that each domain accepted once; it does not run the rules. The
    protocol must re-check the package with `check_package` before treating a
    `Consensus` as a deal.
    """

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


class NoDealReason(StrEnum):
    NOTHING_LEGAL = "NOTHING_LEGAL"  # a real constraint blocks every package
    SYSTEM_FAULT = "SYSTEM_FAULT"  # missing data or a failure blocks every package


class NoDeal(FrozenModel):
    """No package passed every rule. Escalate to the duty manager.

    `nearest_package` is the one failing the fewest rules, so a reader sees what
    would have to change. It is None only when no package was enumerated.
    """

    kind: Literal["NO_DEAL"] = "NO_DEAL"
    reason_type: NoDealReason
    binding_rule_ids: tuple[str, ...]
    eliminations: tuple[RuleElimination, ...]
    packages_considered: int
    nearest_package: Package | None
    nearest_violations: tuple[Violation, ...]
    reason: str
    # One representative violation, with observed value and limit, per binding
    # rule. The card shows these.
    binding_violations: tuple[Violation, ...] = ()


type Decision = Deal | NoDeal


@dataclass(frozen=True, slots=True)
class Rule:
    """A hard rule: a stable ID, its domain and source, and a pure check."""

    rule_id: str
    domain: Domain
    source: str
    description: str
    public_reason: PublicReason
    check: Callable[[Scenario, Package], tuple[Violation, ...]]
