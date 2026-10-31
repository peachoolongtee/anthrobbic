"""Seeded, synthetic free-text notes, each written from a hidden preference.

Every domain gets a note that can change a ranking among legal packages and a
second note that is irrelevant or ambiguous, so an evaluation can score whether
an agent read each one correctly. `notes_for` is what prompts may contain.
`ground_truth_preferences` is the answer key and must never reach a prompt.

Targets are drawn uniformly from what actually separates legal packages, not
aimed at the fallback's choice, so the generator does not flatter the agents.
Notes name only public package terms (gate, runway, action, earlier or later).
"""

import random
from enum import StrEnum
from typing import Literal

from app.negotiation.contracts import (
    Domain,
    FlightPlanAction,
    FrozenModel,
    Package,
    Provenance,
    Scenario,
)
from app.negotiation.options import PackageBoundError, enumerate_packages
from app.negotiation.rules import check_package

TOPIC_BY_DOMAIN = {
    Domain.PILOT: "crew",
    Domain.GROUND: "ramp",
    Domain.ATC: "weather",
}


class PreferenceKind(StrEnum):
    PREFER_GATE = "prefer_gate"
    AVOID_GATE = "avoid_gate"
    PREFER_RUNWAY = "prefer_runway"
    AVOID_RUNWAY = "avoid_runway"
    PREFER_ACTION = "prefer_action"
    AVOID_ACTION = "avoid_action"
    PREFER_EARLIER = "prefer_earlier"
    PREFER_LATER = "prefer_later"
    NO_PREFERENCE = "no_preference"  # the note has no bearing on any package
    AMBIGUOUS = "ambiguous"  # the note cannot be read as one direction


class Note(FrozenModel):
    """Prompt-safe. The text is untrusted data, whatever it says."""

    note_id: str
    domain: Domain
    topic: str
    provenance: Provenance = Provenance.SYNTHETIC
    text: str


class HiddenPreference(FrozenModel):
    """The structure a note was written from. Never shown to an agent."""

    note_id: str
    domain: Domain
    kind: PreferenceKind
    target: str | None
    relevance: Literal["affects_ranking", "irrelevant", "ambiguous"]
    firm: bool = False  # an avoid note worded to rule its target out entirely


# Candidate preferences per domain: which package attribute each may talk about.
_KINDS_BY_DOMAIN: dict[Domain, tuple[PreferenceKind, ...]] = {
    Domain.PILOT: (
        PreferenceKind.AVOID_ACTION,
        PreferenceKind.PREFER_ACTION,
        PreferenceKind.PREFER_EARLIER,
    ),
    Domain.GROUND: (
        PreferenceKind.PREFER_GATE,
        PreferenceKind.AVOID_GATE,
        PreferenceKind.PREFER_LATER,
    ),
    Domain.ATC: (
        PreferenceKind.PREFER_RUNWAY,
        PreferenceKind.AVOID_RUNWAY,
        PreferenceKind.PREFER_LATER,
        PreferenceKind.PREFER_EARLIER,
    ),
}

_ACTION_WORDS = {
    FlightPlanAction.DIRECT: "going direct",
    FlightPlanAction.HOLD: "a hold",
    FlightPlanAction.VECTOR: "vectors",
    FlightPlanAction.GROUND_DELAY: "a ground delay",
}

