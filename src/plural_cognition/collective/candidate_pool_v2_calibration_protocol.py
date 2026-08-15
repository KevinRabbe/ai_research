"""Frozen minimal calibration gate for candidate-pool v2.

This module binds the successful challenger load observer repair, the six fixed
candidate identities, the existing six-defect calibration matrix, and the V4
whole-file candidate representation before any v2 calibration inference occurs.
Calibration is development evidence only and cannot select a population.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CALIBRATION_PROTOCOL_SCHEMA_V2 = (
    "plural-cognition-candidate-pool-v2-calibration-gate-protocol-v1"
)
EXPECTED_CALIBRATION_PROTOCOL_SHA256_V2 = (
    "58a087adda5e6a1f0d10281ebc7bc5f89434ac24d88bd18aadec9aedf787f31c"
)
QUALIFICATION_PROTOCOL_SHA256_V2 = (
    "f3886fa683aeb5ab3343dc6c388da4b58ebc63f2911be01602fa2fdc2ddaa4b6"
)
SOURCE_FREEZE_SHA256_V2 = (
    "22aa8b34a6f27cc87e651099d8194acce00ee736161d00d9866f4463322b9f2d"
)
LOAD_OBSERVER_REPAIR_REVISION_V2 = "15b55a51e3fa35e4f146009d3af18c4769cfafb1"
LOAD_OBSERVER_REPAIR_PLAN_SHA256_V2 = (
    "c4f5063d596dd8204963277b209768685817f03cbe38403bd79762bd2cb5b942"
)
LOAD_OBSERVER_REPAIR_SUITE_FILE_SHA256_V2 = (
    "5d8a0e0d0ff63944d4e94e52ee3fb33a09065e925cd31bc82242b088c8190952"
)
LOAD_OBSERVER_REPAIR_SUITE_REPORT_SHA256_V2 = (
    "7315b0faf8c912ef353376c38d1c238e53e2b0cd1900d1f406a95f25cd01faec"
)
CALIBRATION_MATRIX_SOURCE_GIT_BLOB_SHA1 = "827aa7062c029797db571288fc3042b1dc19e2ff"
V4_SOURCE_REVISION = "671e5f41c171f3e2be2a6a06f9ae7e17394e43df"
V4_SOURCE_GIT_BLOB_SHA1 = "6f9976fcea6be94f5d5dce832d6c661a3c91f5bd"

CANDIDATE_IDS_V2 = (
    "qwen3-8b-q8",
    "qwen2.5-coder-14b-q5km",
    "devstral-24b-q4km",
    "gpt-oss-20b-mxfp4",
    "phi-4-reasoning-plus-14b-q5km",
    "devstral-small-2-24b-q4km",
)
INCUMBENT_IDS_V2 = CANDIDATE_IDS_V2[:3]
CHALLENGER_IDS_V2 = CANDIDATE_IDS_V2[3:]

CALIBRATION_TASK_IDS_V2 = (
    "repository-surgery-calibration-api-contract-0001",
    "repository-surgery-calibration-boundary-0001",
    "repository-surgery-calibration-error-handling-0001",
    "repository-surgery-calibration-local-logic-0001",
    "repository-surgery-calibration-multi-file-0001",
    "repository-surgery-calibration-state-management-0001",
)

REQUIRED_PARSE_VALID_COUNT_V2 = 6
MINIMUM_SOLVED_COUNT_V2 = 4
CALIBRATION_CONTEXT_TOKENS_V2 = 4096
CALIBRATION_PREDICT_TOKENS_V2 = 2048
CALIBRATION_THREADS_V2 = 16
CALIBRATION_BATCH_THREADS_V2 = 16
CALIBRATION_BATCH_TOKENS_V2 = 2048
CALIBRATION_MICROBATCH_TOKENS_V2 = 512
CALIBRATION_LOG_VERBOSITY_V2 = 4


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_calibration_protocol_payload() -> dict[str, Any]:
    return {
        "schema": CALIBRATION_PROTOCOL_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-calibration-only-not-selection-evidence",
        "candidate_pool_v2_protocol_sha256": QUALIFICATION_PROTOCOL_SHA256_V2,
        "source_freeze_sha256": SOURCE_FREEZE_SHA256_V2,
        "load_observer_repair": {
            "software_revision": LOAD_OBSERVER_REPAIR_REVISION_V2,
            "recovery_plan_sha256": LOAD_OBSERVER_REPAIR_PLAN_SHA256_V2,
            "suite_file_sha256": LOAD_OBSERVER_REPAIR_SUITE_FILE_SHA256_V2,
            "suite_report_sha256": LOAD_OBSERVER_REPAIR_SUITE_REPORT_SHA256_V2,
            "qualified_count": 3,
            "failed_count": 0,
        },
        "candidate_ids": list(CANDIDATE_IDS_V2),
        "calibration_matrix": {
            "source_git_blob_sha1": CALIBRATION_MATRIX_SOURCE_GIT_BLOB_SHA1,
            "task_ids": list(CALIBRATION_TASK_IDS_V2),
            "task_count_per_candidate": 6,
            "task_split": "calibration-only",
        },
        "representation": {
            "v4_source_revision": V4_SOURCE_REVISION,
            "v4_source_git_blob_sha1": V4_SOURCE_GIT_BLOB_SHA1,
            "prompt_source_representation": "plain-source-v1",
            "output_contract": "raw-full-file-replacement-v1",
            "candidate_output_interpreter": "deterministic-full-file-unified-diff-v1",
            "control_line_grammar": "optional-horizontal-whitespace-control-lines-v1",
            "terminal_lf_semantics": "preserve-original-terminal-lf-v1",
            "obsolete_issue_serialization_normalization": (
                "remove-one-exact-' and return a unified diff only.'-clause-v1"
            ),
            "self_review": False,
            "candidate_output_repair": False,
            "fuzzy_matching": False,
            "max_attempts": 1,
        },
        "resource_budget": {
            "context_tokens": CALIBRATION_CONTEXT_TOKENS_V2,
            "predict_tokens": CALIBRATION_PREDICT_TOKENS_V2,
            "threads": CALIBRATION_THREADS_V2,
            "batch_threads": CALIBRATION_BATCH_THREADS_V2,
            "batch_size": CALIBRATION_BATCH_TOKENS_V2,
            "microbatch_size": CALIBRATION_MICROBATCH_TOKENS_V2,
            "flash_attention": "auto",
            "temperature": 0.0,
            "seed": 1,
            "full_gpu_offload_required": True,
        },
        "transport": {
            "conversation_mode": True,
            "single_turn": True,
            "simple_io": True,
            "output_file_capture": True,
            "escape_processing": False,
            "terminal_prompt_lf": False,
            "reasoning_eof_policy": "closed-reasoning-empty-answer-residual-lf-v2",
            "log_verbosity": CALIBRATION_LOG_VERBOSITY_V2,
        },
        "gate": {
            "required_parse_valid_count": REQUIRED_PARSE_VALID_COUNT_V2,
            "minimum_solved_count": MINIMUM_SOLVED_COUNT_V2,
            "per_candidate_prompt_tuning_after_observation": False,
            "reruns_for_failed_candidates": False,
        },
        "evidence_policy": {
            "pair_attempt_marker_before_inference": True,
            "completed_pair_reused_without_inference": True,
            "partial_pair_blocks_rerun": True,
            "raw_streams_persisted_before_classification": True,
            "selection_evidence": False,
            "selection_modules_prohibited": True,
        },
    }


FINAL_CALIBRATION_PROTOCOL_SHA256_V2 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_calibration_protocol_payload())
).hexdigest()
if FINAL_CALIBRATION_PROTOCOL_SHA256_V2 != EXPECTED_CALIBRATION_PROTOCOL_SHA256_V2:
    raise AssertionError("candidate-pool v2 calibration protocol identity drifted")
