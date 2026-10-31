import pytest
from pydantic import ValidationError

from app.negotiation.contracts import (
    ArrivalSlot,
    Consensus,
    Domain,
    FlightPlanAction,
    GateOccupancy,
    NoDeal,
    Package,
    Provenance,
    Response,
    ResponseKind,
    Scenario,
    Sourced,
    Violation,
    WeatherPeriod,
)
from tests.negotiation.factories import BASELINE_PACKAGE, make_scenario


def test_every_scenario_field_carries_provenance() -> None:
    scenario = make_scenario()
    for name in Scenario.model_fields:
        field = getattr(scenario, name)
        assert isinstance(field, Sourced), name
        assert isinstance(field.provenance, Provenance), name


def test_provenance_is_required() -> None:
    with pytest.raises(ValidationError):
        Sourced[int].model_validate({"value": 3})


def test_provenance_is_kept_per_field() -> None:
    scenario = make_scenario(provenance=Provenance.REAL)
    assert scenario.earliest_arrival_min.provenance is Provenance.REAL
    assert {p.value for p in Provenance} == {"real", "derived", "synthetic"}


def test_models_are_immutable_and_reject_unknown_fields() -> None:
    scenario = make_scenario()
    with pytest.raises(ValidationError):
        scenario.flight_id = Sourced(value="X", provenance=Provenance.REAL)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        BASELINE_PACKAGE.gate_id = "B1"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Package.model_validate({**BASELINE_PACKAGE.model_dump(), "extra": 1})
    assert hash(BASELINE_PACKAGE) == hash(BASELINE_PACKAGE.model_copy())


def test_scenario_round_trips_through_json() -> None:
    scenario = make_scenario(taxi_in_min=None)
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario


def test_response_counter_must_match_kind() -> None:
    kwargs = {
        "turn": 1,
        "responder": Domain.ATC,
        "package": BASELINE_PACKAGE,
        "reason": "r",
    }
    Response(kind=ResponseKind.ACCEPT, **kwargs)
    Response(kind=ResponseKind.COUNTER, counter=BASELINE_PACKAGE, **kwargs)
    with pytest.raises(ValidationError):
        Response(kind=ResponseKind.COUNTER, **kwargs)
    with pytest.raises(ValidationError):
        Response(kind=ResponseKind.ACCEPT, counter=BASELINE_PACKAGE, **kwargs)


def test_consensus_needs_every_domain_once() -> None:
    common = {"turn": 1, "package": BASELINE_PACKAGE, "rules_checked": ("A",)}
    Consensus(accepted_by=(Domain.ATC, Domain.PILOT, Domain.GROUND), **common)
    for accepted in (
        (Domain.ATC, Domain.PILOT),
        (Domain.ATC, Domain.ATC, Domain.PILOT),
        (Domain.ATC, Domain.PILOT, Domain.GROUND, Domain.GROUND),
    ):
        with pytest.raises(ValidationError):
            Consensus(accepted_by=accepted, **common)


def test_turn_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Response(
            turn=0,
            responder=Domain.ATC,
            kind=ResponseKind.ACCEPT,
            package=BASELINE_PACKAGE,
            reason="r",
        )


def test_occupancy_and_weather_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        GateOccupancy(gate_id="A", flight_id="F", start_min=5, end_min=5)
    with pytest.raises(ValidationError):
        WeatherPeriod(start_min=5, end_min=4, ceiling_ft=1, visibility_tenth_mi=1)
    WeatherPeriod(start_min=5, end_min=5, ceiling_ft=1, visibility_tenth_mi=1)


def test_result_kinds_are_discriminated() -> None:
    no_deal = NoDeal(
        binding_rule_ids=("X",), eliminations=(), packages_considered=1, reason="r"
    )
    assert no_deal.kind == "NO_DEAL"
    violation = Violation(rule_id="X", domain=Domain.ATC, message="m", source="s")
    assert violation.domain is Domain.ATC
    assert (
        ArrivalSlot(runway_id="1", time_min=2).time_min == 2
        and FlightPlanAction.DIRECT.value == "direct"
    )