_TEMPLATES: dict[PreferenceKind, tuple[str, ...]] = {
    PreferenceKind.AVOID_ACTION: (
        "Captain says the crew would really rather not take {target} on this one.",
        "Crew feedback from the last sector: {target} is the option they like least.",
        "FO asked if we can stay away from {target} today, the crew is worn out.",
    ),
    PreferenceKind.PREFER_ACTION: (
        "If there is a choice, the crew would go for {target}.",
        "Captain's preference on delay handling is {target}, all else being equal.",
        "Crew chat suggests {target} suits them best on this arrival.",
    ),
    PreferenceKind.PREFER_EARLIER: (
        "Crew are near the end of a long pairing and want on the ground sooner.",
        "Captain would take the earliest landing on offer, the crew is tired.",
        "Conditions are expected to worsen, so sooner beats later on this arrival.",
    ),
    PreferenceKind.PREFER_LATER: (
        "Things should ease off in a while, so a later arrival would go smoother.",
        "Better to bring this one in later on if we can, the next while looks busy.",
        "Leaning towards a later slot, the picture should improve as time goes on.",
    ),
    PreferenceKind.PREFER_GATE: (
        "Ramp lead would like this aircraft on gate {target} if possible.",
        "Bags and fuelling are already staged near gate {target}, so that is easiest.",
        "Gate {target} would make the ramp's life much easier today.",
    ),
    PreferenceKind.AVOID_GATE: (
        "Ramp asks to keep off gate {target}, the ground power unit there is flaky.",
        "Gate {target} has a slow jet bridge today, the team would rather not use it.",
        "Short-staffed around gate {target}, please steer away from it if you can.",
    ),
    PreferenceKind.PREFER_RUNWAY: (
        "Wind trend favours runway {target} for this arrival.",
        "Latest met briefing suggests runway {target} is the better bet.",
        "Spotter reports the smoothest approaches are onto runway {target}.",
    ),
    PreferenceKind.AVOID_RUNWAY: (
        "Crosswind building on runway {target}, would rather not use it.",
        "Reports of light turbulence on final for runway {target}, prefer another.",
        "Standing water reported near runway {target}, best avoided where possible.",
    ),
    PreferenceKind.NO_PREFERENCE: (
        "Reminder that the staff canteen closes early this weekend.",
        "Annual recurrent paperwork is due by the end of the month.",
        "New coffee machine in the briefing room is finally working.",
    ),
    PreferenceKind.AMBIGUOUS: (
        "Someone mentioned {target} earlier, not sure if that was good or bad.",
        "There was a comment about {target} at handover, could go either way.",
        "Heard {target} might matter today, nobody could say in which direction.",
    ),
}


_FIRM_TEMPLATES: dict[PreferenceKind, tuple[str, ...]] = {
    PreferenceKind.AVOID_ACTION: (
        "Captain has ruled out {target} on this arrival, the crew will not accept it.",
        "Crew have refused {target} today, take it off the table.",
        "Under no circumstances {target} for this crew, the captain was explicit.",
    ),
    PreferenceKind.AVOID_GATE: (
        "Gate {target} is out of action for this turn, do not plan onto it.",
        "Jet bridge at gate {target} has failed, it cannot be used for this arrival.",
        "Ramp cannot work gate {target} today, rule it out.",
    ),
    PreferenceKind.AVOID_RUNWAY: (
        "Do not plan this arrival onto runway {target}, braking action is poor.",
        "Runway {target} is unusable for this flow, rule it out.",
        "Met and flow agree runway {target} is off the table for this arrival.",
    ),
}


def _legal_packages(scenario: Scenario) -> tuple[Package, ...]:
    try:
        packages = enumerate_packages(scenario)
    except PackageBoundError:
        return ()
    return tuple(p for p in packages if not check_package(scenario, p))


def _candidates(
    domain: Domain, legal: tuple[Package, ...]
) -> list[tuple[PreferenceKind, str | None]]:
    """Preferences that truly separate this legal set, in stable order."""
    gates = sorted({p.gate_id for p in legal})
    runways = sorted({p.slot.runway_id for p in legal})
    actions = sorted({p.action for p in legal}, key=list(FlightPlanAction).index)
    has_times = len({p.slot.time_min for p in legal}) > 1

    found: list[tuple[PreferenceKind, str | None]] = []
    for kind in _KINDS_BY_DOMAIN[domain]:
        match kind:
            case PreferenceKind.PREFER_GATE | PreferenceKind.AVOID_GATE:
                if len(gates) > 1:
                    found.extend((kind, gate) for gate in gates)
            case PreferenceKind.PREFER_RUNWAY | PreferenceKind.AVOID_RUNWAY:
                if len(runways) > 1:
                    found.extend((kind, runway) for runway in runways)
            case PreferenceKind.PREFER_ACTION | PreferenceKind.AVOID_ACTION:
                if len(actions) > 1:
                    found.extend((kind, action.value) for action in actions)
            case PreferenceKind.PREFER_EARLIER | PreferenceKind.PREFER_LATER:
                if has_times:
                    found.append((kind, None))
            case _:
                pass
    return found


def preference_score(preference: HiddenPreference, package: Package) -> int:
    """How one package fares under a preference. Higher is better.

    Lets an evaluation check a ranking against the answer key. Irrelevant and
    ambiguous preferences score every package the same.
    """
    target = preference.target
    match preference.kind:
        case PreferenceKind.PREFER_GATE:
            return 1 if package.gate_id == target else 0
        case PreferenceKind.AVOID_GATE:
            return 0 if package.gate_id == target else 1
        case PreferenceKind.PREFER_RUNWAY:
            return 1 if package.slot.runway_id == target else 0
        case PreferenceKind.AVOID_RUNWAY:
            return 0 if package.slot.runway_id == target else 1
        case PreferenceKind.PREFER_ACTION:
            return 1 if package.action.value == target else 0
        case PreferenceKind.AVOID_ACTION:
            return 0 if package.action.value == target else 1
        case PreferenceKind.PREFER_EARLIER:
            return -package.slot.time_min
        case PreferenceKind.PREFER_LATER:
            return package.slot.time_min
        case PreferenceKind.NO_PREFERENCE | PreferenceKind.AMBIGUOUS:
            return 0


