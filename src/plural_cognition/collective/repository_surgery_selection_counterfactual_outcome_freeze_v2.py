"""Immutable post-selection forensic outcome for candidate-pool v2.

This is development evidence only. It does not alter the frozen v2 selection
result, authorize a rerun, lower the validity threshold, or instantiate a
population. It records what the already-consumed assistant outputs would have
looked like under a small, candidate-agnostic parser-tolerance ladder.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v2_operational_freeze import FINAL_CANDIDATE_IDS_V2
from .repository_surgery_selection_outcome_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2,
    SELECTION_REPORT_SHA256_V2,
    SELECTION_SUITE_FILE_SHA256_V2,
)

COUNTERFACTUAL_OUTCOME_FREEZE_SCHEMA_V2 = (
    "plural-cognition-candidate-pool-v2-selection-counterfactual-outcome-freeze-v1"
)
COUNTERFACTUAL_FORENSIC_SOFTWARE_REVISION_V2 = (
    "e3c51ea3541aa648c386d8a6396416d3fe5e443f"
)
COUNTERFACTUAL_REPORT_FILE_SHA256_V2 = (
    "d99473a45835af905243cb9c860a2b1218ed0fca2bc61126b4f90c51abe6b63f"
)
COUNTERFACTUAL_REPORT_SHA256_V2 = (
    "fbed493f89f2d2f442a837a0f355b48542b4c86e7f2919533825359f0e76ea13"
)
EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2 = (
    "8e03ebe5ac9e1d9c3f99e95523183bb94398bcfc75561340b4e40df03ddc5251"
)

V3_DEVELOPMENT_CANDIDATE_IDS = (
    "qwen3-8b-q8",
    "qwen2.5-coder-14b-q5km",
    "devstral-24b-q4km",
    "gpt-oss-20b-mxfp4",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


LEVEL_DIAGNOSTICS = (
    (
        "frozen-strict",
        (
            ("qwen3-8b-q8", 12, 10, True),
            ("qwen2.5-coder-14b-q5km", 11, 10, False),
            ("devstral-24b-q4km", 8, 8, False),
            ("gpt-oss-20b-mxfp4", 2, 2, False),
            ("devstral-small-2-24b-q4km", 0, 0, False),
        ),
    ),
    (
        "surface-tolerant",
        (
            ("qwen3-8b-q8", 12, 10, True),
            ("qwen2.5-coder-14b-q5km", 12, 11, True),
            ("devstral-24b-q4km", 10, 10, False),
            ("gpt-oss-20b-mxfp4", 12, 12, True),
            ("devstral-small-2-24b-q4km", 0, 0, False),
        ),
    ),
    (
        "prompt-path-tolerant",
        (
            ("qwen3-8b-q8", 12, 10, True),
            ("qwen2.5-coder-14b-q5km", 12, 11, True),
            ("devstral-24b-q4km", 12, 12, True),
            ("gpt-oss-20b-mxfp4", 12, 12, True),
            ("devstral-small-2-24b-q4km", 0, 0, False),
        ),
    ),
    (
        "bare-file-tolerant",
        (
            ("qwen3-8b-q8", 12, 10, True),
            ("qwen2.5-coder-14b-q5km", 12, 11, True),
            ("devstral-24b-q4km", 12, 12, True),
            ("gpt-oss-20b-mxfp4", 12, 12, True),
            ("devstral-small-2-24b-q4km", 12, 10, True),
        ),
    ),
)


def counterfactual_outcome_freeze_payload_v2() -> dict[str, Any]:
    return {
        "schema": COUNTERFACTUAL_OUTCOME_FREEZE_SCHEMA_V2,
        "scientific_status": "post-selection-development-forensics-only",
        "forensic_software_revision": COUNTERFACTUAL_FORENSIC_SOFTWARE_REVISION_V2,
        "frozen_v2_selection_suite_file_sha256": SELECTION_SUITE_FILE_SHA256_V2,
        "frozen_v2_selection_report_sha256": SELECTION_REPORT_SHA256_V2,
        "counterfactual_report_file_sha256": COUNTERFACTUAL_REPORT_FILE_SHA256_V2,
        "counterfactual_report_sha256": COUNTERFACTUAL_REPORT_SHA256_V2,
        "invalid_pair_count": 27,
        "recovery_level_counts": {
            "surface-tolerant": 13,
            "prompt-path-tolerant": 2,
            "bare-file-tolerant": 12,
        },
        "levels": [
            {
                "level": level,
                "diagnostics": [list(item) for item in diagnostics],
            }
            for level, diagnostics in LEVEL_DIAGNOSTICS
        ],
        "candidate_model_inference_performed": False,
        "selection_outcome_mutated": False,
        "selection_rerun": False,
        "threshold_lowered": False,
        "frozen_v2_selection_result_changed": False,
        "v3_design_decision": {
            "keep_structured_whole_file_replacement": True,
            "accept_optional_colon_after_file_keyword": True,
            "accept_blank_lines_between_file_blocks": True,
            "fix_prompt_path_example": True,
            "production_relative_prefix_rewrite": False,
            "bare_file_mode": False,
            "candidate_pool_for_v3_development": list(V3_DEVELOPMENT_CANDIDATE_IDS),
            "devstral_small_2_status": (
                "development-only-evidence-insufficient-for-bare-file-production-grammar"
            ),
        },
    }


def validate_counterfactual_outcome_freeze_v2() -> None:
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.validate_against_repository()
    if tuple(item[0] for item in LEVEL_DIAGNOSTICS[0][1]) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("counterfactual candidate order drifted")
    prompt_path = dict((item[0], item) for item in LEVEL_DIAGNOSTICS[2][1])
    eligible = tuple(
        candidate_id
        for candidate_id, valid_count, _solved_count, _flag in LEVEL_DIAGNOSTICS[2][1]
        if valid_count / 12 >= 0.95
    )
    if eligible != V3_DEVELOPMENT_CANDIDATE_IDS:
        raise RuntimeError("minimal non-bare v3 development population drifted")
    if any(prompt_path[candidate_id][1] != 12 for candidate_id in eligible):
        raise RuntimeError("v3 development population no longer has full counterfactual validity")
    if LEVEL_DIAGNOSTICS[3][1][-1][1:3] != (12, 10):
        raise RuntimeError("Devstral-Small bare-file forensic evidence drifted")
    digest = hashlib.sha256(
        _canonical_json_bytes(counterfactual_outcome_freeze_payload_v2())
    ).hexdigest()
    if digest != EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2:
        raise RuntimeError("counterfactual outcome freeze identity drifted")


validate_counterfactual_outcome_freeze_v2()
