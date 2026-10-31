"""Pilot rules. Each is pure and returns every violation.

The fuel reserve is our demo policy, shaped on 14 CFR 121.639 and FAA InFO
08004. 121.639 is a dispatch and takeoff test and does not bind in flight, so
this rule is a policy limit and says so in its ID and messages.
"""

from dataclasses import dataclass
from types import MappingProxyType

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    DecisionPoint,
    Domain,
    FlightPlanAction,
    Package,
    PublicReason,
    Rule,
    Scenario,
    Violation,
    WeatherPeriod,
)

FUEL_POLICY = "PLT-FUEL-POLICY"

# Delay can only be absorbed where the aircraft is: on the ground before
# departure, or in the air after it. DIRECT (no delay) is always possible.
ALLOWED_ACTIONS: MappingProxyType[DecisionPoint, tuple[FlightPlanAction, ...]] = (
    MappingProxyType(
        {
            DecisionPoint.PRE_DEPARTURE: (
                FlightPlanAction.DIRECT,
                FlightPlanAction.GROUND_DELAY,
            ),
            DecisionPoint.AIRBORNE: (
                FlightPlanAction.DIRECT,
                FlightPlanAction.HOLD,
                FlightPlanAction.VECTOR,
            ),
        }
    )
)


def _violation(
    message: str, source: str, observed: int, limit: int, unit: str
) -> Violation:
    return Violation(
        rule_id=FUEL_POLICY,
        domain=Domain.PILOT,
        message=message,
        source=source,
        observed=observed,
        limit=limit,
        unit=unit,
    )


@dataclass(frozen=True, slots=True)
class FuelProjection:
    delay_min: int
    extra_burn_kg: int
    landing_fuel_kg: int
    required_kg: int
    alternate_required: bool


def delay_min(scenario: Scenario, package: Package) -> int | None:
    """Minutes between the earliest arrival and the assigned slot."""
    earliest = scenario.earliest_arrival_min.value
    if earliest is None:
        return None
    return package.slot.time_min - earliest


def extra_burn_kg(scenario: Scenario, package: Package) -> int | None:
    """Fuel burned absorbing the delay, or None if an input is unknown.

    A ground delay burns no airborne fuel (taxi and APU burn are ignored).
    """
    delay = delay_min(scenario, package)
    if delay is None:
        return None
    match package.action:
        case FlightPlanAction.DIRECT | FlightPlanAction.GROUND_DELAY:
            return 0
        case FlightPlanAction.HOLD:
            rate = scenario.hold_burn_kg_per_min.value
        case FlightPlanAction.VECTOR:
            rate = scenario.cruise_burn_kg_per_min.value
    return None if rate is None else delay * rate


def _poor(period: WeatherPeriod) -> bool:
    ceiling = rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value
    visibility = rv.rule_value(rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI).value
    return period.ceiling_ft < ceiling or period.visibility_tenth_mi < visibility


def alternate_required(scenario: Scenario, package: Package) -> bool:
    """14 CFR 121.619(a): no alternate if the forecast stays at or above the
    minimums from an hour before to an hour after the ETA.

    Missing forecast, or a forecast that does not cover the whole window,
    means an alternate is required.
    """
    forecast = scenario.destination_forecast.value
    if forecast is None:
        return True
    margin = rv.rule_value(rv.ALTERNATE_WINDOW_MIN).value
    window_start = package.slot.time_min - margin
    window_end = package.slot.time_min + margin
    relevant = sorted(
        (
            p
            for p in forecast
            if p.end_min >= window_start and p.start_min <= window_end
        ),
        key=lambda p: (p.start_min, p.end_min),
    )
    covered_to = window_start
    for period in relevant:
        if period.start_min > covered_to:
            return True  # gap in coverage
        covered_to = max(covered_to, period.end_min)
    if covered_to < window_end:
        return True
    return any(_poor(p) for p in relevant)


