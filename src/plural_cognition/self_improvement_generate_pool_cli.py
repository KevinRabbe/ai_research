"""Generate all fixed SI candidate paths and their pool with one model load."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import read_execution_manifest
from .self_improvement import (
    GenerationSource,
    build_pool_from_generation_artifacts,
    generate_target_free_artifact,
)
from .self_improvement.io import (
    write_candidate_pool,
    write_generation_artifact,
)
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
            "Generate every frozen SI sampling path for one task split while "
            "loading the checkpoint only once."
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
    parser.add_argument(
        "--sampling-seeds",
        nargs="+",
        type=int,
        required=True,
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--pool-output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        seeds = tuple(args.sampling_seeds)
        if not seeds or len(set(seeds)) != len(seeds):
            raise ValueError("sampling seeds must be nonempty and unique")
        if tuple(sorted(seeds)) != seeds:
            raise ValueError("sampling seeds must be supplied in increasing order")
        if args.temperature <= 0.0 or args.top_k < 1:
            raise ValueError("temperature and top_k must be positive")
        if args.max_new_tokens < 1:
            raise ValueError("max_new_tokens must be positive")
        execution = read_execution_manifest(args.execution)
        bindings = read_shard_bindings(args.task_shard)
        verify_shard_contents(bindings)
        if not args.checkpoint.is_file():
            raise SelfImprovementCommandError(
                f"checkpoint does not exist: {args.checkpoint}"
            )
        generation_commit = current_git_commit()
        row_count = sum(manifest.example_count for _, manifest in bindings)
        if args.dry_run:
            print(
                f"verified {row_count} target-free rows and {len(seeds)} sampling "
                f"paths on SI commit {generation_commit}"
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
        execution_sha = execution.sha256
        checkpoint_sha = file_sha256(args.checkpoint)
        shard_hashes = shard_manifest_sha256s(bindings)
        artifacts = []
        args.artifact_dir.mkdir(parents=True, exist_ok=True)
        for seed in seeds:
            source = GenerationSource(
                f"sample-{seed}",
                "sampled",
                seed,
                float(args.temperature),
                args.top_k,
            )
            artifact = generate_target_free_artifact(
                model,
                public_tasks,
                device=device,
                generation_git_commit=generation_commit,
                execution_sha256=execution_sha,
                checkpoint_sha256=checkpoint_sha,
                task_shard_manifest_sha256s=shard_hashes,
                source=source,
                max_new_tokens=args.max_new_tokens,
            )
            artifact_path = args.artifact_dir / f"generation-{source.source_id}.json"
            write_generation_artifact(artifact_path, artifact)
            artifacts.append(artifact)
            print(
                f"wrote {artifact_path} artifact_sha256={artifact.sha256}",
                flush=True,
            )
        pool = build_pool_from_generation_artifacts(tuple(artifacts))
        write_candidate_pool(args.pool_output, pool)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.pool_output} cases={len(pool.tasks)} paths={len(pool.sources)} "
        f"pool_sha256={pool.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
