"""Reads evaluation output from disk. Never computes or invents a number.

No output means `not_yet_run` with no rows. Output that cannot be read means
`unreadable` with no rows, so a broken file is never shown as a result.
"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.api.wire import Evaluation, EvaluationRow
from app.negotiation.evaluate import Measure

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[2] / "eval_results"


def _row(raw: dict[str, Any], panel: str) -> EvaluationRow:
    """One measure, displayed by the evaluation's own code, so no number is
    reformatted here."""
    measure = Measure.model_validate(raw)
    low, high = measure.ci_low, measure.ci_high
    arm: Literal["guarded", "unguarded_model"] = (
        "unguarded_model" if "unguarded" in measure.name.lower() else "guarded"
    )
    return EvaluationRow(
        arm=arm,
        metric=measure.name,
        value=measure.display_value(),
        interval=None if low is None or high is None else (low, high),
        interval_text=measure.display_interval() or None,
        n=measure.n,
        evidence_class=measure.evidence_class.value,
        panel=panel,
        note=measure.note,
        commit=measure.meta.commit[:12],
        mode=measure.meta.mode,
        seed=measure.meta.seed,
    )


def read_evaluation(results_dir: Path = DEFAULT_RESULTS_DIR) -> Evaluation:
    paths = sorted(results_dir.glob("latest_*.json")) or sorted(
        results_dir.glob("eval_*.json")
    )
    if not paths:
        return Evaluation(status="not_yet_run", rows=(), limits=())
    rows: list[EvaluationRow] = []
    limits: dict[str, None] = {}
    failures: dict[str, None] = {}
    try:
        for path in paths:
            report = json.loads(path.read_text(encoding="utf-8"))
            for panel in report["panels"]:
                title = str(panel["title"])
                rows.extend(_row(measure, title) for measure in panel["measures"])
            limits.update(dict.fromkeys(str(limit) for limit in report["limits"]))
            failures.update(dict.fromkeys(str(f) for f in report.get("failures", ())))
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        return Evaluation(status="unreadable", rows=(), limits=())
    return Evaluation(
        status="ok",
        rows=tuple(rows),
        limits=tuple(limits),
        failures=tuple(failures),
    )
