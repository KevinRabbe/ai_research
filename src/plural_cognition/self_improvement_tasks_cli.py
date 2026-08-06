"""Build deterministic SI task shards, including the structural-shift profile."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .boolean_world.generator import GenerationConfig
from .boolean_world.qualification import EvidenceConfig
from .dataset_shard import build_dataset_shard
from .manifest_io import write_dataset_shard_manifest
from .training_data import TrainingDataConfig


STANDARD_PROFILE = GenerationConfig()
SHIFT_PROFILE = GenerationConfig(
    variable_count=6,
    min_atoms=5,
    max_atoms=6,
    max_depth=5,
    negation_probability=0.35,
    ite_probability=0.35,
    max_attempts=1024,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build one content-addressed SI task shard. The shift profile uses "
            "deeper, denser, and more conditional mechanisms."
        )
    )
    parser.add_argument("--split", choices=("validation", "test"), required=True)
    parser.add_argument("--profile", choices=("standard", "shift-v1"), required=True)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--example-count", type=int, required=True)
    parser.add_argument("--base-seed", type=int, default=20260806)
    parser.add_argument("--catalog-size", type=int, default=128)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        generation = (
            STANDARD_PROFILE if args.profile == "standard" else SHIFT_PROFILE
        )
        config = TrainingDataConfig(
            base_seed=args.base_seed,
            catalog_size=args.catalog_size,
            generation=generation,
            evidence=EvidenceConfig(),
            max_tokens=args.max_tokens,
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
        f"wrote {args.output} profile={args.profile} "
        f"examples={manifest.example_count} records_sha256={manifest.records_sha256}"
    )
    print(f"wrote {args.manifest} manifest_sha256={manifest.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
