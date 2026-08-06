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


def validation_evaluation_payload(
    evaluation: ValidationEvaluation,
    *,
    execution_sha256: str,
    checkpoint_sha256: str,
) -> dict:
    return {
        "schema": "plural-cognition-validation-evaluation-v1",
        "execution_sha256": execution_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "case_count": len(evaluation.cases),
        "parse_rate": evaluation.parse_rate,
        "exact_accuracy": evaluation.exact_accuracy,
        "visible_consistency_rate": evaluation.visible_consistency_rate,
        "mean_semantic_accuracy": evaluation.mean_semantic_accuracy,
        "cases": [
            {
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
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
        )
        write_canonical_json(
            args.output,
            validation_evaluation_payload(
                evaluation,
                execution_sha256=execution.sha256,
                checkpoint_sha256=_file_sha256(args.checkpoint),
            ),
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} exact={evaluation.exact_accuracy:.6f} "
        f"parse={evaluation.parse_rate:.6f} "
        f"semantic={evaluation.mean_semantic_accuracy:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
