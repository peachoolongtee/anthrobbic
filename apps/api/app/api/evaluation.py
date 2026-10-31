"""Reads evaluation output from disk. Never computes or invents a number.

No output means `not_yet_run` with no rows. Output that cannot be read means
`unreadable` with no rows, so a broken file is never shown as a result.
"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.api.wire import Evaluation, EvaluationRow

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[2] / "eval_results"


def _display(measure: dict[str, Any]) -> int | float | str:
    """The measure as recorded. A status with no value stays a status."""
    value = measure.get("value")
    status = str(measure.get("status", ""))
    if value is None or status.upper() == "NOT_REACHED":
        return status or "no value"
    k, n = measure.get("k"), measure.get("n")
    if k is not None and n is not None:
        return f"{k}/{n}"
    unit = measure.get("unit") or ""
    return f"{value:g} {unit}" if unit else value


def _row(measure: dict[str, Any]) -> EvaluationRow:
    meta = measure["meta"]
    low, high = measure.get("ci_low"), measure.get("ci_high")
    name = str(measure["name"])
    arm: Literal["guarded", "unguarded_model"] = (
        "unguarded_model" if "unguarded" in name.lower() else "guarded"
    )
    return EvaluationRow(
        arm=arm,
        metric=name,
        value=_display(measure),
        interval=None if low is None or high is None else (low, high),
        n=measure.get("n"),
        evidence_class=measure["evidence_class"],
        commit=meta["commit"],
        mode=meta["mode"],
        seed=meta["seed"],
    )


def read_evaluation(results_dir: Path = DEFAULT_RESULTS_DIR) -> Evaluation:
    paths = sorted(results_dir.glob("latest_*.json")) or sorted(
        results_dir.glob("eval_*.json")
    )
    if not paths:
        return Evaluation(status="not_yet_run", rows=(), limits=())
    rows: list[EvaluationRow] = []
    limits: dict[str, None] = {}
    try:
        for path in paths:
            report = json.loads(path.read_text(encoding="utf-8"))
            for panel in report["panels"]:
                rows.extend(_row(measure) for measure in panel["measures"])
            limits.update(dict.fromkeys(str(limit) for limit in report["limits"]))
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        return Evaluation(status="unreadable", rows=(), limits=())
    return Evaluation(status="ok", rows=tuple(rows), limits=tuple(limits))
