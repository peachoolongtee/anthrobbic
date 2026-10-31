"""The headline measures, read from the evaluation output on disk.

Reads the stored measures and returns their own display text. It never computes,
rounds or reformats a number. A headline measure the results lack is returned as
`absent`, so a gap is said out loud, never filled.
"""

import json
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import ValidationError

from app.api.evaluation import DEFAULT_RESULTS_DIR, result_paths
from app.negotiation.contracts import FrozenModel
from app.negotiation.evaluate import Measure, MeasureStatus

type MeasureState = Literal["measured", "not_reached", "failed", "absent"]

RULES_ONLY: Final = "rules_only"
LIVE: Final = "live"

# (key, plain label, the exact name the evaluation writes for it)
HEADLINE: Final[tuple[tuple[str, str, str], ...]] = (
    ("plan_found", "Plan found", "Deal rate, all rows"),
    (
        "no_go_nothing_legal",
        "No-go: nothing legal",
        "NO_GO NOTHING_LEGAL rate, all rows",
    ),
    (
        "no_go_system_fault",
        "No-go: system fault",
        "NO_GO SYSTEM_FAULT rate, all rows",
    ),
    (
        "chosen_plans_breaking_a_rule",
        "Chosen plans breaking a rule",
        "Final packages breaking a rule",
    ),
    (
        "chosen_plans_harm_flagged",
        "Chosen plans the harm check flags",
        "Final packages the independent harm check calls harmful",
    ),
    (
        "first_come_first_served_breaking_a_rule",
        "First come, first served breaking a rule",
        "first_come_first_served: packages breaking a rule",
    ),
    (
        "flights_flipping_across_seeds",
        "Flights flipping between a plan and a no-go across seeds",
        "Outcome flips between deal and NO_GO across synthetic seeds",
    ),
)

_STATE: Final[dict[MeasureStatus, MeasureState]] = {
    MeasureStatus.MEASURED: "measured",
    MeasureStatus.NOT_REACHED: "not_reached",
    MeasureStatus.FAILED: "failed",
}


class HeadlineItem(FrozenModel):
    key: str
    label: str
    metric: str  # the evaluation's own name for the measure
    state: MeasureState
    # The stored display text, e.g. "3905/5000 (78.1%)". "NOT_REACHED" when not reached.
    # None only when the measure is absent.
    value: str | None
    interval_text: str | None
    n: int | None
    evidence_class: str | None
    commit: str | None
    mode: str | None
    seed: int | None
    note: str


class Headline(FrozenModel):
    # "not_yet_run": no output exists. "unreadable": output exists but is not usable.
    status: Literal["ok", "not_yet_run", "unreadable"]
    # Every headline measure once per match, in order. One `absent` item stands for
    # a measure the results lack.
    rules_only: tuple[HeadlineItem, ...]
    # Live measures, apart from the rules-only list. Empty when no live measure exists.
    live: tuple[HeadlineItem, ...]
    # Headline measures of any other class (recorded, unseen, tuned, test).
    other: tuple[HeadlineItem, ...]


def _item(key: str, label: str, metric: str, measure: Measure | None) -> HeadlineItem:
    if measure is None:
        return HeadlineItem(
            key=key,
            label=label,
            metric=metric,
            state="absent",
            value=None,
            interval_text=None,
            n=None,
            evidence_class=None,
            commit=None,
            mode=None,
            seed=None,
            note="",
        )
    return HeadlineItem(
        key=key,
        label=label,
        metric=metric,
        state=_STATE[measure.status],
        value=measure.display_value(),
        interval_text=measure.display_interval() or None,
        n=measure.n,
        evidence_class=measure.evidence_class.value,
        commit=measure.meta.commit[:12],
        mode=measure.meta.mode,
        seed=measure.meta.seed,
        note=measure.note,
    )


def _listed(
    measures: dict[tuple[str, str], list[Measure]], evidence_class: str, pad: bool
) -> tuple[HeadlineItem, ...]:
    items: list[HeadlineItem] = []
    for key, label, metric in HEADLINE:
        found = measures.get((metric, evidence_class), [])
        items.extend(_item(key, label, metric, m) for m in found)
        if not found and pad:
            items.append(_item(key, label, metric, None))
    return tuple(items)


def read_headline(results_dir: Path = DEFAULT_RESULTS_DIR) -> Headline:
    paths = result_paths(results_dir)
    if not paths:
        return Headline(status="not_yet_run", rules_only=(), live=(), other=())
    names = {metric for _, _, metric in HEADLINE}
    found: dict[tuple[str, str], list[Measure]] = {}
    try:
        for path in paths:
            report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            for panel in report["panels"]:
                for raw in panel["measures"]:
                    measure = Measure.model_validate(raw)
                    if measure.name in names:
                        key = (measure.name, measure.evidence_class.value)
                        found.setdefault(key, []).append(measure)
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        return Headline(status="unreadable", rules_only=(), live=(), other=())
    has_live = any(cls == LIVE for _, cls in found)
    other_classes = sorted({cls for _, cls in found} - {RULES_ONLY, LIVE})
    other: list[HeadlineItem] = []
    for cls in other_classes:
        other.extend(_listed(found, cls, pad=False))
    return Headline(
        status="ok",
        rules_only=_listed(found, RULES_ONLY, pad=True),
        live=_listed(found, LIVE, pad=True) if has_live else (),
        other=tuple(other),
    )
