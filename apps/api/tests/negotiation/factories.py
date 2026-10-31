"""Hand-built scenario fixtures and a seeded random generator.

Nothing here assumes DOT column names. `make_scenario` starts from one fully
legal baseline; override a field with a raw value, or `None` for unknown.
"""

import random
from typing import Any

from app.negotiation.contracts import (
    AircraftSize,
    ArrivalSlot,
    Connection,
    DecisionPoint,
    FlightPlanAction,
    FlightRules,
    Gate,
    GateOccupancy,
    OtherArrival,
    Package,
    Provenance,
    Runway,
    Scenario,
    Sourced,
    Taxiway,
    WakeCategory,
    WeatherPeriod,
)

# Baseline times: the flight can land at 100; gate-in is 110 (taxi-in 10).
EARLIEST = 100
TAXI_IN = 10
GATE_IN = EARLIEST + TAXI_IN

BASELINE: dict[str, Any] = {
    "scenario_id": "S-1",
    "flight_id": "AB123",
    "decision_point": DecisionPoint.AIRBORNE,
    "flight_rules": FlightRules.IFR,
    "wake_category": WakeCategory.LARGE,
    "aircraft_size": AircraftSize.NARROW_BODY,
    "earliest_arrival_min": EARLIEST,
    "latest_arrival_min": EARLIEST + 20,
    "taxi_in_min": TAXI_IN,
    "fuel_on_board_kg": 10_000,
    "trip_fuel_kg": 4_000,
    "cruise_burn_kg_per_min": 50,
    "hold_burn_kg_per_min": 40,
    "alternate_fuel_kg": 1_000,
    # Ceiling below 2,000 ft, so an alternate is required and its fuel counts.
    "destination_forecast": (
        WeatherPeriod(
            start_min=0, end_min=1_000, ceiling_ft=1_500, visibility_tenth_mi=100
        ),
    ),
    "runways": (
        Runway(runway_id="28L", closed=False),
        Runway(runway_id="28R", closed=False),
    ),
    "taxiways": (
        Taxiway(taxiway_id="T1", closed=False),
        Taxiway(taxiway_id="T2", closed=False),
    ),
    "gates": (
        Gate(gate_id="A1", taxiway_id="T1", max_size=AircraftSize.NARROW_BODY),
        Gate(gate_id="A2", taxiway_id="T1", max_size=AircraftSize.REGIONAL),
        Gate(gate_id="B1", taxiway_id="T2", max_size=AircraftSize.WIDE_BODY),
    ),
    "other_arrivals": (
        OtherArrival(
            flight_id="XY9",
            wake_category=WakeCategory.LARGE,
            runway_id="28L",
            time_min=90,
        ),
    ),
    "gate_occupancies": (
        GateOccupancy(gate_id="A1", flight_id="OLD1", start_min=20, end_min=60),
        GateOccupancy(gate_id="B1", flight_id="OLD2", start_min=0, end_min=400),
    ),
    "planned_gate": "A1",
    "next_departure_min": 200,
    "next_leg_turnaround_hard": True,
    "ground_shift_end_min": 300,
    "connections": (Connection(passengers=20, departure_min=150),),
}

BASELINE_PACKAGE = Package(
    slot=ArrivalSlot(runway_id="28L", time_min=EARLIEST),
    gate_id="A1",
    action=FlightPlanAction.DIRECT,
)


def make_scenario(
    provenance: Provenance = Provenance.SYNTHETIC, **overrides: Any
) -> Scenario:
    unknown = set(overrides) - set(BASELINE)
    if unknown:
        raise KeyError(f"not scenario fields: {sorted(unknown)}")
    values = {**BASELINE, **overrides}
    return Scenario(
        **{
            name: Sourced(value=value, provenance=provenance)
            for name, value in values.items()
        }
    )


def make_package(
    time_min: int = EARLIEST,
    runway_id: str = "28L",
    gate_id: str = "A1",
    action: FlightPlanAction = FlightPlanAction.DIRECT,
) -> Package:
    return Package(
        slot=ArrivalSlot(runway_id=runway_id, time_min=time_min),
        gate_id=gate_id,
        action=action,
    )


