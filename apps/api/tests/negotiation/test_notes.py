"""Notes are seeded, synthetic and generated from a hidden structured preference."""

import pytest

from app.negotiation.contracts import Domain, Provenance, Runway
from app.negotiation.notes import (
    PreferenceKind,
    ground_truth_preferences,
    notes_for,
    preference_score,
    rules_out,
)
from app.negotiation.options import enumerate_packages
from app.negotiation.rules import check_package
from tests.negotiation.factories import make_scenario, random_scenario


def test_same_inputs_give_identical_notes_and_truth() -> None:
    scenario = make_scenario()
    assert notes_for(scenario, 3) == notes_for(scenario, 3)
    assert ground_truth_preferences(scenario, 3) == ground_truth_preferences(
        scenario, 3
    )


def test_seeds_vary_wording_and_preferences() -> None:
    # With no occupancies two gates are legal, so ramp notes have gates to name.
    scenario = make_scenario(gate_occupancies=())
    assert len({notes_for(scenario, seed) for seed in range(12)}) > 1
    texts = {
        note.text
        for seed in range(30)
        for note in notes_for(scenario, seed)
        if note.domain is Domain.GROUND and note.note_id == "ramp-1"
    }
    assert len(texts) >= 4


def test_every_note_is_labelled_synthetic_and_covers_each_domain_topic() -> None:
    notes = notes_for(make_scenario(), 1)
    assert all(note.provenance is Provenance.SYNTHETIC for note in notes)
    assert {(note.domain, note.topic) for note in notes} == {
        (Domain.PILOT, "crew"),
        (Domain.GROUND, "ramp"),
        (Domain.ATC, "weather"),
    }


def test_truth_lines_up_with_notes() -> None:
    scenario = make_scenario()
    notes = notes_for(scenario, 5)
    truths = ground_truth_preferences(scenario, 5)
    assert [n.note_id for n in notes] == [t.note_id for t in truths]
    assert [n.domain for n in notes] == [t.domain for t in truths]


@pytest.mark.parametrize("seed", range(20))
def test_each_run_has_ranking_irrelevant_and_ambiguous_notes(seed: int) -> None:
    relevance = {t.relevance for t in ground_truth_preferences(make_scenario(), seed)}
    assert relevance == {"affects_ranking", "irrelevant", "ambiguous"}


@pytest.mark.parametrize("seed", range(30))
def test_ranking_notes_really_separate_legal_packages(seed: int) -> None:
    """Not decorative: each such note must score two legal packages differently."""
    scenario = random_scenario(seed)
    legal = [p for p in enumerate_packages(scenario) if not check_package(scenario, p)]
    for truth in ground_truth_preferences(scenario, seed):
        scores = {preference_score(truth, package) for package in legal}
        if truth.relevance == "affects_ranking":
            assert len(scores) > 1, truth
        else:
            assert len(scores) <= 1, truth


def test_a_quiet_note_is_not_scored() -> None:
    scenario = make_scenario()
    package = enumerate_packages(scenario)[0]
    quiet = [
        t
        for t in ground_truth_preferences(scenario, 2)
        if t.kind in (PreferenceKind.NO_PREFERENCE, PreferenceKind.AMBIGUOUS)
    ]
    assert quiet
    assert all(preference_score(t, package) == 0 for t in quiet)


def test_with_nothing_legal_no_note_claims_to_matter() -> None:
    scenario = make_scenario(
        runways=(Runway(runway_id="28L", closed=True, parallel_group=None),)
    )
    truths = ground_truth_preferences(scenario, 1)
    assert truths
    assert all(t.relevance != "affects_ranking" for t in truths)


def test_some_avoid_notes_are_firm_and_rule_their_target_out() -> None:
    scenario = make_scenario(gate_occupancies=())
    legal = [p for p in enumerate_packages(scenario) if not check_package(scenario, p)]
    pairs = [
        (note, truth)
        for seed in range(60)
        for note, truth in zip(
            notes_for(scenario, seed),
            ground_truth_preferences(scenario, seed),
            strict=True,
        )
    ]
    firm = [(n, t) for n, t in pairs if t.firm]
    assert firm
    assert any(not t.firm and t.kind.value.startswith("avoid_") for _, t in pairs)
    assert all(t.kind.value.startswith("avoid_") for _, t in firm)
    soft_texts = {n.text for n, t in pairs if not t.firm}
    assert not soft_texts & {n.text for n, _ in firm}
    for _, truth in firm:
        ruled_out = [p for p in legal if rules_out(truth, p)]
        assert ruled_out
        assert len(ruled_out) < len(legal)  # a firm note never empties the legal set


def test_a_soft_note_rules_nothing_out() -> None:
    scenario = make_scenario(gate_occupancies=())
    package = enumerate_packages(scenario)[0]
    for seed in range(20):
        for truth in ground_truth_preferences(scenario, seed):
            if not truth.firm:
                assert not rules_out(truth, package)


def test_notes_name_no_private_values() -> None:
    scenario = make_scenario(
        fuel_on_board_kg=98_765, next_departure_min=4_321, ground_shift_end_min=8_765
    )
    text = " ".join(note.text for note in notes_for(scenario, 4))
    for private in ("98765", "4321", "8765"):
        assert private not in text
