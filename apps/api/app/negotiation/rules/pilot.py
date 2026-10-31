"""Pilot rules. Each is pure and returns every violation.

The fuel limit is the challenge workbook's: a final reserve of 30 minutes of
holding fuel plus a contingency of 5% of trip fuel, and an alternate when the
destination forecast (tested the way 14 CFR 121.619(a) does, as our policy)
needs one. The workbook values are synthetic planning limits, not regulations.
The rule ID keeps "POLICY" for stability. Crew duty is the workbook's 13 hours
from report time.
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
)
from app.negotiation.rules.shared import is_poor

FUEL_POLICY = "PLT-FUEL-POLICY"
CREW_DUTY = "PLT-CREW-DUTY"

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


# Quantities that cannot be real if they break these bounds. Bad data fails
# closed, the same as missing data.
_MUST_BE_POSITIVE = frozenset(
    {
        "cruise_burn_kg_per_min",
        "hold_burn_kg_per_min",
        "trip_fuel_kg",
        "alternate_fuel_kg",
    }
)
_MUST_NOT_BE_NEGATIVE = frozenset({"fuel_on_board_kg"})


def _problem(name: str, value: object) -> str | None:
    """ "unknown" or "invalid" when a needed input cannot be used, else None."""
    if value is None:
        return "unknown"
    if isinstance(value, int) and not isinstance(value, bool):
        if name in _MUST_BE_POSITIVE and value <= 0:
            return "invalid"
        if name in _MUST_NOT_BE_NEGATIVE and value < 0:
            return "invalid"
    return None


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
    return any(is_poor(p) for p in relevant)


def project_fuel(scenario: Scenario, package: Package) -> FuelProjection | None:
    """Landing fuel against the workbook reserve, or None if an input is unknown.

    Required fuel is the final reserve in minutes of holding fuel, plus the
    contingency as a share of trip fuel (rounded up), plus the alternate when
    one is required.
    """
    delay = delay_min(scenario, package)
    burn = extra_burn_kg(scenario, package)
    on_board = scenario.fuel_on_board_kg.value
    trip = scenario.trip_fuel_kg.value
    hold = scenario.hold_burn_kg_per_min.value
    needs_alternate = alternate_required(scenario, package)
    alternate = scenario.alternate_fuel_kg.value if needs_alternate else 0
    if (
        delay is None
        or burn is None
        or on_board is None
        or trip is None
        or hold is None
        or alternate is None
    ):
        return None
    reserve_min = rv.rule_value(rv.FUEL_RESERVE_MIN).value
    contingency_pct = rv.rule_value(rv.FUEL_CONTINGENCY_PCT).value
    percent = rv.rule_value(rv.PERCENT_BASE).value
    contingency = (trip * contingency_pct + percent - 1) // percent  # rounded up
    return FuelProjection(
        delay_min=delay,
        extra_burn_kg=burn,
        landing_fuel_kg=on_board - trip - burn,
        required_kg=reserve_min * hold + contingency + alternate,
        alternate_required=needs_alternate,
    )


def check_fuel_policy(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """Fuel at landing, after any hold and any required alternate, must meet
    the challenge workbook's reserve and contingency."""
    reserve = rv.rule_value(rv.FUEL_RESERVE_MIN)
    source = rv.reference(reserve)

    needed: dict[str, object] = {
        "decision_point": scenario.decision_point.value,
        "earliest_arrival_min": scenario.earliest_arrival_min.value,
        "fuel_on_board_kg": scenario.fuel_on_board_kg.value,
        "trip_fuel_kg": scenario.trip_fuel_kg.value,
        "hold_burn_kg_per_min": scenario.hold_burn_kg_per_min.value,
    }
    if alternate_required(scenario, package):
        needed["alternate_fuel_kg"] = scenario.alternate_fuel_kg.value
    if package.action is FlightPlanAction.VECTOR:
        needed["cruise_burn_kg_per_min"] = scenario.cruise_burn_kg_per_min.value
    missing = [
        Violation.missing_data(FUEL_POLICY, Domain.PILOT, name, source, problem)
        for name, value in needed.items()
        if (problem := _problem(name, value)) is not None
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
                f"challenge workbook limit of {projection.required_kg} kg "
                f"({reserve.value} min of holding fuel plus contingency, "
                f"{alternate_note}); a synthetic planning limit, not a regulation",
                source,
                projection.landing_fuel_kg,
                projection.required_kg,
                "kg",
            )
        )
    return tuple(found)


def check_crew_duty(scenario: Scenario, package: Package) -> tuple[Violation, ...]:
    """The flight crew must be on blocks within their maximum duty.

    Duty runs from the (synthetic, schedule-seeded) report time. The crew is
    off duty at gate-in, the arrival slot plus taxi-in. `observed` is minutes
    on duty at gate-in and `limit` the maximum.
    """
    limit = rv.rule_value(rv.CREW_MAX_DUTY_MIN)
    source = rv.reference(limit)
    report = scenario.crew_report_min.value
    taxi = scenario.taxi_in_min.value
    missing: list[Violation] = []
    if report is None:
        missing.append(
            Violation.missing_data(CREW_DUTY, Domain.PILOT, "crew report time", source)
        )
    if taxi is None or taxi < 0:
        missing.append(
            Violation.missing_data(
                CREW_DUTY,
                Domain.PILOT,
                "taxi-in time",
                source,
                "unknown" if taxi is None else "invalid",
            )
        )
    if report is None or taxi is None or taxi < 0:
        return tuple(missing)
    on_duty = package.slot.time_min + taxi - report
    if on_duty > limit.value:
        return (
            Violation(
                rule_id=CREW_DUTY,
                domain=Domain.PILOT,
                message=f"crew on duty {on_duty} min at gate-in; the workbook "
                f"maximum is {limit.value} min from report time",
                source=source,
                observed=on_duty,
                limit=limit.value,
                unit="min",
            ),
        )
    return ()


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id=FUEL_POLICY,
        domain=Domain.PILOT,
        source="challenge workbook (fuel_and_crew): 30 minutes of holding fuel "
        "plus 5% of trip fuel; alternate test shaped on 14 CFR 121.619(a)",
        description="Workbook limit: landing fuel, after any hold and any "
        "required alternate, covers the final reserve and contingency",
        # Fuel state is private to the pilot; others only learn it is infeasible.
        public_reason=PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        check=check_fuel_policy,
    ),
    Rule(
        rule_id=CREW_DUTY,
        domain=Domain.PILOT,
        source="challenge workbook (fuel_and_crew): flight crew max duty, 13 hours "
        "from report time, simplified FAA Part 117",
        description="Flight crew must be on blocks within their maximum duty",
        public_reason=PublicReason.INFEASIBLE_FOR_ANOTHER_DOMAIN,
        check=check_crew_duty,
    ),
)
