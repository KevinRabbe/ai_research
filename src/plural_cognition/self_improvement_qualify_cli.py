"""Apply the frozen strong-claim gate across independent SI-V1 runs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import read_canonical_json, write_canonical_json
from .self_improvement.io import read_experiment_manifest
from .self_improvement.reproduction import (
    qualify_reproductions,
    reproduction_run_from_payload,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify at least three independent SI hidden-opening results."
    )
    parser.add_argument(
        "--run",
        nargs=2,
        action="append",
        metavar=("EXPERIMENT_JSON", "HIDDEN_REPORT_JSON"),
        required=True,
    )
    parser.add_argument("--minimum-runs", type=int, default=3)
    parser.add_argument("--minimum-mean-gain", type=float, default=0.05)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260806)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        runs = tuple(
            reproduction_run_from_payload(
                read_experiment_manifest(experiment_path),
                read_canonical_json(report_path),
            )
            for experiment_path, report_path in args.run
        )
        qualification = qualify_reproductions(
            runs,
            minimum_runs=args.minimum_runs,
            minimum_mean_gain=args.minimum_mean_gain,
            bootstrap_resamples=args.bootstrap_resamples,
            bootstrap_seed=args.bootstrap_seed,
        )
        write_canonical_json(args.output, qualification.canonical_payload())
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} passed={qualification.passed} "
        f"runs={len(qualification.runs)} "
        f"mean_hidden_gain={qualification.mean_hidden_gain:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
