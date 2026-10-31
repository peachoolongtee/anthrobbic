"""An independent harm check on a final package.

This module must not import `app.negotiation.rules`, or anything that does
(`options`, `utility`, `fallback`). Values come from `rule_values`, but every
judgement is reworked here by a different route, so a slip in one implementation
shows up as a disagreement rather than passing twice:

- wake: distance flown in the gap, in nautical miles, not minutes rounded up
- throughput: every 60-minute window holding the arrival, minute by minute
- fuel: endurance left in minutes, not kilograms, with a sweep over the forecast
- gate: padded intervals, not a clear-gap formula
- closed resources: every matching record, not the first one found
- slot: inside the window and on the grid, from the package alone

A shared misreading of the plan still passes both. A disagreement is a finding
to report, never something to reconcile quietly.
"""

from collections.abc import Sequence
from enum import StrEnum
from fractions import Fraction

from app.negotiation import rule_values as rv
from app.negotiation.contracts import (
    FlightPlanAction,
    FrozenModel,
    Package,
    Runway,
    Scenario,
    Violation,
    ViolationCause,
    WakeCategory,
    WeatherPeriod,
)

# Read by key so that this module loads on a core without the per-class speed.
_SMALL_APPROACH_SPEED_KEY = "approach_ground_speed_kt.small"


class HarmCheck(StrEnum):
    WAKE_SPACING = "wake_spacing"
    THROUGHPUT = "throughput"
    FUEL_MARGIN = "fuel_margin"
    GATE_OVERLAP = "gate_overlap"
    CLOSED_RESOURCE = "closed_resource"
    SLOT_VALIDITY = "slot_validity"


class HarmVerdict(StrEnum):
    CLEAR = "clear"
    HARM = "harm"
    UNKNOWN = "unknown"  # an input was missing, so this check could not clear it


class HarmFinding(FrozenModel):
    check: HarmCheck
    verdict: HarmVerdict
    detail: str


class HarmReport(FrozenModel):
    findings: tuple[HarmFinding, ...]

    @property
    def harmful(self) -> bool:
        return any(f.verdict is HarmVerdict.HARM for f in self.findings)

    @property
    def unknown(self) -> bool:
        return any(f.verdict is HarmVerdict.UNKNOWN for f in self.findings)

    def verdict_of(self, check: HarmCheck) -> HarmVerdict:
        return next(f.verdict for f in self.findings if f.check is check)


class DisagreementKind(StrEnum):
    # The serious one: rules passed a package this check calls harmful.
    HARM_ONLY = "harm_only"
    # Rules rejected on a real limit, but this check finds no harm.
    RULES_ONLY = "rules_only"
    # Rules passed, but this check could not clear the package.
    HARM_UNKNOWN = "harm_unknown"
    # Rules failed closed on missing data this check did not need.
    RULES_FAIL_CLOSED_ONLY = "rules_fail_closed_only"


class Disagreement(FrozenModel):
    check: HarmCheck
    kind: DisagreementKind
    rule_ids: tuple[str, ...]
    detail: str


def _finding(check: HarmCheck, verdict: HarmVerdict, detail: str) -> HarmFinding:
    return HarmFinding(check=check, verdict=verdict, detail=detail)


def _same_runway_ids(runways: Sequence[Runway], runway_id: str) -> set[str]:
    """This runway and any that share a parallel group with it. They count as one."""
    group_of = {r.runway_id: getattr(r, "parallel_group", None) for r in runways}
    mine = group_of.get(runway_id)
    if mine is None:
        return {runway_id}
    return {rid for rid, group in group_of.items() if group == mine} | {runway_id}


def _approach_knots(follower: WakeCategory) -> int:
    general = rv.RULE_VALUES[rv.APPROACH_GROUND_SPEED_KT]
    if follower is WakeCategory.SMALL:
        return rv.RULE_VALUES.get(_SMALL_APPROACH_SPEED_KEY, general).value
    return general.value