# Fields a random scenario may leave unknown, to exercise failing closed.
_UNKNOWN_CANDIDATES = (
    "decision_point",
    "flight_rules",
    "destination_forecast",
    "wake_category",
    "aircraft_size",
    "taxi_in_min",
    "fuel_on_board_kg",
    "hold_burn_kg_per_min",
    "other_arrivals",
    "gate_occupancies",
    "next_departure_min",
    "next_leg_turnaround_hard",
    "ground_shift_end_min",
    "connections",
    "planned_gate",
)


def random_scenario(seed: int, small: bool = False) -> Scenario:
    """A seeded scenario. `small` keeps the package set cheap to brute force."""
    rng = random.Random(seed)
    earliest = rng.randrange(0, 200)
    slots = rng.randrange(1, 4) if small else rng.randrange(1, 9)
    latest = earliest + 5 * (slots - 1)

    runway_ids = ["R1", "R2", "R3"][: rng.randrange(1, 3 if small else 4)]
    taxiway_ids = ["T1", "T2", "T3"][: rng.randrange(1, 3 if small else 4)]
    runways = tuple(Runway(runway_id=r, closed=rng.random() < 0.25) for r in runway_ids)
    taxiways = tuple(
        Taxiway(taxiway_id=t, closed=rng.random() < 0.2) for t in taxiway_ids
    )
    gates = tuple(
        Gate(
            gate_id=f"G{i}",
            taxiway_id=rng.choice(taxiway_ids),
            max_size=rng.choice(list(AircraftSize)),
        )
        for i in range(rng.randrange(1, 3 if small else 5))
    )
    others = tuple(
        OtherArrival(
            flight_id=f"O{i}",
            wake_category=rng.choice(list(WakeCategory)),
            runway_id=rng.choice(runway_ids),
            time_min=rng.randrange(earliest - 15, latest + 15),
        )
        for i in range(rng.randrange(0, 4 if small else 7))
    )
    occupancies: list[GateOccupancy] = []
    for i in range(rng.randrange(0, 3 if small else 5)):
        start = rng.randrange(earliest - 20, latest + 60)
        occupancies.append(
            GateOccupancy(
                gate_id=rng.choice(gates).gate_id,
                flight_id=f"P{i}",
                start_min=start,
                end_min=start + rng.randrange(20, 90),
            )
        )

    trip = rng.randrange(2_000, 6_000)
    cruise = rng.randrange(30, 80)
    alternate = rng.choice([0, 0, 800, 1_500])
    reserve = 45 * cruise + alternate
    weather_start = earliest - 120 + rng.choice([0, 0, 0, 90])  # sometimes a gap
    forecast = tuple(
        WeatherPeriod(
            start_min=start,
            end_min=start + 120,
            ceiling_ft=rng.choice([1_500, 1_999, 2_000, 5_000]),
            visibility_tenth_mi=rng.choice([20, 29, 30, 100]),
        )
        for start in range(weather_start, latest + 130, 120)
    )
    overrides: dict[str, Any] = {
        "scenario_id": f"R-{seed}",
        "flight_id": f"F{seed}",
        "decision_point": rng.choice(list(DecisionPoint)),
        "flight_rules": rng.choice(list(FlightRules)),
        "destination_forecast": forecast,
        "wake_category": rng.choice(list(WakeCategory)),
        "aircraft_size": rng.choice(list(AircraftSize)),
        "earliest_arrival_min": earliest,
        "latest_arrival_min": latest,
        "taxi_in_min": rng.randrange(3, 25),
        "fuel_on_board_kg": trip + reserve + rng.randrange(-300, 1_200),
        "trip_fuel_kg": trip,
        "cruise_burn_kg_per_min": cruise,
        "hold_burn_kg_per_min": rng.randrange(20, 90),
        "alternate_fuel_kg": alternate,
        "runways": runways,
        "taxiways": taxiways,
        "gates": gates,
        "other_arrivals": others,
        "gate_occupancies": tuple(occupancies),
        "planned_gate": rng.choice(gates).gate_id,
        "next_departure_min": earliest + rng.randrange(30, 240),
        "next_leg_turnaround_hard": rng.random() < 0.5,
        "ground_shift_end_min": earliest + rng.randrange(60, 300),
        "connections": tuple(
            Connection(
                passengers=rng.randrange(1, 40),
                departure_min=earliest + rng.randrange(30, 200),
            )
            for _ in range(rng.randrange(0, 4))
        ),
    }
    for name in _UNKNOWN_CANDIDATES:
        if rng.random() < 0.03:
            overrides[name] = None
    return make_scenario(**overrides)
