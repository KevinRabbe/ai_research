"""Compare the different-checkpoint population with the same-checkpoint control."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .condition_comparison import (
    compare_population_payloads,
    condition_comparison_payload,
)
from .manifest_io import read_canonical_json, write_canonical_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply the paired different-weight versus same-weight V1 gate."
    )
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--same-weight-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-control-coverage", type=float, default=0.95)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260806)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        comparison = compare_population_payloads(
            read_canonical_json(args.primary),
            read_canonical_json(args.same_weight_control),
            minimum_control_coverage=args.minimum_control_coverage,
            bootstrap_resamples=args.bootstrap_resamples,
            bootstrap_seed=args.bootstrap_seed,
        )
        write_canonical_json(args.output, condition_comparison_payload(comparison))
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} passed={comparison.passed} "
        f"accuracy_advantage={comparison.paired_accuracy_advantage:.6f} "
        f"gain_advantage={comparison.paired_gain_advantage:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
