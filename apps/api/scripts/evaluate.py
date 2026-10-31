"""One command for the evaluation table.

    uv --directory apps/api run python scripts/evaluate.py --mode off --sample 5000

Exit codes: 0 all controls held; 1 a control failed; 2 refused by a guard, or bad
arguments; 3 the harness ran, but a requested sample could not (a parallel module
has not landed).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXIT_OK = 0
EXIT_CONTROL_FAILED = 1
EXIT_REFUSED = 2
EXIT_INCOMPLETE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the evaluation table.")
    parser.add_argument("--mode", choices=("off", "recorded", "live"), default="off")
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="rows, stratified half weather, half late-aircraft; ignored with --split",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--split", choices=("none", "tune", "frozen"), default="none")
    parser.add_argument(
        "--confirm-live-calls",
        type=int,
        default=None,
        metavar="N",
        help="required with --mode live; must cover the printed plan",
    )
    parser.add_argument(
        "--force-frozen-rescore",
        action="store_true",
        help="run past the planned frozen runs or call ceiling; recorded as forced",
    )
    parser.add_argument(
        "--regenerate-split",
        action="store_true",
        help="choose the split again; refused once a live run has used it",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max((os.cpu_count() or 2) - 1, 1),
        help="processes for the rules-only rows",
    )
    parser.add_argument("--synthetic-seeds", type=int, default=3)
    parser.add_argument(
        "--generator-rows",
        type=int,
        default=500,
        help="rows in the generator-parameter sweep; 0 turns it off",
    )
    parser.add_argument("--data", default=None, help="path to flights.csv")
    parser.add_argument("--results-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Imported late so --help works anywhere, and after the path is set.
    from app.negotiation import evaluate as ev

    if args.sample < 0 or args.synthetic_seeds < 1 or args.workers < 1:
        print("--sample must not be negative; seeds and workers must be positive")
        return EXIT_REFUSED

    request = ev.RunRequest(
        mode=args.mode,
        sample=args.sample,
        seed=args.seed,
        split=args.split,
        confirm_live_calls=args.confirm_live_calls,
        force_frozen_rescore=args.force_frozen_rescore,
        regenerate_split=args.regenerate_split,
        workers=args.workers,
        synthetic_seeds=args.synthetic_seeds,
        generator_rows=args.generator_rows,
        results_dir=args.results_dir or ev.EVAL_RESULTS_DIR,
        data_path=args.data,
    )
    backends = ev.load_backends()
    try:
        if request.mode == ev.MODE_LIVE:
            # Printed before anything is spent, whatever happens next.
            plan, _ = ev.preview_live_plan(request, backends)
            print(plan.describe(), flush=True)
        report = ev.run_evaluation(request, backends)
    except (
        ev.LiveCallsNotConfirmed,
        ev.FrozenRescoreRefused,
        ev.SplitError,
    ) as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    print(ev.render_markdown(report))
    if report.failures:
        return EXIT_CONTROL_FAILED
    wanted_rows = args.sample > 0 or args.split != "none"
    if wanted_rows and report.meta.sample_size == 0:
        return EXIT_INCOMPLETE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
