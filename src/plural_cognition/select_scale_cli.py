"""Select the smallest qualifying V1 model from six checkpoint evaluations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from .manifest_io import read_canonical_json, write_canonical_json
from .screening_selection import ScreeningRunResult, select_screening_scale


class ScaleSelectionInputError(ValueError):
    pass


def _hex(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ScaleSelectionInputError(f"{field} must contain 64 hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ScaleSelectionInputError(f"{field} must be hexadecimal") from exc
    return value


def read_screening_result(
    model_name: str,
    initialization_seed: int,
    path: str | Path,
) -> ScreeningRunResult:
    payload = read_canonical_json(path)
    required = {
        "schema",
        "execution_sha256",
        "checkpoint_sha256",
        "validation_shard_manifest_sha256s",
        "generation",
        "case_count",
        "parse_rate",
        "exact_accuracy",
        "visible_consistency_rate",
        "mean_semantic_accuracy",
        "cases",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ScaleSelectionInputError("screening evaluation has wrong fields")
    if payload["schema"] != "plural-cognition-validation-evaluation-v1":
        raise ScaleSelectionInputError("unsupported screening evaluation schema")
    if payload["generation"] != {
        "mode": "greedy",
        "sampling_seed": None,
        "temperature": None,
        "top_k": None,
    }:
        raise ScaleSelectionInputError(
            "model-scale selection requires greedy checkpoint evaluations"
        )
    if not isinstance(payload["cases"], list) or payload["case_count"] != len(payload["cases"]):
        raise ScaleSelectionInputError("screening evaluation case count is inconsistent")
    shard_values = payload["validation_shard_manifest_sha256s"]
    if not isinstance(shard_values, list) or not shard_values:
        raise ScaleSelectionInputError("screening evaluation has no validation shard identities")
    try:
        return ScreeningRunResult(
            model_name,
            initialization_seed,
            _hex(payload["execution_sha256"], "execution_sha256"),
            _hex(payload["checkpoint_sha256"], "checkpoint_sha256"),
            tuple(_hex(value, "validation shard identity") for value in shard_values),
            payload["parse_rate"],
            payload["exact_accuracy"],
            payload["visible_consistency_rate"],
            payload["mean_semantic_accuracy"],
        )
    except (TypeError, ValueError) as exc:
        raise ScaleSelectionInputError("invalid screening evaluation metrics") from exc


def selection_payload(decision) -> dict:
    return {
        "schema": "plural-cognition-scale-selection-v1",
        "selected": decision.selected,
        "selected_model": decision.selected_model,
        "status": decision.status,
        "reasons": list(decision.reasons),
        "summaries": [
            {
                "model_name": summary.model_name,
                "seeds": list(summary.seeds),
                "mean_parse_rate": summary.mean_parse_rate,
                "minimum_parse_rate": summary.minimum_parse_rate,
                "mean_exact_accuracy": summary.mean_exact_accuracy,
                "minimum_exact_accuracy": summary.minimum_exact_accuracy,
                "maximum_exact_accuracy": summary.maximum_exact_accuracy,
                "mean_visible_consistency_rate": summary.mean_visible_consistency_rate,
                "mean_semantic_accuracy": summary.mean_semantic_accuracy,
                "qualifies": summary.qualifies,
                "reasons": list(summary.reasons),
            }
            for summary in decision.summaries
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select the smallest V1 model in the frozen capability band."
    )
    parser.add_argument(
        "--result",
        nargs=3,
        action="append",
        metavar=("MODEL", "INITIALIZATION_SEED", "EVALUATION_JSON"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-parse-rate", type=float, default=0.95)
    parser.add_argument("--minimum-exact-accuracy", type=float, default=0.20)
    parser.add_argument("--maximum-exact-accuracy", type=float, default=0.70)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        results = tuple(
            read_screening_result(model, int(seed), path)
            for model, seed, path in args.result
        )
        decision = select_screening_scale(
            results,
            minimum_parse_rate=args.minimum_parse_rate,
            minimum_exact_accuracy=args.minimum_exact_accuracy,
            maximum_exact_accuracy=args.maximum_exact_accuracy,
        )
        write_canonical_json(args.output, selection_payload(decision))
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} status={decision.status} "
        f"selected_model={decision.selected_model}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
