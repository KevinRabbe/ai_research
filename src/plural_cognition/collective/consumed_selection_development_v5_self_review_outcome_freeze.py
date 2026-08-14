"""Content-addressed freeze of the completed V5 self-review development evidence.

This is development evidence only. The underlying V1 selection split was already
consumed and cannot support a new selection/generalization claim. The freeze binds
the immutable recovered V5 report and output manifest, the predecessor partial-root
manifests used for no-repeat recovery, the predeclared continuation rule, and the
exact targeted diagnostics that caused the continuation gate to reject.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

V5_SELF_REVIEW_OUTCOME_FREEZE_SCHEMA = (
    "plural-cognition-consumed-selection-development-v5-self-review-outcome-freeze-v1"
)
V5_ORIGINAL_SOFTWARE_REVISION = "e9fb2e9630080dfe88ad5faaf15702d5643032cd"
V5_RECOVERY_SOFTWARE_REVISION = "b2d4b3052124da46f37692e24c2fdaab164943fd"
V5_DEVELOPMENT_PROTOCOL_SHA256 = "6bba796afed7138f1a679e11cbc84b4c19512b5f86de2a70138f7e7d4f2638c1"
V4_OUTCOME_FREEZE_SHA256 = "93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a"
V5_RECOVERY_REPORT_SHA256 = "588ff8a6c619934b1ef0237ca09f1fe53bac3d971d56ca87af1cfa2e2470c5e1"
V5_RECOVERY_OUTPUT_MANIFEST_SHA256 = "aa6c150962aa606559d09e4aef13e73e4c82114af0ba5bf74ade788a0caefc7a"
V5_PARTIAL_ROOT_MANIFEST_SHA256 = "bee3bdd30334bdeba2eaeeb1c22e21e98e1e8a8302c393552a05166847a9b6d1"
V5_FAILED_RECOVERY_ROOT_MANIFEST_SHA256 = "4db80825c52d690098bdc578d48c025e4e524c7d9d39b932988562c273d80d14"
EXPECTED_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256 = (
    "738d1e633c767f09f5d11c46e71eb7e552adfe424b93b826f3834380af7af58d"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def consumed_selection_development_v5_self_review_outcome_payload() -> dict[str, Any]:
    return {
        "schema": V5_SELF_REVIEW_OUTCOME_FREEZE_SCHEMA,
        "scientific_status": "development-only-consumed-split-self-review-not-selection-evidence",
        "original_v5_software_revision": V5_ORIGINAL_SOFTWARE_REVISION,
        "recovery_software_revision": V5_RECOVERY_SOFTWARE_REVISION,
        "development_protocol_sha256": V5_DEVELOPMENT_PROTOCOL_SHA256,
        "v4_outcome_freeze_sha256": V4_OUTCOME_FREEZE_SHA256,
        "v5_recovery_report_sha256": V5_RECOVERY_REPORT_SHA256,
        "v5_recovery_output_manifest_sha256": V5_RECOVERY_OUTPUT_MANIFEST_SHA256,
        "partial_v5_root_manifest_sha256": V5_PARTIAL_ROOT_MANIFEST_SHA256,
        "failed_recovery_root_manifest_sha256": V5_FAILED_RECOVERY_ROOT_MANIFEST_SHA256,
        "partial_review_inference_calls_reused": 10,
        "new_review_inference_calls": 2,
        "total_review_inference_calls": 12,
        "result_count": 12,
        "v4_targeted_parsed_count": 11,
        "v4_targeted_solved_count": 9,
        "v5_reviewed_parsed_count": 12,
        "v5_reviewed_solved_count": 10,
        "parse_delta": 1,
        "solved_delta": 1,
        "recovered_v4_failure_count": 1,
        "regressed_v4_solve_count": 0,
        "review_outputs_changed_count": 4,
        "continuation_gate": "reject",
        "continuation_gate_rule": {
            "minimum_reviewed_parsed_count": 12,
            "minimum_reviewed_solved_count": 11,
            "minimum_recovered_v4_failure_count": 2,
            "maximum_regressed_v4_solve_count": 0,
        },
        "candidates": [
            {
                "candidate_id": "qwen3-8b-q8",
                "v4_draft_parsed_count": 3,
                "v4_draft_solved_count": 2,
                "v5_reviewed_parsed_count": 3,
                "v5_reviewed_solved_count": 3,
                "new_review_inference_calls": 0,
            },
            {
                "candidate_id": "qwen2.5-coder-14b-q5km",
                "v4_draft_parsed_count": 3,
                "v4_draft_solved_count": 3,
                "v5_reviewed_parsed_count": 3,
                "v5_reviewed_solved_count": 3,
                "new_review_inference_calls": 0,
            },
            {
                "candidate_id": "devstral-24b-q4km",
                "v4_draft_parsed_count": 3,
                "v4_draft_solved_count": 3,
                "v5_reviewed_parsed_count": 3,
                "v5_reviewed_solved_count": 3,
                "new_review_inference_calls": 0,
            },
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "v4_draft_parsed_count": 2,
                "v4_draft_solved_count": 1,
                "v5_reviewed_parsed_count": 3,
                "v5_reviewed_solved_count": 1,
                "new_review_inference_calls": 2,
            },
        ],
        "failure_or_partial_results": [
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "task_id": "repository-surgery-selection-error-handling-0002",
                "source_kind": "partial-transcript-reused-no-inference",
                "draft_parse_valid": True,
                "draft_solved": False,
                "reviewed_parse_valid": True,
                "reviewed_solved": False,
                "output_changed_from_draft": True,
                "exact_accuracy_milli": 500,
                "evaluator_valid_rate_milli": 1000,
                "patch_sha256": "7567ca345671cf3d198466fe5fddde5d86e3711d4867e6fab819e263a2c63f4d",
                "evaluation_sha256": "5a80af027e19c596e5a8b149366f79c1579aa8db025fd232053b042345ef6006",
                "parse_error": None,
            },
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "task_id": "repository-surgery-selection-multi-file-0001",
                "source_kind": "missing-review-inference",
                "draft_parse_valid": False,
                "draft_solved": False,
                "reviewed_parse_valid": True,
                "reviewed_solved": False,
                "output_changed_from_draft": True,
                "exact_accuracy_milli": 500,
                "evaluator_valid_rate_milli": 1000,
                "patch_sha256": "36b51e948083fdb7bb9cfeda67231e7059ed5f9b0d06ac0d10a678425c287374",
                "evaluation_sha256": "722c53ed13b4d032d2c7bcdc52ebae195f2742fbed5bdda619768d4c7704898f",
                "parse_error": None,
            },
        ],
        "orchestration_recovery": {
            "base_generation_reused": True,
            "original_completed_review_calls_reused": 10,
            "final_missing_review_calls_run_exactly_once": 2,
            "failed_long_path_recovery_new_inference_calls": 0,
            "failed_short_path_preflight_new_inference_calls": 0,
        },
    }


FINAL_CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256 = hashlib.sha256(
    _canonical_json_bytes(consumed_selection_development_v5_self_review_outcome_payload())
).hexdigest()

if (
    FINAL_CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256
    != EXPECTED_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256
):
    raise AssertionError("V5 self-review development outcome freeze identity drifted")
