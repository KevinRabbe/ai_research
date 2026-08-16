"""Freeze and authorize the exact sequential v3 expansion calibration runner.

This freeze is created after the three-scout load outcome and after the sequential
calibration runner passed the full repository test suite, but before any expansion
calibration inference. It authorizes only the predeclared ordered six-task batches,
with a hard stop after the first scout that passes the unchanged v3 gate.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_expansion_load_outcome_freeze import (
    EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3,
    validate_candidate_pool_v3_expansion_load_outcome_freeze,
)
from .candidate_pool_v3_expansion_source_freeze import EXPANSION_SCOUT_IDS_V3
from .local_candidate_pool_v3_expansion_calibration import (
    BASE_V3_CALIBRATION_ENGINE_GIT_BLOB_SHA1,
    EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3,
    EXPANSION_LOAD_ARTIFACT_ROOT_V3,
    EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
    expansion_calibration_runner_protocol_payload_v3,
    expansion_calibration_runner_protocol_sha256_v3,
    validate_expansion_calibration_runner_protocol_v3,
)
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3

EXPANSION_CALIBRATION_RUNNER_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-runner-freeze-v1"
)
EXPANSION_CALIBRATION_RUNNER_SOURCE_REVISION_V3 = (
    "8a6506700e5eea79afbece4b7b112215f8552b3a"
)
EXPANSION_CALIBRATION_RUNNER_SOURCE_GIT_BLOB_SHA1_V3 = (
    "9d063bcad030aa728aa670acb6b400633df6933d"
)
EXPANSION_CALIBRATION_RUNNER_TEST_GIT_BLOB_SHA1_V3 = (
    "76e9f658a356cd727c5cc237fe97b56a6d41762f"
)
EXPANSION_LOAD_OUTCOME_FREEZE_REVISION_V3 = (
    "30ff8664ff2244baa75d540a7dd37d24ed257733"
)
EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3 = (
    "8986bcc869326493483e239da153965000d9f8c65254baf67c903e9959e5da26"
)
EXPANSION_RUNTIME_ROOT_V3 = (
    "artifacts/capable-collective/inference-runtime/llama.cpp-b10361-win-cuda12.4"
)
EXPANSION_MODEL_ROOT_V3 = "artifacts/capable-collective/m2"
EXPANSION_QUALIFICATION_ROOT_V3 = "artifacts/capable-collective/c3q-r1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_calibration_runner_freeze_payload() -> dict[str, Any]:
    return {
        "schema": EXPANSION_CALIBRATION_RUNNER_FREEZE_SCHEMA_V3,
        "scientific_status": (
            "v3-expansion-calibration-runner-frozen-before-expansion-calibration-inference"
        ),
        "predecessor_load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "predecessor_load_outcome_freeze_revision": (
            EXPANSION_LOAD_OUTCOME_FREEZE_REVISION_V3
        ),
        "runner": {
            "source_revision": EXPANSION_CALIBRATION_RUNNER_SOURCE_REVISION_V3,
            "source_git_blob_sha1": (
                EXPANSION_CALIBRATION_RUNNER_SOURCE_GIT_BLOB_SHA1_V3
            ),
            "test_git_blob_sha1": (
                EXPANSION_CALIBRATION_RUNNER_TEST_GIT_BLOB_SHA1_V3
            ),
            "protocol_sha256": (
                EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3
            ),
            "base_v3_calibration_engine_git_blob_sha1": (
                BASE_V3_CALIBRATION_ENGINE_GIT_BLOB_SHA1
            ),
        },
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "gate": {
            "required_parse_valid_count": 6,
            "minimum_solved_count": 4,
        },
        "roots": {
            "runtime": EXPANSION_RUNTIME_ROOT_V3,
            "model": EXPANSION_MODEL_ROOT_V3,
            "qualification": EXPANSION_QUALIFICATION_ROOT_V3,
            "load_evidence": EXPANSION_LOAD_ARTIFACT_ROOT_V3,
            "calibration_evidence": EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3,
        },
        "authorization": {
            "candidate_model_calls_consumed_before_freeze": 0,
            "candidate_model_calls_authorized_upper_bound": 18,
            "sequential_candidate_batch_size": 6,
            "stop_after_first_gate_pass": True,
            "first_invocation_requires_fresh_calibration_root": True,
            "one_call_per_pair": True,
            "max_attempts_per_pair": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "failed_candidate_rerun_authorized": False,
            "candidate_specific_prompt_tuning": False,
            "automatic_reruns": False,
            "load_rerun_authorized": False,
            "artifact_substitution_authorized": False,
            "scout_reordering_authorized": False,
            "calibration_inference_authorized_after_green": True,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
            "selection_evidence": False,
        },
        "post_run": {
            "expansion_calibration_outcome_freeze_required_before_population_or_selection_decision": True
        },
        "selection_evidence": False,
    }


def validate_candidate_pool_v3_expansion_calibration_runner_freeze() -> None:
    validate_candidate_pool_v3_expansion_load_outcome_freeze()
    validate_expansion_calibration_runner_protocol_v3()
    if (
        expansion_calibration_runner_protocol_sha256_v3()
        != EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3
    ):
        raise RuntimeError("expansion calibration runner protocol identity drifted")

    protocol = expansion_calibration_runner_protocol_payload_v3()
    payload = candidate_pool_v3_expansion_calibration_runner_freeze_payload()

    if payload["predecessor_load_outcome_freeze_sha256"] != (
        EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
    ):
        raise RuntimeError("expansion calibration freeze predecessor drifted")
    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("expansion calibration freeze scout order drifted")
    if tuple(payload["task_ids"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("expansion calibration freeze task order drifted")
    if protocol["gate"] != payload["gate"]:
        raise RuntimeError("expansion calibration freeze gate drifted")

    authorization = payload["authorization"]
    if authorization["candidate_model_calls_consumed_before_freeze"] != 0:
        raise RuntimeError("expansion calibration calls occurred before freeze")
    if authorization["candidate_model_calls_authorized_upper_bound"] != 18:
        raise RuntimeError("expansion calibration upper-bound call authorization drifted")
    if authorization["sequential_candidate_batch_size"] != 6:
        raise RuntimeError("expansion calibration sequential batch size drifted")
    if not authorization["stop_after_first_gate_pass"]:
        raise RuntimeError("expansion calibration must stop after first gate pass")
    if authorization["max_attempts_per_pair"] != 1:
        raise RuntimeError("expansion calibration attempts-per-pair drifted")
    if not authorization["first_invocation_requires_fresh_calibration_root"]:
        raise RuntimeError("first expansion calibration root must be fresh")
    forbidden = (
        "failed_candidate_rerun_authorized",
        "candidate_specific_prompt_tuning",
        "automatic_reruns",
        "load_rerun_authorized",
        "artifact_substitution_authorized",
        "scout_reordering_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
        "selection_evidence",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("expansion calibration freeze improperly authorizes continuation")
    if not authorization["calibration_inference_authorized_after_green"]:
        raise RuntimeError("green runner freeze must authorize expansion calibration")

    if payload["selection_evidence"]:
        raise RuntimeError("expansion calibration runner freeze cannot be selection evidence")
    if not payload["post_run"][
        "expansion_calibration_outcome_freeze_required_before_population_or_selection_decision"
    ]:
        raise RuntimeError("expansion calibration outcome freeze requirement drifted")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3:
        raise RuntimeError(
            f"expansion calibration runner freeze identity drifted: {digest}"
        )


FINAL_CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_RUNNER_FREEZE = (
    candidate_pool_v3_expansion_calibration_runner_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256 = (
    EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3
)

validate_candidate_pool_v3_expansion_calibration_runner_freeze()
