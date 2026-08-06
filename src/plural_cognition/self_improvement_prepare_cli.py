"""Freeze SI-V1 pools, budgets, parent, controls, and statistical gates."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .self_improvement import (
    PolicyMode,
    ReasoningBudget,
    ReasoningPolicyGenome,
    SearchConfig,
    build_experiment_manifest,
)
from .self_improvement.io import (
    read_candidate_pool,
    write_experiment_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the complete SI-V1 experiment before search results exist."
    )
    parser.add_argument("--discovery-pool", type=Path, required=True)
    parser.add_argument("--development-pool", type=Path, required=True)
    parser.add_argument("--hidden-pool", type=Path, required=True)
    parser.add_argument("--shift-pool", type=Path, required=True)
    parser.add_argument("--generations", type=int, default=8)
    parser.add_argument("--max-genome-evaluations", type=int, default=64)
    parser.add_argument("--archive-capacity", type=int, default=24)
    parser.add_argument("--random-seed", type=int, default=20260806)
    parser.add_argument("--max-candidate-inputs", type=int, default=8)
    parser.add_argument("--max-packet-extractions", type=int, default=8)
    parser.add_argument("--max-reasoning-operations", type=int, default=1024)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260806)
    parser.add_argument("--shuffled-label-seed", type=int, default=20260807)
    parser.add_argument("--minimum-hidden-gain", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        pools = tuple(
            read_candidate_pool(path)
            for path in (
                args.discovery_pool,
                args.development_pool,
                args.hidden_pool,
                args.shift_pool,
            )
        )
        manifest = build_experiment_manifest(
            *pools,
            search_config=SearchConfig(
                args.generations,
                args.max_genome_evaluations,
                args.archive_capacity,
                args.random_seed,
            ),
            reasoning_budget=ReasoningBudget(
                args.max_candidate_inputs,
                args.max_packet_extractions,
                args.max_reasoning_operations,
            ),
            fixed_policy=ReasoningPolicyGenome(
                PolicyMode.VERIFIED_SYNTHESIS
            ),
            bootstrap_resamples=args.bootstrap_resamples,
            bootstrap_seed=args.bootstrap_seed,
            shuffled_label_seed=args.shuffled_label_seed,
            minimum_hidden_gain=args.minimum_hidden_gain,
        )
        write_experiment_manifest(args.output, manifest)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} experiment_sha256={manifest.sha256} "
        f"sources={len(manifest.generation_source_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
