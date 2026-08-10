"""Evaluate one execution-bound checkpoint on its frozen validation shards."""

from __future__ import annotations

import argparse
from hashlib import sha256
from itertools import islice
from pathlib import Path
from typing import Sequence

import torch

from .boolean_world.canonical import canonical_text
from .checkpoint_bundle import load_execution_checkpoint
from .manifest_io import read_execution_manifest, write_canonical_json
from .model import PluralDecoder
from .train_cli import (
    _iter_examples,
    _read_bindings,
    _validate_binding_manifests,
    _validate_environment,
    _verify_shard_contents,
)
from .training import build_optimizer
from .validation import ValidationEvaluation, evaluate_validation_examples


def _file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def generation_protocol_payload(
    *,
    sampling_seed: int | None,
    temperature: float,
    top_k: int | None,
) -> dict:
    if sampling_seed is None:
        if temperature != 1.0 or top_k is not None:
            raise ValueError("temperature and top_k require --sampling-seed")
        return {
            "mode": "greedy",
            "sampling_seed": None,
            "temperature": None,
            "top_k": None,
        }
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be positive")
    return {
        "mode": "sampled",
        "sampling_seed": sampling_seed,
        "temperature": float(temperature),
        "top_k": top_k,
    }


def validation_evaluation_payload(
    evaluation: ValidationEvaluation,
    *,
    execution_sha256: str,
    checkpoint_sha256: str,
    validation_shard_manifest_sha256s: tuple[str, ...],
    generation: dict,
) -> dict:
    if not validation_shard_manifest_sha256s:
        raise ValueError("validation evaluation requires shard manifest identities")
    if set(generation) != {"mode", "sampling_seed", "temperature", "top_k"}:
        raise ValueError("generation protocol has wrong fields")
    return {
        "schema": "plural-cognition-validation-evaluation-v1",
        "execution_sha256": execution_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "validation_shard_manifest_sha256s": list(
            validation_shard_manifest_sha256s
        ),
        "generation": generation,
        "case_count": len(evaluation.cases),
        "parse_rate": evaluation.parse_rate,
        "exact_accuracy": evaluation.exact_accuracy,
        "visible_consistency_rate": evaluation.visible_consistency_rate,
        "mean_semantic_accuracy": evaluation.mean_semantic_accuracy,
        "cases": [
            {
                "case_index": case.case_index,
                "task_id": case.task_id,
                "valid": case.generation.valid,
                "expression": None
                if case.generation.expression is None
                else canonical_text(case.generation.expression),
                "generated_token_ids": list(case.generation.generated_token_ids),
                "generation_error": case.generation.error,
                "exact": case.exact,
                "visible_consistent": case.visible_consistent,
                "semantic_accuracy": case.semantic_accuracy,
            }
            for case in evaluation.cases
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate one execution-bound checkpoint on frozen validation data."
    )
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--validation-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument(
        "--sampling-seed",
        type=int,
        help="Enable a reproducible sampled path; omit for greedy scale evaluation.",
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-k", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        generation = generation_protocol_payload(
            sampling_seed=args.sampling_seed,
            temperature=args.temperature,
            top_k=args.top_k,
        )
        execution = read_execution_manifest(args.execution)
        bindings = _read_bindings(args.validation_shard)
        _validate_binding_manifests(
            bindings,
            execution.validation_shards,
            "validation",
        )
        _verify_shard_contents(bindings)
        device = _validate_environment(execution, args.preflight)
        model = PluralDecoder(execution.run.intent.model_config).to(device)
        optimizer = build_optimizer(model, execution.run.intent.optimizer)
        scaler = (
            torch.amp.GradScaler("cuda", enabled=True)
            if execution.run.precision == "fp16"
            else None
        )
        load_execution_checkpoint(
            args.checkpoint,
            model=model,
            optimizer=optimizer,
            execution=execution,
            scaler=scaler,
            map_location=device,
        )
        iterator = _iter_examples(bindings)
        examples = tuple(
            islice(iterator, execution.run.intent.validation_examples)
        )
        if len(examples) != execution.run.intent.validation_examples:
            raise ValueError("validation shards do not contain the frozen evaluation count")
        evaluation = evaluate_validation_examples(
            model,
            examples,
            device=device,
            max_new_tokens=args.max_new_tokens,
            sampling_seed=args.sampling_seed,
            temperature=args.temperature,
            top_k=args.top_k,
        )
        write_canonical_json(
            args.output,
            validation_evaluation_payload(
                evaluation,
                execution_sha256=execution.sha256,
                checkpoint_sha256=_file_sha256(args.checkpoint),
                validation_shard_manifest_sha256s=tuple(
                    shard.sha256 for shard in execution.validation_shards
                ),
                generation=generation,
            ),
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} mode={generation['mode']} "
        f"exact={evaluation.exact_accuracy:.6f} "
        f"parse={evaluation.parse_rate:.6f} "
        f"semantic={evaluation.mean_semantic_accuracy:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
