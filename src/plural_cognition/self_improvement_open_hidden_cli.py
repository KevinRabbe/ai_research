"""Open SI-V1 hidden and shift targets for an already-frozen finalist set."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import read_canonical_json, write_canonical_json
from .self_improvement import ExperimentSplit, open_hidden_phase
from .self_improvement.io import (
    finalist_manifest_from_payload,
    read_candidate_pool,
    read_experiment_manifest,
    read_search_phase,
)
from .self_improvement_cli_common import (
    iter_examples,
    read_shard_bindings,
    shard_manifest_sha256s,
    verify_shard_contents,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate only the frozen SI finalists on hidden and shift targets."
        )
    )
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--search-phase", type=Path, required=True)
    parser.add_argument("--finalists", type=Path, required=True)
    parser.add_argument("--hidden-pool", type=Path, required=True)
    parser.add_argument("--shift-pool", type=Path, required=True)
    parser.add_argument(
        "--hidden-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument(
        "--shift-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _validate_bound_split(experiment, split, bindings) -> None:
    expected = experiment.split(split).task_shard_manifest_sha256s
    actual = shard_manifest_sha256s(bindings)
    if actual != expected:
        raise ValueError(
            f"{split.value} shard bindings differ from the frozen experiment"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        experiment = read_experiment_manifest(args.experiment)
        search_phase = read_search_phase(args.search_phase)
        finalist_file = finalist_manifest_from_payload(
            read_canonical_json(args.finalists)
        )
        if finalist_file.sha256 != search_phase.finalist_manifest.sha256:
            raise ValueError(
                "physical finalist file differs from the frozen search phase"
            )
        hidden_pool = read_candidate_pool(args.hidden_pool)
        shift_pool = read_candidate_pool(args.shift_pool)
        hidden_bindings = read_shard_bindings(args.hidden_shard)
        shift_bindings = read_shard_bindings(args.shift_shard)
        _validate_bound_split(
            experiment,
            ExperimentSplit.HIDDEN,
            hidden_bindings,
        )
        _validate_bound_split(
            experiment,
            ExperimentSplit.SHIFT,
            shift_bindings,
        )
        verify_shard_contents(hidden_bindings)
        verify_shard_contents(shift_bindings)
        report = open_hidden_phase(
            experiment,
            search_phase,
            hidden_pool=hidden_pool,
            hidden_examples=tuple(iter_examples(hidden_bindings)),
            shift_pool=shift_pool,
            shift_examples=tuple(iter_examples(shift_bindings)),
        )
        write_canonical_json(args.output, report.canonical_payload())
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    primary = report.comparison(
        next(
            item.role
            for item in report.evaluations
            if item.role.value == "archive-champion"
        )
    )
    print(
        f"wrote {args.output} passed={report.passed_single_run_gate} "
        f"hidden_gain={primary.hidden_semantic_gain:.6f} "
        f"shift_gain={primary.shift_semantic_gain:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
