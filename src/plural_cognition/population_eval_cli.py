"""Combine fixed checkpoint evaluations into the Version 1 population analysis."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Sequence

from .boolean_world import (
    CatalogEntry,
    MechanismCatalog,
    QualificationTask,
    canonical_text,
    parse_canonical_text,
    semantic_key,
)
from .manifest_io import read_canonical_json, write_canonical_json
from .population import (
    AblationMode,
    MemberCandidate,
    QualificationDecision,
    SynthesisConfig,
    qualify_population_signal,
    run_population_task_experiment,
    summarize_population_experiment,
)
from .train_cli import _iter_examples, _read_bindings, _verify_shard_contents
from .validation import decode_supervised_causal_example


class PopulationEvaluationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FixedMemberCase:
    case_index: int
    valid: bool
    expression_text: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class FixedMemberEvaluation:
    member_id: str
    validation_shard_manifest_sha256s: tuple[str, ...]
    cases: tuple[FixedMemberCase, ...]
    execution_sha256: str
    checkpoint_sha256: str


def _hex(value: Any, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length:
        raise PopulationEvaluationError(f"{field} has the wrong length")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PopulationEvaluationError(f"{field} is not hexadecimal") from exc
    return value


def read_fixed_member_evaluation(
    member_id: str,
    path: str | Path,
) -> FixedMemberEvaluation:
    if not member_id:
        raise PopulationEvaluationError("member_id must not be empty")
    payload = read_canonical_json(path)
    expected = {
        "schema",
        "execution_sha256",
        "checkpoint_sha256",
        "validation_shard_manifest_sha256s",
        "case_count",
        "parse_rate",
        "exact_accuracy",
        "visible_consistency_rate",
        "mean_semantic_accuracy",
        "cases",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PopulationEvaluationError("member evaluation has wrong fields")
    if payload["schema"] != "plural-cognition-validation-evaluation-v1":
        raise PopulationEvaluationError("unsupported member evaluation schema")
    execution_sha = _hex(payload["execution_sha256"], 64, "execution_sha256")
    checkpoint_sha = _hex(payload["checkpoint_sha256"], 64, "checkpoint_sha256")
    shard_hashes_raw = payload["validation_shard_manifest_sha256s"]
    if not isinstance(shard_hashes_raw, list) or not shard_hashes_raw:
        raise PopulationEvaluationError("member evaluation has no validation shard identities")
    shard_hashes = tuple(
        _hex(value, 64, "validation shard manifest SHA")
        for value in shard_hashes_raw
    )
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list) or payload["case_count"] != len(raw_cases):
        raise PopulationEvaluationError("member evaluation case count is inconsistent")
    cases: list[FixedMemberCase] = []
    for expected_index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise PopulationEvaluationError("member evaluation case is not an object")
        expected_case_fields = {
            "case_index",
            "task_id",
            "valid",
            "expression",
            "generated_token_ids",
            "generation_error",
            "exact",
            "visible_consistent",
            "semantic_accuracy",
        }
        if set(raw) != expected_case_fields or raw["case_index"] != expected_index:
            raise PopulationEvaluationError("member evaluation case identity is inconsistent")
        if type(raw["valid"]) is not bool:
            raise PopulationEvaluationError("member evaluation valid flag is not Boolean")
        expression = raw["expression"]
        error = raw["generation_error"]
        if raw["valid"]:
            if not isinstance(expression, str) or error is not None:
                raise PopulationEvaluationError("valid member case has invalid expression metadata")
        else:
            if expression is not None or not isinstance(error, str):
                raise PopulationEvaluationError("invalid member case has invalid failure metadata")
        cases.append(FixedMemberCase(expected_index, raw["valid"], expression, error))
    return FixedMemberEvaluation(
        member_id,
        shard_hashes,
        tuple(cases),
        execution_sha,
        checkpoint_sha,
    )


def _qualification_from_example(example) -> QualificationTask:
    decoded = decode_supervised_causal_example(example)
    _, target_bitset = semantic_key(decoded.target, decoded.public.variable_order)
    catalog = MechanismCatalog(
        decoded.public.variable_order,
        (
            CatalogEntry(
                decoded.target,
                target_bitset,
                canonical_text(decoded.target),
            ),
        ),
    )
    return QualificationTask(
        decoded.public,
        decoded.target,
        target_bitset,
        catalog,
        (),
    )


def _task_payload(case_index: int, report) -> dict:
    ablations = []
    if report.ablations is not None:
        ablations = [
            {
                "mode": outcome.mode.value,
                "candidate_id": outcome.selected.candidate_id,
                "external_score": outcome.external_score,
                "generated_composites": outcome.generated_composites,
                "candidate_evaluations": outcome.candidate_evaluations,
            }
            for outcome in report.ablations
        ]
    contributions = []
    if report.coalition is not None:
        contributions = [
            {
                "member_id": item.member_id,
                "shapley_value": item.shapley_value,
                "leave_one_out_score_drop": item.leave_one_out_score_drop,
                "selected_semantics_changed": item.selected_semantics_changed,
                "appears_in_full_provenance": item.appears_in_full_provenance,
            }
            for item in report.coalition.contributions
        ]
    return {
        "case_index": case_index,
        "analysis_available": report.analysis_available,
        "unavailable_reason": report.unavailable_reason,
        "best_individual_semantic_accuracy": report.best_individual_semantic_accuracy,
        "full_synthesis_semantic_accuracy": None
        if report.full_synthesis_hidden is None
        else report.full_synthesis_hidden.semantic_accuracy,
        "full_synthesis_exact": report.full_synthesis_exact,
        "synthesis_gain": report.synthesis_gain,
        "novel_semantic_composition": report.novel_semantic_composition,
        "multi_source_provenance": report.multi_source_provenance,
        "source_members": list(report.full_source_members),
        "score_necessary_members": list(report.score_necessary_members),
        "strong_synthesis_event": report.strong_synthesis_event,
        "individuals": [
            {
                "member_id": item.member_id,
                "valid": item.valid,
                "error": item.error,
                "semantic_accuracy": item.semantic_accuracy,
                "exact": item.exact,
                "fragment_count": item.fragment_count,
                "packet_sha256": item.packet_sha256,
            }
            for item in report.individuals
        ],
        "ablations": ablations,
        "contributions": contributions,
        "graph_sha256": None if report.graph is None else report.graph.sha256(),
    }


def run_population_evaluation(
    examples: Sequence,
    evaluations: Sequence[FixedMemberEvaluation],
    *,
    synthesis_config: SynthesisConfig | None = None,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
) -> dict:
    if len(evaluations) != 4:
        raise PopulationEvaluationError("primary V1 population evaluation requires four members")
    if len({item.member_id for item in evaluations}) != len(evaluations):
        raise PopulationEvaluationError("population member IDs must be unique")
    case_counts = {len(item.cases) for item in evaluations}
    if len(case_counts) != 1:
        raise PopulationEvaluationError("member evaluations have different case counts")
    case_count = case_counts.pop()
    if len(examples) != case_count:
        raise PopulationEvaluationError("validation examples do not match evaluation case count")
    shard_sets = {
        item.validation_shard_manifest_sha256s for item in evaluations
    }
    if len(shard_sets) != 1:
        raise PopulationEvaluationError("members were evaluated on different validation shards")

    reports = []
    for case_index, example in enumerate(examples):
        qualification = _qualification_from_example(example)
        members = []
        for evaluation in sorted(evaluations, key=lambda item: item.member_id):
            fixed = evaluation.cases[case_index]
            if fixed.valid:
                try:
                    expression = parse_canonical_text(
                        fixed.expression_text,
                        allowed_variables=qualification.public.variable_order,
                    )
                except (TypeError, ValueError) as exc:
                    raise PopulationEvaluationError(
                        f"member {evaluation.member_id} case {case_index} has invalid canonical expression"
                    ) from exc
                members.append(MemberCandidate(evaluation.member_id, expression))
            else:
                members.append(
                    MemberCandidate(
                        evaluation.member_id,
                        None,
                        error=fixed.error or "invalid generation",
                    )
                )
        reports.append(
            run_population_task_experiment(
                qualification,
                tuple(members),
                synthesis_config=synthesis_config,
                require_all_members_valid=True,
            )
        )

    analyzable = tuple(report for report in reports if report.analysis_available)
    if analyzable:
        summary = summarize_population_experiment(
            reports,
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed,
        )
        decision = qualify_population_signal(summary)
        summary_payload = {
            "task_count": summary.task_count,
            "analyzable_task_count": summary.analyzable_task_count,
            "analysis_coverage": summary.analysis_coverage,
            "mean_best_individual_accuracy": summary.mean_best_individual_accuracy,
            "mean_synthesis_accuracy": summary.mean_synthesis_accuracy,
            "mean_synthesis_gain": summary.mean_synthesis_gain,
            "synthesis_gain_ci": {
                "lower": summary.synthesis_gain_ci.lower,
                "estimate": summary.synthesis_gain_ci.estimate,
                "upper": summary.synthesis_gain_ci.upper,
                "confidence": summary.synthesis_gain_ci.confidence,
            },
            "exact_synthesis_rate": summary.exact_synthesis_rate,
            "novel_composition_rate": summary.novel_composition_rate,
            "multi_source_rate": summary.multi_source_rate,
            "strong_synthesis_event_count": summary.strong_synthesis_event_count,
            "strong_synthesis_event_rate": summary.strong_synthesis_event_rate,
            "mean_ablation_scores": {
                mode.value: score for mode, score in summary.mean_ablation_scores
            },
        }
    else:
        decision = QualificationDecision(False, ("no analyzable population tasks",))
        summary_payload = None

    return {
        "schema": "plural-cognition-population-evaluation-v1",
        "members": [
            {
                "member_id": item.member_id,
                "execution_sha256": item.execution_sha256,
                "checkpoint_sha256": item.checkpoint_sha256,
            }
            for item in sorted(evaluations, key=lambda item: item.member_id)
        ],
        "validation_shard_manifest_sha256s": list(next(iter(shard_sets))),
        "case_count": case_count,
        "summary": summary_payload,
        "qualification": {
            "passed": decision.passed,
            "reasons": list(decision.reasons),
        },
        "tasks": [
            _task_payload(index, report) for index, report in enumerate(reports)
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine four fixed checkpoint evaluations into the V1 population test."
    )
    parser.add_argument(
        "--member",
        nargs=2,
        action="append",
        metavar=("MEMBER_ID", "EVALUATION_JSON"),
        required=True,
    )
    parser.add_argument(
        "--validation-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260806)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if len(args.member) != 4:
            raise PopulationEvaluationError("exactly four --member entries are required")
        evaluations = tuple(
            read_fixed_member_evaluation(member_id, path)
            for member_id, path in args.member
        )
        bindings = _read_bindings(args.validation_shard)
        _verify_shard_contents(bindings)
        expected_hashes = tuple(manifest.sha256 for _, manifest in bindings)
        if any(
            item.validation_shard_manifest_sha256s != expected_hashes
            for item in evaluations
        ):
            raise PopulationEvaluationError(
                "member evaluations do not match supplied validation shard manifests"
            )
        case_count = len(evaluations[0].cases)
        examples = tuple(islice(_iter_examples(bindings), case_count))
        if len(examples) != case_count:
            raise PopulationEvaluationError("validation shards contain too few cases")
        payload = run_population_evaluation(
            examples,
            evaluations,
            bootstrap_resamples=args.bootstrap_resamples,
            bootstrap_seed=args.bootstrap_seed,
        )
        write_canonical_json(args.output, payload)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} passed={payload['qualification']['passed']} "
        f"cases={payload['case_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
