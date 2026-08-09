"""Run SI-V1 discovery/development search and freeze hidden finalists."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import write_canonical_json
from .self_improvement import ExperimentSplit, run_search_phase
from .self_improvement.io import (
    read_candidate_pool,
    read_experiment_manifest,
    write_search_phase,
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
            "Run all SI search controls using discovery/development targets only, "
            "then freeze the finalist manifest."
        )
    )
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--discovery-pool", type=Path, required=True)
    parser.add_argument("--development-pool", type=Path, required=True)
    parser.add_argument(
        "--discovery-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument(
        "--development-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--finalists-output", type=Path, required=True)
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
        discovery_pool = read_candidate_pool(args.discovery_pool)
        development_pool = read_candidate_pool(args.development_pool)
        discovery_bindings = read_shard_bindings(args.discovery_shard)
        development_bindings = read_shard_bindings(args.development_shard)
        _validate_bound_split(
            experiment,
            ExperimentSplit.DISCOVERY,
            discovery_bindings,
        )
        _validate_bound_split(
            experiment,
            ExperimentSplit.DEVELOPMENT,
            development_bindings,
        )
        verify_shard_contents(discovery_bindings)
        verify_shard_contents(development_bindings)
        phase = run_search_phase(
            experiment,
            discovery_pool=discovery_pool,
            discovery_examples=tuple(iter_examples(discovery_bindings)),
            development_pool=development_pool,
            development_examples=tuple(iter_examples(development_bindings)),
        )
        write_search_phase(args.output, phase)
        write_canonical_json(
            args.finalists_output,
            phase.finalist_manifest.canonical_payload(),
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} search_phase_sha256={phase.sha256} "
        f"evaluations={phase.archive.evaluated_genome_count}"
    )
    print(
        f"wrote {args.finalists_output} "
        f"finalist_manifest_sha256={phase.finalist_manifest.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
