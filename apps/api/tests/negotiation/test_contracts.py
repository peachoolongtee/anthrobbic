import hashlib
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.negotiation.contracts import (
    ArrivalSlot,
    Consensus,
    Domain,
    FlightPlanAction,
    GateOccupancy,
    NoDeal,
    NoDealReason,
    Package,
    Proposal,
    Provenance,
    Response,
    Scenario,
    Sourced,
    Violation,
    ViolationCause,
    WeatherPeriod,
    intersect_responses,
)
from tests.negotiation.factories import (
    BASELINE_PACKAGE,
    make_package,
    make_scenario,
)


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


def _pkg(time_min: int, gate: str = "A1") -> Package:
    return make_package(time_min=time_min, gate_id=gate)


def _response(domain: Domain, *packages: Package) -> Response:
    ids = tuple(p.terms_hash for p in packages)
    return Response(
        turn=1,
        responder=domain,
        acceptable_package_ids=ids,
        ranking=ids,
        reason="r",
    )


def test_response_ranking_must_order_exactly_the_acceptable_packages() -> None:
    a, b = _pkg(100).terms_hash, _pkg(105).terms_hash
    common: dict[str, Any] = {"turn": 1, "responder": Domain.ATC, "reason": "r"}
    Response(acceptable_package_ids=(a, b), ranking=(b, a), **common)
    Response(acceptable_package_ids=(), ranking=(), **common)
    for acceptable, ranking in (
        ((a, b), (a,)),
        ((a,), (a, b)),
        ((a, a), (a, a)),
        ((a,), (b,)),
    ):
        with pytest.raises(ValidationError):
            Response(acceptable_package_ids=acceptable, ranking=ranking, **common)


def test_intersection_is_ordered_by_code_not_by_rankings() -> None:
    p100, p105, p110 = _pkg(100), _pkg(105), _pkg(110)
    # ATC prefers the latest slot; the result still follows the code order.
    late_first = (p110.terms_hash, p105.terms_hash, p100.terms_hash)
    responses = [
        Response(
            turn=1,
            responder=Domain.ATC,
            acceptable_package_ids=late_first,
            ranking=late_first,
            reason="r",
        ),
        _response(Domain.PILOT, p105, p110, p100),
        _response(Domain.GROUND, p100, p105),
    ]
    assert intersect_responses(responses, [p110, p100, p105]) == (p100, p105)


def test_tie_break_order_is_time_then_runway_then_gate_then_action() -> None:
    packages = [
        make_package(105, "28L", "A1"),
        make_package(100, "28R", "A1"),
        make_package(100, "28L", "B1"),
        make_package(100, "28L", "A1", FlightPlanAction.HOLD),
        make_package(100, "28L", "A1"),
    ]
    responses = [_response(d, *packages) for d in Domain]
    assert intersect_responses(responses, packages) == (
        make_package(100, "28L", "A1"),
        make_package(100, "28L", "A1", FlightPlanAction.HOLD),
        make_package(100, "28L", "B1"),
        make_package(100, "28R", "A1"),
        make_package(105, "28L", "A1"),
    )


def test_empty_intersection() -> None:
    responses = [
        _response(Domain.ATC, _pkg(100)),
        _response(Domain.PILOT, _pkg(105)),
        _response(Domain.GROUND, _pkg(100), _pkg(105)),
    ]
    assert intersect_responses(responses, [_pkg(100), _pkg(105)]) == ()


def test_a_refusal_empties_the_intersection() -> None:
    responses = [
        _response(Domain.ATC, _pkg(100)),
        _response(Domain.PILOT),
        _response(Domain.GROUND, _pkg(100)),
    ]
    assert intersect_responses(responses, [_pkg(100)]) == ()


def test_intersection_fails_closed_on_missing_or_duplicate_domains() -> None:
    p = _pkg(100)
    two = [_response(Domain.ATC, p), _response(Domain.PILOT, p)]
    assert intersect_responses(two, [p]) == ()
    assert intersect_responses([], [p]) == ()
    twice = [*two, _response(Domain.ATC, p)]
    with pytest.raises(ValueError):
        intersect_responses(twice, [p])


def test_accepted_ids_matching_no_package_are_dropped() -> None:
    known, unknown = _pkg(100), _pkg(105)
    responses = [_response(d, known, unknown) for d in Domain]
    assert intersect_responses(responses, [known]) == (known,)


def test_consensus_needs_every_domain_once() -> None:
    common: dict[str, Any] = {
        "turn": 1,
        "package": BASELINE_PACKAGE,
        "rules_checked": ("A",),
    }
    Consensus(accepted_by=(Domain.ATC, Domain.PILOT, Domain.GROUND), **common)
    for accepted in (
        (Domain.ATC, Domain.PILOT),
        (Domain.ATC, Domain.ATC, Domain.PILOT),
        (Domain.ATC, Domain.PILOT, Domain.GROUND, Domain.GROUND),
    ):
        with pytest.raises(ValidationError):
            Consensus(accepted_by=accepted, **common)


def test_terms_hash_is_the_sha256_of_the_canonical_terms() -> None:
    canonical = '{"action":"direct","gate_id":"A1","runway_id":"28L","time_min":100}'
    assert BASELINE_PACKAGE.terms_hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_terms_hash_ignores_explanations() -> None:
    first = Proposal(
        turn=1, author=Domain.PILOT, package=BASELINE_PACKAGE, reason="fuel is tight"
    )
    second = Proposal(
        turn=2, author=Domain.ATC, package=BASELINE_PACKAGE, reason="another story"
    )
    assert first.package.terms_hash == second.package.terms_hash
    copy = Package.model_validate_json(BASELINE_PACKAGE.model_dump_json())
    assert copy.terms_hash == BASELINE_PACKAGE.terms_hash
    assert "reason" not in Package.model_fields


@pytest.mark.parametrize(
    "changed",
    [
        make_package(time_min=101),
        make_package(runway_id="28R"),
        make_package(gate_id="B1"),
        make_package(action=FlightPlanAction.HOLD),
    ],
)
def test_changing_any_term_changes_the_hash(changed: Package) -> None:
    assert changed.terms_hash != BASELINE_PACKAGE.terms_hash


def test_package_fields_are_grouped_by_authority() -> None:
    assert Package.AUTHORITY == {
        "airline_decides": ("gate_id",),
        "requires_request": ("slot", "action"),
    }
    labelled = {
        name: cast(dict[str, Any], field.json_schema_extra or {}).get("authority")
        for name, field in Package.model_fields.items()
    }
    assert labelled == {
        "slot": "requires_request",
        "gate_id": "airline_decides",
        "action": "requires_request",
    }
    for group, names in Package.AUTHORITY.items():
        assert all(labelled[n] == group for n in names)


def test_turn_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Response(
            turn=0,
            responder=Domain.ATC,
            acceptable_package_ids=(),
            ranking=(),
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
        reason_type=NoDealReason.NOTHING_LEGAL,
        binding_rule_ids=("X",),
        eliminations=(),
        packages_considered=1,
        nearest_package=None,
        nearest_violations=(),
        reason="r",
    )
    assert no_deal.kind == "NO_DEAL"
    violation = Violation(
        rule_id="X",
        domain=Domain.ATC,
        message="m",
        source="s",
        observed=1,
        limit=2,
        unit="min",
    )
    assert violation.domain is Domain.ATC
    assert violation.cause is ViolationCause.CONSTRAINT
    assert (
        ArrivalSlot(runway_id="1", time_min=2).time_min == 2
        and FlightPlanAction.DIRECT.value == "direct"
    )
