"""Command-line preparation for measured screening runs and dataset shards."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .dataset_shard import build_dataset_shard
from .execution import ExecutionManifest
from .manifest_io import (
    read_dataset_shard_manifest,
    read_screening_plan,
    write_dataset_shard_manifest,
    write_execution_manifest,
    write_screening_plan,
)
from .preflight_resolution import resolve_screening_plan_from_preflight
from .training_data import TrainingDataConfig


def _resolve_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve the frozen six-run screening plan from a measured CUDA preflight."
    )
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initialization-seeds", type=int, nargs="+", default=(101, 102))
    parser.add_argument("--data-seed", type=int, default=20260806)
    return parser


def resolve_screening_plan_main(argv: Sequence[str] | None = None) -> int:
    parser = _resolve_parser()
    args = parser.parse_args(argv)
    try:
        runs = resolve_screening_plan_from_preflight(
            args.preflight,
            initialization_seeds=tuple(args.initialization_seeds),
            data_seed=args.data_seed,
        )
        write_screening_plan(args.output, runs)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"wrote {args.output} with {len(runs)} resolved runs")
    for run in runs:
        print(
            f"{run.intent.run_id} model={run.intent.model_name} "
            f"microbatch={run.microbatch_examples} accumulation={run.gradient_accumulation_steps}"
        )
    return 0


def _dataset_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one deterministic content-addressed Boolean dataset shard."
    )
    parser.add_argument("--split", choices=("train", "validation", "test"), required=True)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--example-count", type=int, required=True)
    parser.add_argument("--data-seed", type=int, default=20260806)
    parser.add_argument("--catalog-size", type=int, default=128)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


def build_dataset_shard_main(argv: Sequence[str] | None = None) -> int:
    parser = _dataset_parser()
    args = parser.parse_args(argv)
    try:
        config = TrainingDataConfig(
            base_seed=args.data_seed,
            catalog_size=args.catalog_size,
        )
        manifest = build_dataset_shard(
            args.output,
            split=args.split,
            start_index=args.start_index,
            example_count=args.example_count,
            config=config,
        )
        write_dataset_shard_manifest(args.manifest, manifest)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} ({manifest.example_count} examples, "
        f"records_sha256={manifest.records_sha256})"
    )
    print(f"wrote {args.manifest} (manifest_sha256={manifest.sha256})")
    return 0


def _execution_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bind one resolved screening run to exact dataset shard manifests."
    )
    parser.add_argument("--screening-plan", type=Path, required=True)
    parser.add_argument("--model", choices=("PC-4M", "PC-10M", "PC-18M"), required=True)
    parser.add_argument("--initialization-seed", type=int, required=True)
    parser.add_argument("--training-manifests", type=Path, nargs="+", required=True)
    parser.add_argument("--validation-manifests", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def prepare_execution_main(argv: Sequence[str] | None = None) -> int:
    parser = _execution_parser()
    args = parser.parse_args(argv)
    try:
        runs = read_screening_plan(args.screening_plan)
        matches = tuple(
            run
            for run in runs
            if run.intent.model_name == args.model
            and run.intent.initialization_seed == args.initialization_seed
        )
        if len(matches) != 1:
            raise ValueError(
                f"screening plan contains {len(matches)} matching runs; expected exactly one"
            )
        training = tuple(
            read_dataset_shard_manifest(path) for path in args.training_manifests
        )
        validation = tuple(
            read_dataset_shard_manifest(path) for path in args.validation_manifests
        )
        execution = ExecutionManifest(matches[0], training, validation)
        write_execution_manifest(args.output, execution)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"wrote {args.output}")
    print(f"execution_sha256={execution.sha256}")
    print(
        f"steps={execution.optimizer_steps} "
        f"effective_tokens={execution.effective_training_tokens} "
        f"training_examples={execution.required_training_examples}"
    )
    return 0


if __name__ == "__main__":
    sys.stderr.write(
        "Use an installed plural-cognition preparation command rather than invoking this module directly.\n"
    )
    raise SystemExit(2)
