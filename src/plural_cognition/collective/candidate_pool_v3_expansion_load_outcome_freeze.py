"""Freeze the completed three-scout v3 expansion load-only outcome.

The exact load-only qualification authorized by the expansion load-runner freeze
completed once on the target machine. All three frozen scouts produced terminal PASS
reports with full GPU offload. This module records that immutable development outcome
without permitting load reruns, artifact substitution, scout reordering, calibration
inference, selection work, or plural synthesis.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_expansion_load_runner_freeze import (
    EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3,
    validate_candidate_pool_v3_expansion_load_runner_freeze,
)
from .candidate_pool_v3_expansion_source_freeze import (
    EXPANSION_SCOUT_IDS_V3,
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
)
from .local_candidate_pool_v3_expansion_load_qualification import (
    EXPANSION_LOAD_ARTIFACT_ROOT_V3,
    EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3,
)

EXPANSION_LOAD_OUTCOME_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-outcome-freeze-v1"
)
EXPANSION_LOAD_OUTCOME_SCIENTIFIC_STATUS_V3 = (
    "candidate-pool-v3-expansion-load-qualified-three-scout-outcome-freeze"
)
EXPANSION_LOAD_OUTCOME_SOFTWARE_REVISION_V3 = (
    "f0a0e59e38f9045485e11ce6b00da3290cc20bbc"
)
EXPANSION_LOAD_SUITE_FILE_SHA256_V3 = (
    "aff58fd340821e34893ee103d5e27c1e583fe18333a4e08e5a7d1ffdee8b99b0"
)
EXPANSION_LOAD_SUITE_REPORT_SHA256_V3 = (
    "e6b99ab7dcb42b359204d3ae2c8b2d0a4c5ea43aaa4dfa198239b20495608966"
)
EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3 = (
    "6d239aeb17b8c29e038cdde7babdd8db91ef7caa3ecb3a7f02ace0920d6c88bd"
)

_EXPANSION_LOAD_RESULTS_V3 = (
    (
        "qwen3-14b-q5km",
        "LOCAL_MODEL_LOAD_PASS",
        "ed07b5e6c09152c1a5a3d0a329074faa699d07aa39b8cb9d9d849ef5a6098995",
        "e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31",
        10_514_569_568,
        41,
        41,
        10_914,
    ),
    (
        "ministral-3-14b-instruct-2512-q5km",
        "LOCAL_MODEL_LOAD_PASS",
        "a456a460a8fc0f62bf22f46ad6a1aa8337866c8c4cb7923db8528eab253917c1",
        "f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000",
        9_621_091_904,
        41,
        41,
        10_130,
    ),
    (
        "ministral-3-8b-instruct-2512-q5km",
        "LOCAL_MODEL_LOAD_PASS",
        "8273e88b4df5319ebd91c465808c821821ae515e9856d940d099ee847fb13215",
        "7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35",
        6_059_268_512,
        35,
        35,
        6_706,
    ),
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_load_outcome_freeze_payload() -> dict[str, Any]:
    return {
        "schema": EXPANSION_LOAD_OUTCOME_FREEZE_SCHEMA_V3,
        "scientific_status": EXPANSION_LOAD_OUTCOME_SCIENTIFIC_STATUS_V3,
        "software_revision": EXPANSION_LOAD_OUTCOME_SOFTWARE_REVISION_V3,
        "artifact_root": EXPANSION_LOAD_ARTIFACT_ROOT_V3,
        "suite_file_sha256": EXPANSION_LOAD_SUITE_FILE_SHA256_V3,
        "suite_report_sha256": EXPANSION_LOAD_SUITE_REPORT_SHA256_V3,
        "runner_protocol_sha256": EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3,
        "runner_freeze_sha256": EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3,
        "source_freeze_sha256": (
            EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
        ),
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "result_count": 3,
        "qualified_count": 3,
        "failed_count": 0,
        "new_model_launch_count": 3,
        "attempt_marker_count": 3,
        "completed_result_count": 3,
        "partial_result_count": 0,
        "results": [
            {
                "candidate_id": candidate_id,
                "status": status,
                "report_sha256": report_sha256,
                "model_file_sha256": model_file_sha256,
                "model_file_size_bytes": model_file_size_bytes,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "peak_gpu_used_mib": peak_gpu_used_mib,
            }
            for (
                candidate_id,
                status,
                report_sha256,
                model_file_sha256,
                model_file_size_bytes,
                offloaded_layers,
                total_layers,
                peak_gpu_used_mib,
            ) in _EXPANSION_LOAD_RESULTS_V3
        ],
        "load_only": True,
        "selection_evidence": False,
        "authorization": {
            "load_rerun_authorized": False,
            "artifact_substitution_authorized": False,
            "scout_reordering_authorized": False,
            "candidate_specific_runtime_tuning_authorized": False,
            "calibration_runner_authoring_authorized_after_green": True,
            "calibration_inference_authorized": False,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
        },
    }


def validate_candidate_pool_v3_expansion_load_outcome_freeze() -> None:
    validate_candidate_pool_v3_expansion_load_runner_freeze()
    payload = candidate_pool_v3_expansion_load_outcome_freeze_payload()

    if payload["software_revision"] != EXPANSION_LOAD_OUTCOME_SOFTWARE_REVISION_V3:
        raise RuntimeError("v3 expansion load outcome revision drifted")
    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion load outcome scout order drifted")
    if payload["runner_protocol_sha256"] != EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3:
        raise RuntimeError("v3 expansion load outcome runner protocol drifted")
    if payload["runner_freeze_sha256"] != EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3:
        raise RuntimeError("v3 expansion load outcome runner freeze drifted")
    if payload["source_freeze_sha256"] != EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256:
        raise RuntimeError("v3 expansion load outcome source freeze drifted")
    if payload["result_count"] != 3 or payload["qualified_count"] != 3:
        raise RuntimeError("v3 expansion load outcome must retain three qualified scouts")
    if payload["failed_count"] != 0:
        raise RuntimeError("v3 expansion load outcome failure count drifted")
    if payload["new_model_launch_count"] != 3:
        raise RuntimeError("v3 expansion load outcome launch count drifted")
    if payload["attempt_marker_count"] != 3 or payload["completed_result_count"] != 3:
        raise RuntimeError("v3 expansion load evidence completion counts drifted")
    if payload["partial_result_count"] != 0:
        raise RuntimeError("v3 expansion load outcome cannot contain partial evidence")
    if not payload["load_only"] or payload["selection_evidence"]:
        raise RuntimeError("v3 expansion load outcome evidence classification drifted")

    results = payload["results"]
    if tuple(item["candidate_id"] for item in results) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion load result ordering drifted")
    for item in results:
        if item["status"] != "LOCAL_MODEL_LOAD_PASS":
            raise RuntimeError("all frozen expansion scouts must remain load-qualified")
        if item["offloaded_layers"] != item["total_layers"]:
            raise RuntimeError("all frozen expansion scouts must retain full GPU offload")
        if item["model_file_size_bytes"] <= 0 or item["peak_gpu_used_mib"] <= 0:
            raise RuntimeError("v3 expansion load resource evidence drifted")

    authorization = payload["authorization"]
    forbidden = (
        "load_rerun_authorized",
        "artifact_substitution_authorized",
        "scout_reordering_authorized",
        "candidate_specific_runtime_tuning_authorized",
        "calibration_inference_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("v3 expansion load outcome improperly authorizes continuation")
    if not authorization["calibration_runner_authoring_authorized_after_green"]:
        raise RuntimeError("green load outcome must authorize calibration-runner authoring")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3:
        raise RuntimeError(f"v3 expansion load outcome freeze identity drifted: {digest}")


FINAL_CANDIDATE_POOL_V3_EXPANSION_LOAD_OUTCOME_FREEZE = (
    candidate_pool_v3_expansion_load_outcome_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256 = (
    EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
)

validate_candidate_pool_v3_expansion_load_outcome_freeze()
