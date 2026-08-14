"""Content-addressed freeze of the completed V4 consumed-selection development evidence.

This is development evidence only. The underlying V1 selection split was already
consumed and cannot support a new selection/generalization claim. The freeze binds
the immutable targeted and remainder V4 reports, their output-channel manifests,
the predeclared continuation rule, the exact combined 4x12 diagnostics, and the
three failure/partial observations that caused the continuation gate to reject.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

V4_OUTCOME_FREEZE_SCHEMA = "plural-cognition-consumed-selection-development-v4-outcome-freeze-v1"
V4_SOFTWARE_REVISION = "671e5f41c171f3e2be2a6a06f9ae7e17394e43df"
V4_DEVELOPMENT_PROTOCOL_SHA256 = "79a137d27b83ad0faa529878f440e6da142f00cc6588048316e063fa7fd0b616"
V1_SELECTION_REPORT_SHA256 = "cfb56dd84564db7de09be590c93107cf7d2c7e76f8971eabbe41a2f8926826fd"
V4_TARGETED_REPORT_SHA256 = "9d6aa926135b0392bc7d19b9dc018249d0555d581f49c5776fb0cba81268f8be"
V4_TARGETED_OUTPUT_MANIFEST_SHA256 = "42179e1598287a7b0676a2ab566281983d25b25e05f5f4b48e13115d2d94d93c"
V4_REMAINDER_REPORT_SHA256 = "bf9653f7ff9c78f88a9a759498ac76b85b3db902e6bdc2bc6f7200b493986f2f"
V4_REMAINDER_OUTPUT_MANIFEST_SHA256 = "94ef8646d67e8b7ef9a03c7c27e7dc22927a942d39ef44c56545c5d8af1a233a"
EXPECTED_V4_OUTCOME_FREEZE_SHA256 = "93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def consumed_selection_development_v4_outcome_payload() -> dict[str, Any]:
    return {
        "schema": V4_OUTCOME_FREEZE_SCHEMA,
        "scientific_status": "development-only-consumed-split-not-selection-evidence",
        "software_revision": V4_SOFTWARE_REVISION,
        "development_protocol_sha256": V4_DEVELOPMENT_PROTOCOL_SHA256,
        "v1_selection_report_sha256": V1_SELECTION_REPORT_SHA256,
        "targeted_report_sha256": V4_TARGETED_REPORT_SHA256,
        "targeted_output_manifest_sha256": V4_TARGETED_OUTPUT_MANIFEST_SHA256,
        "remainder_report_sha256": V4_REMAINDER_REPORT_SHA256,
        "remainder_output_manifest_sha256": V4_REMAINDER_OUTPUT_MANIFEST_SHA256,
        "targeted_result_count": 12,
        "remainder_result_count": 36,
        "combined_result_count": 48,
        "combined_unique_pair_count": 48,
        "combined_task_count": 12,
        "v1_parsed_count": 43,
        "v1_solved_count": 42,
        "v4_parsed_count": 47,
        "v4_solved_count": 45,
        "continuation_gate": "reject",
        "continuation_gate_rule": {
            "all_candidates_parse_valid_count": 12,
            "minimum_total_solved_count": 42,
            "per_candidate_minimum_solved_count": {
                "qwen3-8b-q8": 9,
                "qwen2.5-coder-14b-q5km": 11,
                "devstral-24b-q4km": 11,
                "deepseek-coder-v2-lite-q5km": 11,
            },
        },
        "candidates": [
            {
                "candidate_id": "qwen3-8b-q8",
                "v1_parsed_count": 9,
                "v1_solved_count": 9,
                "v4_parsed_count": 12,
                "v4_solved_count": 11,
            },
            {
                "candidate_id": "qwen2.5-coder-14b-q5km",
                "v1_parsed_count": 11,
                "v1_solved_count": 11,
                "v4_parsed_count": 12,
                "v4_solved_count": 12,
            },
            {
                "candidate_id": "devstral-24b-q4km",
                "v1_parsed_count": 11,
                "v1_solved_count": 11,
                "v4_parsed_count": 12,
                "v4_solved_count": 12,
            },
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "v1_parsed_count": 12,
                "v1_solved_count": 11,
                "v4_parsed_count": 11,
                "v4_solved_count": 10,
            },
        ],
        "failure_or_partial_results": [
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "task_id": "repository-surgery-selection-error-handling-0002",
                "parse_valid": True,
                "solved": False,
                "exact_accuracy_milli": 500,
                "evaluator_valid_rate_milli": 1000,
                "patch_sha256": "cc6cd356caa211de0f31e3c9d3e49ceaaa22c796ad9382883eb03b2be58f903a",
                "evaluation_sha256": "1844304694574ec917f6f04feb880bc5eb8c0fb7402df45472c57b07d15a84b3",
                "parse_error": None,
            },
            {
                "candidate_id": "qwen3-8b-q8",
                "task_id": "repository-surgery-selection-multi-file-0001",
                "parse_valid": True,
                "solved": False,
                "exact_accuracy_milli": 0,
                "evaluator_valid_rate_milli": 0,
                "patch_sha256": "3d684bdb7c959a45f26433b2dd49b5d7bbd6dc7276e031d497f5ec95c40b2849",
                "evaluation_sha256": "58196958c4081f73cc4a0ecf64527f6842d84ad5ba027f6f9f4d901794edb749",
                "parse_error": None,
            },
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "task_id": "repository-surgery-selection-multi-file-0001",
                "parse_valid": False,
                "solved": False,
                "exact_accuracy_milli": 0,
                "evaluator_valid_rate_milli": 0,
                "patch_sha256": None,
                "evaluation_sha256": "00ed522dfd2abc7215a08f95f5ecfa600a0204e36661b551a3d7c3cf0f6a2f27",
                "parse_error": "V4 file block leaves file unchanged: app.py",
            },
        ],
    }


FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256 = hashlib.sha256(
    _canonical_json_bytes(consumed_selection_development_v4_outcome_payload())
).hexdigest()

if FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256 != EXPECTED_V4_OUTCOME_FREEZE_SHA256:
    raise AssertionError("V4 consumed-selection development outcome freeze identity drifted")
