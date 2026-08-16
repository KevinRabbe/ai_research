"""Frozen candidate-pool v3 representation and development protocol.

This freeze is created after the v2 post-selection counterfactual forensics and
before any fresh v3 calibration inference. It binds the minimal structured
whole-file grammar, the four evidence-supported development candidates, the
unchanged local runtime budget, and the rule that both v3 calibration and v3
selection use new task material.
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
)
from .candidate_pool_v3_full_file import (
    CANDIDATE_OUTPUT_INTERPRETER_V3,
    CONTROL_LINE_GRAMMAR_V3,
    OUTPUT_CONTRACT_V3,
    PROMPT_SOURCE_REPRESENTATION_V3,
    TERMINAL_LF_SEMANTICS_V3,
)
from .repository_surgery_selection_counterfactual_outcome_freeze_v2 import (
    EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    validate_counterfactual_outcome_freeze_v2,
)

V3_REPRESENTATION_PROTOCOL_SCHEMA = (
    "plural-cognition-candidate-pool-v3-representation-protocol-v1"
)
V3_REPRESENTATION_SOURCE_REVISION = "b9169434ecb3db7b7995e47e5679d95da4cbe24b"
V3_REPRESENTATION_SOURCE_GIT_BLOB_SHA1 = "807c517c39c9fe176e2d3197d756e4948d4e706f"
EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256 = (
    "28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61"
)

V3_FRESH_CALIBRATION_TASK_COUNT = 6
V3_REQUIRED_PARSE_VALID_COUNT = 6
V3_MINIMUM_SOLVED_COUNT = 4
V3_FUTURE_SELECTION_TASK_COUNT = 12
V3_SELECTION_MIN_VALID_RATE = 0.95
V3_SELECTION_POPULATION_SIZE = 4

V3_DEFECT_FAMILIES = (
    "api-contract",
    "boundary",
    "error-handling",
    "local-logic",
    "multi-file-behavior",
    "state-management",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_representation_protocol_payload() -> dict[str, Any]:
    return {
        "schema": V3_REPRESENTATION_PROTOCOL_SCHEMA,
        "scientific_status": "v3-representation-development-freeze-before-fresh-calibration",
        "predecessor_counterfactual_outcome_freeze_sha256": (
            EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2
        ),
        "representation": {
            "source_revision": V3_REPRESENTATION_SOURCE_REVISION,
            "source_git_blob_sha1": V3_REPRESENTATION_SOURCE_GIT_BLOB_SHA1,
            "prompt_source_representation": PROMPT_SOURCE_REPRESENTATION_V3,
            "output_contract": OUTPUT_CONTRACT_V3,
            "candidate_output_interpreter": CANDIDATE_OUTPUT_INTERPRETER_V3,
            "control_line_grammar": CONTROL_LINE_GRAMMAR_V3,
            "terminal_lf_semantics": TERMINAL_LF_SEMANTICS_V3,
            "accept_optional_file_colon": True,
            "accept_blank_lines_between_blocks": True,
            "content_delimiters_required": True,
            "exact_solver_visible_paths_required": True,
            "relative_prefix_rewrite": False,
            "bare_file_mode": False,
            "fuzzy_matching": False,
            "candidate_output_repair": False,
            "candidate_specific_behavior": False,
            "self_review": False,
            "max_attempts": 1,
        },
        "development_candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
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
        "fresh_development_calibration": {
            "task_count_per_candidate": V3_FRESH_CALIBRATION_TASK_COUNT,
            "defect_families": list(V3_DEFECT_FAMILIES),
            "tasks_must_be_new": True,
            "v2_calibration_tasks_reused": False,
            "v2_selection_tasks_reused": False,
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
            "candidate_specific_tuning": False,
            "reruns": False,
            "selection_evidence": False,
        },
        "future_selection": {
            "fresh_untouched_task_count": V3_FUTURE_SELECTION_TASK_COUNT,
            "min_valid_rate": V3_SELECTION_MIN_VALID_RATE,
            "population_size": V3_SELECTION_POPULATION_SIZE,
            "one_selection_run": True,
            "threshold_lowering_after_outcomes": False,
            "v2_selection_tasks_reused": False,
        },
        "candidate_model_inference_performed": False,
        "selection_evidence_observed": False,
    }


def validate_v3_representation_protocol() -> None:
    validate_counterfactual_outcome_freeze_v2()
    if len(V3_DEVELOPMENT_CANDIDATE_IDS) != V3_SELECTION_POPULATION_SIZE:
        raise RuntimeError("v3 development set must contain exactly four candidates")
    if V3_FRESH_CALIBRATION_TASK_COUNT != len(V3_DEFECT_FAMILIES):
        raise RuntimeError("v3 calibration must contain one task per defect family")
    payload = candidate_pool_v3_representation_protocol_payload()
    representation = payload["representation"]
    if representation["bare_file_mode"] or representation["relative_prefix_rewrite"]:
        raise RuntimeError("v3 production representation exceeded frozen forensic boundary")
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256:
        raise RuntimeError("v3 representation protocol identity drifted")


validate_v3_representation_protocol()