def _wake_spacing(scenario: Scenario, package: Package) -> HarmFinding:
    check = HarmCheck.WAKE_SPACING
    own = scenario.wake_category.value
    traffic = scenario.other_arrivals.value
    runways = scenario.runways.value
    if own is None or traffic is None or runways is None:
        return _finding(check, HarmVerdict.UNKNOWN, "wake or traffic unknown")

    per_hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    same_runway = _same_runway_ids(runways, package.slot.runway_id)
    worst: tuple[Fraction, int, str] | None = None
    for flight in traffic:
        if flight.runway_id not in same_runway:
            continue
        minutes_after = package.slot.time_min - flight.time_min
        # At the same minute both orders apply, and both must hold.
        pairs: list[tuple[WakeCategory, WakeCategory]] = []
        if minutes_after >= 0:
            pairs.append((flight.wake_category, own))
        if minutes_after <= 0:
            pairs.append((own, flight.wake_category))
        for leader, follower in pairs:
            needed_nm = rv.wake_separation(leader, follower).value
            flown_nm = Fraction(
                abs(minutes_after) * _approach_knots(follower), per_hour
            )
            if flown_nm < needed_nm and (worst is None or flown_nm < worst[0]):
                worst = (flown_nm, needed_nm, flight.flight_id)
    if worst is None:
        return _finding(check, HarmVerdict.CLEAR, "spacing met on this runway")
    flown, needed, flight_id = worst
    return _finding(
        check,
        HarmVerdict.HARM,
        f"{float(flown):.2f} nm from {flight_id}; needs {needed} nm",
    )


def _weather_is_good(period: WeatherPeriod) -> bool:
    return (
        period.ceiling_ft >= rv.rule_value(rv.ALTERNATE_MIN_CEILING_FT).value
        and period.visibility_tenth_mi
        >= rv.rule_value(rv.ALTERNATE_MIN_VISIBILITY_TENTH_MI).value
    )


def _throughput(scenario: Scenario, package: Package) -> HarmFinding:
    """The cap follows the forecast at this arrival. Without good weather known at
    that minute, the instrument cap applies."""
    check = HarmCheck.THROUGHPUT
    traffic = scenario.other_arrivals.value
    runways = scenario.runways.value
    if traffic is None or runways is None:
        return _finding(check, HarmVerdict.UNKNOWN, "traffic unknown")

    eta = package.slot.time_min
    forecast = scenario.destination_forecast.value or ()
    at_eta = [p for p in forecast if p.start_min <= eta <= p.end_min]
    visual = bool(at_eta) and all(_weather_is_good(p) for p in at_eta)
    cap = rv.rule_value(
        rv.RUNWAY_HOURLY_ARRIVALS_VFR if visual else rv.RUNWAY_HOURLY_ARRIVALS_IFR
    ).value

    hour = rv.rule_value(rv.MINUTES_PER_HOUR).value
    same_runway = _same_runway_ids(runways, package.slot.runway_id)
    times = [f.time_min for f in traffic if f.runway_id in same_runway]
    for window_start in range(eta - hour + 1, eta + 1):
        count = 1 + sum(window_start <= t < window_start + hour for t in times)
        if count > cap:
            return _finding(
                check,
                HarmVerdict.HARM,
                f"{count} arrivals in the hour from {window_start}; cap is {cap}",
            )
    return _finding(check, HarmVerdict.CLEAR, f"within the cap of {cap}")


def _needs_alternate(scenario: Scenario, package: Package) -> bool:
    """Sweep the window at half-minute points, since periods are closed intervals
    and the half-minute between two adjoining ones is not covered by either."""
    forecast = scenario.destination_forecast.value
    if forecast is None:
        return True
    margin = rv.rule_value(rv.ALTERNATE_WINDOW_MIN).value
    first = 2 * (package.slot.time_min - margin)
    last = 2 * (package.slot.time_min + margin)
    for half_minute in range(first, last + 1):
        covering = [
            period
            for period in forecast
            if 2 * period.start_min <= half_minute <= 2 * period.end_min
        ]
        if not covering or not all(_weather_is_good(p) for p in covering):
            return True
    return False


