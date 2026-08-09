"""Generate one target-free fixed candidate path from a frozen checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import read_execution_manifest
from .self_improvement import GenerationSource, generate_target_free_artifact
from .self_improvement.io import write_generation_artifact
from .self_improvement_cli_common import (
    SelfImprovementCommandError,
    current_git_commit,
    file_sha256,
    iter_examples,
    load_frozen_checkpoint,
    public_task_from_causal,
    read_shard_bindings,
    shard_manifest_sha256s,
    validate_generation_environment,
    verify_shard_contents,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one immutable candidate path without decoding, scoring, "
            "or serializing target mechanisms."
        )
    )
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--task-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--greedy", action="store_true")
    mode.add_argument("--sampling-seed", type=int)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify files and identities without allocating CUDA state.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.max_new_tokens < 1:
            raise ValueError("max_new_tokens must be positive")
        if not args.greedy and args.temperature <= 0.0:
            raise ValueError("temperature must be positive")
        if not args.greedy and args.top_k < 1:
            raise ValueError("top_k must be positive")
        execution = read_execution_manifest(args.execution)
        bindings = read_shard_bindings(args.task_shard)
        verify_shard_contents(bindings)
        if not args.checkpoint.is_file():
            raise SelfImprovementCommandError(
                f"checkpoint does not exist: {args.checkpoint}"
            )
        generation_commit = current_git_commit()
        if args.dry_run:
            print(
                f"verified {sum(manifest.example_count for _, manifest in bindings)} "
                f"target-free task rows on SI commit {generation_commit}"
            )
            return 0
        device = validate_generation_environment(execution, args.preflight)
        model = load_frozen_checkpoint(
            execution,
            args.checkpoint,
            device=device,
        )
        public_tasks = tuple(
            public_task_from_causal(example)
            for example in iter_examples(bindings)
        )
        source = (
            GenerationSource("greedy", "greedy", None, None, None)
            if args.greedy
            else GenerationSource(
                f"sample-{args.sampling_seed}",
                "sampled",
                args.sampling_seed,
                float(args.temperature),
                args.top_k,
            )
        )
        artifact = generate_target_free_artifact(
            model,
            public_tasks,
            device=device,
            generation_git_commit=generation_commit,
            execution_sha256=execution.sha256,
            checkpoint_sha256=file_sha256(args.checkpoint),
            task_shard_manifest_sha256s=shard_manifest_sha256s(bindings),
            source=source,
            max_new_tokens=args.max_new_tokens,
        )
        write_generation_artifact(args.output, artifact)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} source={artifact.source.source_id} "
        f"cases={len(artifact.cases)} artifact_sha256={artifact.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
