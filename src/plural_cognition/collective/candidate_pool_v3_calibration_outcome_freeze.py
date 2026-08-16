"""Freeze the completed candidate-pool v3 development calibration outcome.

The exact 24-pair calibration authorized by the v3 runner freeze completed once.
Only three of the four frozen candidates passed the predeclared calibration gate,
so the required four-member population is infeasible under this development set.
This module records that outcome without reruns, gate lowering, candidate-specific
tuning, ad-hoc replacement, selection-pack authoring, or selection inference.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_calibration_runner_freeze import (
    CALIBRATION_ARTIFACT_ROOT_V3,
    EXPECTED_CALIBRATION_RUNNER_FREEZE_SHA256_V3,
    EXPECTED_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
    validate_candidate_pool_v3_calibration_runner_freeze,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
)
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3
from .repository_surgery_calibration_qualification_freeze_v3 import (
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
)

CALIBRATION_OUTCOME_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-calibration-outcome-freeze-v1"
)
CALIBRATION_OUTCOME_SCIENTIFIC_STATUS_V3 = (
    "candidate-pool-v3-calibration-insufficient-eligible-population"
)
CALIBRATION_OUTCOME_SOFTWARE_REVISION_V3 = (
    "d8972e2ecc51f86c286169899024baea3850f33c"
)
CALIBRATION_SUITE_FILE_SHA256_V3 = (
    "b1c8b697fcf2e7ccba5f60ac51ee67067e093f81c5342b4e6fdb791e9a74424e"
)
CALIBRATION_REPORT_SHA256_V3 = (
    "b9d45942ef96d62babf048aaf9661fa6b018d9881ae526029a5fd6e1c638d668"
)
EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3 = (
    "b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56"
)

CALIBRATION_PAIR_COUNT_V3 = 24
CALIBRATION_PARSE_VALID_COUNT_V3 = 23
CALIBRATION_SOLVED_COUNT_V3 = 19
CALIBRATION_NEW_INFERENCE_ATTEMPT_COUNT_V3 = 24
CALIBRATION_MODEL_CALLS_CONSUMED_V3 = 24
CALIBRATION_REQUIRED_POPULATION_SIZE_V3 = 4

CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3 = (
    "qwen2.5-coder-14b-q5km",
    "devstral-24b-q4km",
    "gpt-oss-20b-mxfp4",
)

_CALIBRATION_SUMMARIES_V3 = (
    ("qwen3-8b-q8", 6, 5, 1, False, 9003),
    ("qwen2.5-coder-14b-q5km", 6, 6, 6, True, 11049),
    ("devstral-24b-q4km", 6, 6, 6, True, 14839),
    ("gpt-oss-20b-mxfp4", 6, 6, 6, True, 11823),
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_calibration_outcome_freeze_payload() -> dict[str, Any]:
    return {
        "schema": CALIBRATION_OUTCOME_FREEZE_SCHEMA_V3,
        "scientific_status": CALIBRATION_OUTCOME_SCIENTIFIC_STATUS_V3,
        "software_revision": CALIBRATION_OUTCOME_SOFTWARE_REVISION_V3,
        "artifact_root": CALIBRATION_ARTIFACT_ROOT_V3,
        "suite_file_sha256": CALIBRATION_SUITE_FILE_SHA256_V3,
        "report_sha256": CALIBRATION_REPORT_SHA256_V3,
        "runner_protocol_sha256": EXPECTED_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
        "runner_freeze_sha256": EXPECTED_CALIBRATION_RUNNER_FREEZE_SHA256_V3,
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "repaired_calibration_pack_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "pair_count": CALIBRATION_PAIR_COUNT_V3,
        "parse_valid_count": CALIBRATION_PARSE_VALID_COUNT_V3,
        "solved_count": CALIBRATION_SOLVED_COUNT_V3,
        "new_inference_attempt_count": CALIBRATION_NEW_INFERENCE_ATTEMPT_COUNT_V3,
        "candidate_model_calls_consumed": CALIBRATION_MODEL_CALLS_CONSUMED_V3,
        "summaries": [
            {
                "candidate_id": candidate_id,
                "task_count": task_count,
                "parse_valid_count": parse_valid_count,
                "solved_count": solved_count,
                "passed_calibration_gate": passed_calibration_gate,
                "peak_gpu_used_mib": peak_gpu_used_mib,
            }
            for (
                candidate_id,
                task_count,
                parse_valid_count,
                solved_count,
                passed_calibration_gate,
                peak_gpu_used_mib,
            ) in _CALIBRATION_SUMMARIES_V3
        ],
        "eligible_candidate_count": len(CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3),
        "eligible_candidate_ids": list(CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3),
        "required_population_size": CALIBRATION_REQUIRED_POPULATION_SIZE_V3,
        "population_feasible": False,
        "selection_evidence": False,
        "authorization": {
            "calibration_rerun_authorized": False,
            "calibration_gate_lowering_authorized": False,
            "candidate_specific_tuning_authorized": False,
            "automatic_candidate_replacement_authorized": False,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
            "new_candidate_expansion_authorized_by_this_freeze": False,
            "new_candidate_expansion_requires_new_prefreeze_source_load_qualification_protocol": True,
        },
    }


def validate_candidate_pool_v3_calibration_outcome_freeze() -> None:
    validate_candidate_pool_v3_calibration_runner_freeze()

    payload = candidate_pool_v3_calibration_outcome_freeze_payload()
    if payload["software_revision"] != CALIBRATION_OUTCOME_SOFTWARE_REVISION_V3:
        raise RuntimeError("v3 calibration outcome software revision drifted")
    if tuple(payload["candidate_ids"]) != V3_DEVELOPMENT_CANDIDATE_IDS:
        raise RuntimeError("v3 calibration outcome candidate identities drifted")
    if tuple(payload["task_ids"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("v3 calibration outcome task identities drifted")
    if payload["gate"] != {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }:
        raise RuntimeError("v3 calibration gate drifted")
    if payload["pair_count"] != 24:
        raise RuntimeError("v3 calibration pair count drifted")
    if payload["new_inference_attempt_count"] != 24:
        raise RuntimeError("v3 calibration inference-attempt count drifted")
    if payload["candidate_model_calls_consumed"] != 24:
        raise RuntimeError("all v3 calibration model calls must remain consumed")

    summaries = payload["summaries"]
    if sum(item["parse_valid_count"] for item in summaries) != 23:
        raise RuntimeError("v3 calibration parse-valid total drifted")
    if sum(item["solved_count"] for item in summaries) != 19:
        raise RuntimeError("v3 calibration solved total drifted")

    eligible = tuple(
        item["candidate_id"]
        for item in summaries
        if item["parse_valid_count"] == V3_REQUIRED_PARSE_VALID_COUNT
        and item["solved_count"] >= V3_MINIMUM_SOLVED_COUNT
    )
    if eligible != CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3:
        raise RuntimeError("v3 calibration eligible population drifted")
    if len(eligible) != 3 or len(eligible) >= CALIBRATION_REQUIRED_POPULATION_SIZE_V3:
        raise RuntimeError("v3 calibration population feasibility drifted")
    if payload["population_feasible"]:
        raise RuntimeError("v3 calibration cannot claim a four-member population")
    if payload["selection_evidence"]:
        raise RuntimeError("v3 calibration must not become selection evidence")

    authorization = payload["authorization"]
    forbidden = (
        "calibration_rerun_authorized",
        "calibration_gate_lowering_authorized",
        "candidate_specific_tuning_authorized",
        "automatic_candidate_replacement_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
        "new_candidate_expansion_authorized_by_this_freeze",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("v3 calibration outcome improperly authorizes continuation")
    if not authorization[
        "new_candidate_expansion_requires_new_prefreeze_source_load_qualification_protocol"
    ]:
        raise RuntimeError("v3 candidate expansion must require a new prefreeze protocol")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3:
        raise RuntimeError("v3 calibration outcome freeze identity drifted")


FINAL_CANDIDATE_POOL_V3_CALIBRATION_OUTCOME_FREEZE = (
    candidate_pool_v3_calibration_outcome_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_CALIBRATION_OUTCOME_FREEZE_SHA256 = (
    EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3
)

validate_candidate_pool_v3_calibration_outcome_freeze()