def _fuel_margin(scenario: Scenario, package: Package) -> HarmFinding:
    check = HarmCheck.FUEL_MARGIN
    on_board = scenario.fuel_on_board_kg.value
    trip = scenario.trip_fuel_kg.value
    cruise = scenario.cruise_burn_kg_per_min.value
    earliest = scenario.earliest_arrival_min.value
    if on_board is None or trip is None or cruise is None or earliest is None:
        return _finding(check, HarmVerdict.UNKNOWN, "fuel input unknown")
    if cruise <= 0 or on_board < 0 or trip < 0:
        return _finding(check, HarmVerdict.UNKNOWN, "fuel input cannot be real")

    extra_minutes = max(package.slot.time_min - earliest, 0)
    if package.action is FlightPlanAction.HOLD:
        rate = scenario.hold_burn_kg_per_min.value
        if rate is None or rate < 0:
            return _finding(check, HarmVerdict.UNKNOWN, "hold burn unknown")
    elif package.action is FlightPlanAction.VECTOR:
        rate = cruise
    else:
        rate = 0

    usable = on_board - trip - extra_minutes * rate
    if _needs_alternate(scenario, package):
        alternate = scenario.alternate_fuel_kg.value
        if alternate is None or alternate < 0:
            return _finding(check, HarmVerdict.UNKNOWN, "alternate fuel unknown")
        usable -= alternate

    endurance = Fraction(usable, cruise)
    reserve = rv.rule_value(rv.FUEL_RESERVE_MIN).value
    if endurance < reserve:
        return _finding(
            check,
            HarmVerdict.HARM,
            f"{float(endurance):.1f} min of cruise left; needs {reserve} min",
        )
    return _finding(
        check, HarmVerdict.CLEAR, f"{float(endurance):.1f} min of cruise left"
    )


def _gate_overlap(scenario: Scenario, package: Package) -> HarmFinding:
    """The gate is held from gate-in until the later of the minimum turnaround and
    any known next departure, since the aircraft stays until it leaves."""
    check = HarmCheck.GATE_OVERLAP
    taxi = scenario.taxi_in_min.value
    size = scenario.aircraft_size.value
    occupancies = scenario.gate_occupancies.value
    if taxi is None or size is None or occupancies is None:
        return _finding(check, HarmVerdict.UNKNOWN, "gate input unknown")

    buffer = rv.rule_value(rv.GATE_BUFFER_MIN).value
    arrive = package.slot.time_min + taxi
    leave = arrive + rv.turnaround(size).value
    departure = scenario.next_departure_min.value
    if departure is not None and departure > leave:
        leave = departure
    for other in occupancies:
        if other.gate_id != package.gate_id:
            continue
        blocked_from = other.start_min - buffer
        blocked_to = other.end_min + buffer
        if arrive < blocked_to and blocked_from < leave:
            return _finding(
                check,
                HarmVerdict.HARM,
                f"stay {arrive}-{leave} enters {other.flight_id}'s blocked "
                f"period {blocked_from}-{blocked_to}",
            )
    return _finding(check, HarmVerdict.CLEAR, "no gate conflict")


def _closed_resource(scenario: Scenario, package: Package) -> HarmFinding:
    check = HarmCheck.CLOSED_RESOURCE
    runways = scenario.runways.value
    gates = scenario.gates.value
    taxiways = scenario.taxiways.value
    if runways is None or gates is None or taxiways is None:
        return _finding(check, HarmVerdict.UNKNOWN, "airport map unknown")

    runway_states = {r.closed for r in runways if r.runway_id == package.slot.runway_id}
    if True in runway_states:
        return _finding(
            check, HarmVerdict.HARM, f"runway {package.slot.runway_id} is closed"
        )
    if not runway_states:
        return _finding(
            check, HarmVerdict.UNKNOWN, f"runway {package.slot.runway_id} not listed"
        )

    # Every record for this gate counts, in case a map lists a gate twice.
    routes = {g.taxiway_id for g in gates if g.gate_id == package.gate_id}
    if not routes:
        return _finding(
            check, HarmVerdict.UNKNOWN, f"gate {package.gate_id} not listed"
        )
    closed_taxiways = {t.taxiway_id for t in taxiways if t.closed}
    known_taxiways = {t.taxiway_id for t in taxiways}
    blocked = routes & closed_taxiways
    if blocked:
        return _finding(
            check,
            HarmVerdict.HARM,
            f"gate {package.gate_id} is served by closed taxiway {min(blocked)}",
        )
    if routes - known_taxiways:
        return _finding(
            check, HarmVerdict.UNKNOWN, f"gate {package.gate_id}'s taxiway not listed"
        )
    return _finding(check, HarmVerdict.CLEAR, "runway and taxiway open")


