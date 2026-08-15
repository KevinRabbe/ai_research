"""Frozen one-shot candidate-pool v2 selection execution protocol.

This protocol is created only after the fresh selection pack and its target
qualification are frozen. It does not alter task content or candidate membership.
It binds the exact five-by-twelve selection matrix, the unchanged V4 whole-file
representation/resource envelope, deterministic population selector, and strict
pair-level one-attempt evidence policy before any fresh selection inference.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v2_calibration_protocol import (
    CALIBRATION_BATCH_THREADS_V2,
    CALIBRATION_BATCH_TOKENS_V2,
    CALIBRATION_CONTEXT_TOKENS_V2,
    CALIBRATION_LOG_VERBOSITY_V2,
    CALIBRATION_MICROBATCH_TOKENS_V2,
    CALIBRATION_PREDICT_TOKENS_V2,
    CALIBRATION_THREADS_V2,
    PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
)
from .candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from .candidate_pool_v2_qualification_protocol import (
    FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
)
from .repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_PACK_SOURCE_REVISION_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
)
from .repository_surgery_selection_pack_v2 import (
    SELECTION_TASK_COUNT_V2,
    selection_blueprints_v2,
)

SELECTION_PROTOCOL_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-protocol-v1"
EXPECTED_SELECTION_PROTOCOL_SHA256_V2 = "85cb58d4bcb8dbbc2418251197880c80df6e0f1a85b889bdaa5e41fda2ea5762"
SELECTION_PACK_V2_GIT_BLOB_SHA1 = "2891d350a9d97255897d064ade3eb2cfb5686d22"
FULL_FILE_INTERPRETER_GIT_BLOB_SHA1 = "b3e2f0ac4cb926c5cae1a8a6c359601127fe3d40"
BAKEOFF_SELECTOR_GIT_BLOB_SHA1 = "ab3a36310db21cd558f5da8641a7f304decc7d08"
SELECTION_MIN_VALID_RATE_V2 = 0.95
SELECTION_POPULATION_SIZE_V2 = 4
SELECTION_PAIR_COUNT_V2 = 60
SELECTION_TASK_IDS_V2 = tuple(item.task_id for item in selection_blueprints_v2())


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_selection_protocol_payload() -> dict[str, Any]:
    return {
        "schema": SELECTION_PROTOCOL_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-fresh-selection-evidence-one-shot",
        "candidate_pool_v2_protocol_sha256": FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
        "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_pack_source_revision": SELECTION_PACK_SOURCE_REVISION_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualification_report_sha256": SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        "predecessor_resource_budget_sha256": PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
        "source_blobs": {
            "selection_pack_v2_git_blob_sha1": SELECTION_PACK_V2_GIT_BLOB_SHA1,
            "full_file_interpreter_git_blob_sha1": FULL_FILE_INTERPRETER_GIT_BLOB_SHA1,
            "bakeoff_selector_git_blob_sha1": BAKEOFF_SELECTOR_GIT_BLOB_SHA1,
        },
        "candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
        "task_ids": list(SELECTION_TASK_IDS_V2),
        "representation": {
            "output_contract": "raw-full-file-replacement-v1",
            "candidate_output_interpreter": "deterministic-full-file-unified-diff-v1",
            "control_line_grammar": "optional-horizontal-whitespace-control-lines-v1",
            "terminal_lf_semantics": "preserve-original-terminal-lf-v1",
            "selection_prompt_serialization": "repository-surgery-selection-v2-whole-file-v1",
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
            "gpu_layers": "all",
            "device": "CUDA0",
            "fit": "off",
            "split_mode": "none",
            "main_gpu": 0,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "load_mode": "mmap",
            "offline": True,
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
            "no_display_prompt": True,
            "log_colors": False,
            "log_timestamps": False,
        },
        "selection": {
            "task_count": SELECTION_TASK_COUNT_V2,
            "pair_count": SELECTION_PAIR_COUNT_V2,
            "min_valid_rate": SELECTION_MIN_VALID_RATE_V2,
            "population_size": SELECTION_POPULATION_SIZE_V2,
            "require_strongest_member": True,
            "selector": "bakeoff.select_population-v1",
            "selection_run_count": 1,
            "threshold_lowering_after_outcome": False,
        },
        "evidence_policy": {
            "pair_attempt_marker_before_inference": True,
            "completed_pair_reused_without_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "raw_streams_persisted_before_classification": True,
            "completed_suite_reused_verbatim": True,
            "selection_evidence": True,
            "selection_pack_mutation_after_start": False,
            "candidate_specific_tuning_after_start": False,
        },
    }


FINAL_SELECTION_PROTOCOL_SHA256_V2 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_selection_protocol_payload())
).hexdigest()


def validate_selection_protocol_v2() -> None:
    if FINAL_SELECTION_PROTOCOL_SHA256_V2 != EXPECTED_SELECTION_PROTOCOL_SHA256_V2:
        raise AssertionError("candidate-pool v2 selection protocol identity drifted")
    if SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2 != FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256:
        raise AssertionError("selection protocol operational freeze drifted")
    if len(FINAL_CANDIDATE_IDS_V2) != 5:
        raise AssertionError("selection protocol candidate count drifted")
    if len(SELECTION_TASK_IDS_V2) != SELECTION_TASK_COUNT_V2 or len(SELECTION_TASK_IDS_V2) != 12:
        raise AssertionError("selection protocol task count drifted")
    if SELECTION_PAIR_COUNT_V2 != len(FINAL_CANDIDATE_IDS_V2) * len(SELECTION_TASK_IDS_V2):
        raise AssertionError("selection protocol pair count drifted")


validate_selection_protocol_v2()