def project_fuel(scenario: Scenario, package: Package) -> FuelProjection | None:
    """Landing fuel against the policy reserve, or None if an input is unknown."""
    delay = delay_min(scenario, package)
    burn = extra_burn_kg(scenario, package)
    on_board = scenario.fuel_on_board_kg.value
    trip = scenario.trip_fuel_kg.value
    cruise = scenario.cruise_burn_kg_per_min.value
    needs_alternate = alternate_required(scenario, package)
    alternate = scenario.alternate_fuel_kg.value if needs_alternate else 0
    if (
        delay is None
        or burn is None
        or on_board is None
        or trip is None
        or cruise is None
        or alternate is None
    ):
        return None
    reserve_min = rv.rule_value(rv.FUEL_RESERVE_MIN).value
    return FuelProjection(
        delay_min=delay,
        extra_burn_kg=burn,
        landing_fuel_kg=on_board - trip - burn,
        required_kg=reserve_min * cruise + alternate,
        alternate_required=needs_alternate,
    )


def check_fuel_policy(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """Fuel at landing, after any hold and any required alternate, must meet
    the policy reserve."""
    reserve = rv.rule_value(rv.FUEL_RESERVE_MIN)
    source = rv.reference(reserve)

    needed: dict[str, object] = {
        "decision_point": scenario.decision_point.value,
        "earliest_arrival_min": scenario.earliest_arrival_min.value,
        "fuel_on_board_kg": scenario.fuel_on_board_kg.value,
        "trip_fuel_kg": scenario.trip_fuel_kg.value,
        "cruise_burn_kg_per_min": scenario.cruise_burn_kg_per_min.value,
    }
    if alternate_required(scenario, package):
        needed["alternate_fuel_kg"] = scenario.alternate_fuel_kg.value
    if package.action is FlightPlanAction.HOLD:
        needed["hold_burn_kg_per_min"] = scenario.hold_burn_kg_per_min.value
    missing = [
        Violation.missing_data(FUEL_POLICY, Domain.PILOT, name, source)
        for name, value in needed.items()
        if value is None
    ]
    decision_point = scenario.decision_point.value
    if missing or decision_point is None:
        return tuple(missing)

    projection = project_fuel(scenario, package)
    if projection is None:  # unreachable while `needed` covers every input
        return (
            Violation.missing_data(
                FUEL_POLICY, Domain.PILOT, "fuel projection input", source
            ),
        )

    found: list[Violation] = []
    if package.action not in ALLOWED_ACTIONS[decision_point]:
        found.append(
            _violation(
                f"{package.action.value} is not possible {decision_point.value}",
                source,
                1,
                0,
                "impossible actions",
            )
        )
    if projection.delay_min < 0:
        found.append(
            _violation(
                f"slot is {-projection.delay_min} min before the earliest arrival",
                source,
                projection.delay_min,
                0,
                "min of delay",
            )
        )
    if package.action is FlightPlanAction.DIRECT and projection.delay_min != 0:
        found.append(
            _violation(
                f"direct cannot absorb a {projection.delay_min} min delay",
                source,
                projection.delay_min,
                0,
                "min of delay",
            )
        )
    if projection.landing_fuel_kg < projection.required_kg:
        alternate_note = (
            "plus alternate" if projection.alternate_required else "no alternate"
        )
        found.append(
            _violation(
                f"landing fuel {projection.landing_fuel_kg} kg is below the "
                f"policy limit of {projection.required_kg} kg "
                f"({reserve.value} min reserve, {alternate_note}); a demo policy "
                "limit, not a regulation",
                source,
                projection.landing_fuel_kg,
                projection.required_kg,
                "kg",
            )
        )
    return tuple(found)


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id=FUEL_POLICY,
        domain=Domain.PILOT,
        source="demo policy shaped on 14 CFR 121.639 and FAA InFO 08004; "
        "alternate test from 14 CFR 121.619(a)",
        description="Policy limit: landing fuel, after any hold and any required "
        "alternate, covers the final reserve",
        # Fuel state is private to the pilot; others only learn it is infeasible.
        public_reason=PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        check=check_fuel_policy,
    ),
)