def _slot_validity(scenario: Scenario, package: Package) -> HarmFinding:
    check = HarmCheck.SLOT_VALIDITY
    earliest = scenario.earliest_arrival_min.value
    latest = scenario.latest_arrival_min.value
    if earliest is None or latest is None:
        return _finding(check, HarmVerdict.UNKNOWN, "planning window unknown")
    time_min = package.slot.time_min
    if not earliest <= time_min <= latest:
        return _finding(
            check,
            HarmVerdict.HARM,
            f"slot {time_min} is outside the window {earliest}-{latest}",
        )
    step = rv.rule_value(rv.SLOT_STEP_MIN).value
    if (time_min - earliest) % step:
        return _finding(
            check, HarmVerdict.HARM, f"slot {time_min} is off the {step}-minute grid"
        )
    return _finding(check, HarmVerdict.CLEAR, "slot is in the window and on the grid")


def inspect_package(scenario: Scenario, package: Package) -> HarmReport:
    """Judge one final package, returning a verdict for every check."""
    return HarmReport(
        findings=(
            _wake_spacing(scenario, package),
            _throughput(scenario, package),
            _fuel_margin(scenario, package),
            _gate_overlap(scenario, package),
            _closed_resource(scenario, package),
            _slot_validity(scenario, package),
        )
    )


# Rule IDs are strings here so that this module imports nothing from `rules`. A
# test holds them to the registry, so a renamed rule cannot drop out of this map.
RULES_COVERED: dict[HarmCheck, tuple[str, ...]] = {
    HarmCheck.WAKE_SPACING: ("ATC-WAKE-SEP",),
    HarmCheck.THROUGHPUT: ("ATC-RWY-THROUGHPUT",),
    HarmCheck.FUEL_MARGIN: ("PLT-FUEL-POLICY",),
    HarmCheck.GATE_OVERLAP: ("GND-GATE-OVERLAP",),
    HarmCheck.CLOSED_RESOURCE: ("ATC-RWY-CLOSED", "ATC-TWY-CLOSED"),
}
# The fuel rule also rejects impossible actions and incoherent delays, which are
# not fuel harm. Only its kilogram violations (and missing data) are comparable.
_FUEL_MARGIN_UNIT = "kg"


def _comparable(check: HarmCheck, violation: Violation) -> bool:
    if violation.rule_id not in RULES_COVERED[check]:
        return False
    if check is not HarmCheck.FUEL_MARGIN:
        return True
    return (
        violation.cause is ViolationCause.MISSING_DATA
        or violation.unit == _FUEL_MARGIN_UNIT
    )


def compare_with_rules(
    report: HarmReport, violations: Sequence[Violation]
) -> tuple[Disagreement, ...]:
    """Where this check and the rules reach different answers on one package.

    Rules outside `RULES_COVERED` (gate size, turnaround) are out of this check's
    scope, so they are never a disagreement. Slot validity has no one rule to pair
    with, so it disagrees only when the rules passed the package outright.
    """
    found: list[Disagreement] = []
    for finding in report.findings:
        if finding.check is HarmCheck.SLOT_VALIDITY:
            if finding.verdict is HarmVerdict.HARM and not violations:
                found.append(
                    Disagreement(
                        check=finding.check,
                        kind=DisagreementKind.HARM_ONLY,
                        rule_ids=(),
                        detail=finding.detail,
                    )
                )
            continue
        matching = [v for v in violations if _comparable(finding.check, v)]
        real = [v for v in matching if v.cause is ViolationCause.CONSTRAINT]
        kind: DisagreementKind | None = None
        if finding.verdict is HarmVerdict.HARM and not matching:
            kind = DisagreementKind.HARM_ONLY
        elif finding.verdict is HarmVerdict.UNKNOWN and not matching:
            kind = DisagreementKind.HARM_UNKNOWN
        elif finding.verdict is HarmVerdict.CLEAR and real:
            kind = DisagreementKind.RULES_ONLY
        elif finding.verdict is HarmVerdict.CLEAR and matching:
            kind = DisagreementKind.RULES_FAIL_CLOSED_ONLY
        if kind is not None:
            found.append(
                Disagreement(
                    check=finding.check,
                    kind=kind,
                    rule_ids=tuple(sorted({v.rule_id for v in matching})),
                    detail=finding.detail,
                )
            )
    return tuple(found)