def rules_out(preference: HiddenPreference, package: Package) -> bool:
    """Whether a firm note excludes this package. Lets an evaluation score sets."""
    return preference.firm and preference_score(preference, package) == 0


def _word_for(kind: PreferenceKind, target: str | None) -> str:
    if target is None:
        return ""
    if kind in (PreferenceKind.PREFER_ACTION, PreferenceKind.AVOID_ACTION):
        return _ACTION_WORDS[FlightPlanAction(target)]
    return target


def _ambiguous_target(domain: Domain, legal: tuple[Package, ...]) -> str:
    """A subject for a vague note, public and generic if nothing else exists."""
    if legal and domain is Domain.GROUND:
        return f"gate {min(p.gate_id for p in legal)}"
    if legal and domain is Domain.ATC:
        return f"runway {min(p.slot.runway_id for p in legal)}"
    return "the arrival timing"


def _generate(
    scenario: Scenario, seed: int
) -> tuple[tuple[Note, ...], tuple[HiddenPreference, ...]]:
    scenario_id = scenario.scenario_id.value or "unknown"
    # A string seed is hashed stably by `random`, unlike `hash()`.
    rng = random.Random(f"{scenario_id}:{seed}")
    legal = _legal_packages(scenario)

    # Across the three domains the second note covers both quiet categories.
    domains = list(Domain)
    quiet: list[PreferenceKind] = [
        PreferenceKind.NO_PREFERENCE,
        PreferenceKind.AMBIGUOUS,
        rng.choice([PreferenceKind.NO_PREFERENCE, PreferenceKind.AMBIGUOUS]),
    ]
    rng.shuffle(quiet)

    notes: list[Note] = []
    truths: list[HiddenPreference] = []
    for domain, quiet_kind in zip(domains, quiet, strict=True):
        topic = TOPIC_BY_DOMAIN[domain]
        candidates = _candidates(domain, legal)
        drawn: list[tuple[PreferenceKind, str | None, str]] = []
        if candidates:
            kind, target = rng.choice(candidates)
            drawn.append((kind, target, _word_for(kind, target)))
        else:
            # Nothing separates legal packages, so no note can honestly matter.
            drawn.append((PreferenceKind.NO_PREFERENCE, None, ""))
        if quiet_kind is PreferenceKind.AMBIGUOUS:
            subject = _ambiguous_target(domain, legal)
            drawn.append((PreferenceKind.AMBIGUOUS, None, subject))
        else:
            drawn.append((PreferenceKind.NO_PREFERENCE, None, ""))

        for index, (kind, target, word) in enumerate(drawn, start=1):
            note_id = f"{topic}-{index}"
            firm = kind in _FIRM_TEMPLATES and rng.random() < 0.5
            templates = _FIRM_TEMPLATES[kind] if firm else _TEMPLATES[kind]
            text = rng.choice(templates).format(target=word)
            notes.append(Note(note_id=note_id, domain=domain, topic=topic, text=text))
            truths.append(
                HiddenPreference(
                    note_id=note_id,
                    domain=domain,
                    kind=kind,
                    target=target,
                    relevance=_relevance(kind),
                    firm=firm,
                )
            )
    return tuple(notes), tuple(truths)


def _relevance(
    kind: PreferenceKind,
) -> Literal["affects_ranking", "irrelevant", "ambiguous"]:
    if kind is PreferenceKind.NO_PREFERENCE:
        return "irrelevant"
    if kind is PreferenceKind.AMBIGUOUS:
        return "ambiguous"
    return "affects_ranking"


def notes_for(scenario: Scenario, seed: int) -> tuple[Note, ...]:
    """The synthetic notes for a scenario. Same inputs, same notes."""
    return _generate(scenario, seed)[0]


def ground_truth_preferences(
    scenario: Scenario, seed: int
) -> tuple[HiddenPreference, ...]:
    """The answer key for `notes_for`, in the same order. Never put in a prompt."""
    return _generate(scenario, seed)[1]
