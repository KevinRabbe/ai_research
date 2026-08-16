"""Freeze and authorize the exact v3 expansion load-only runner.

This freeze is created after the three-scout source freeze and after the restart-safe
load-only runner passed the full repository test suite, but before any new expansion
model launch. It authorizes exactly one load-only attempt for each of the three frozen
scouts. It does not authorize calibration or selection work.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_expansion_source_freeze import (
    EXPANSION_SCOUT_IDS_V3,
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
    candidate_pool_v3_expansion_source_freeze_payload,
    validate_candidate_pool_v3_expansion_source_freeze,
)
from .local_candidate_pool_v3_expansion_load_qualification import (
    EXPANSION_LOAD_ARTIFACT_ROOT_V3,
    EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3,
    expansion_load_runner_protocol_payload_v3,
    expansion_load_runner_protocol_sha256_v3,
)

EXPANSION_LOAD_RUNNER_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-runner-freeze-v1"
)
EXPANSION_LOAD_RUNNER_SOURCE_REVISION_V3 = (
    "3a8a80d8fdc28d9de36f7ee248d07d952117f428"
)
EXPANSION_LOAD_RUNNER_SOURCE_GIT_BLOB_SHA1_V3 = (
    "0241f1d38dc9db2a86cfd0cbf2dd9169deceb403"
)
EXPANSION_LOAD_RUNNER_TEST_GIT_BLOB_SHA1_V3 = (
    "af1c88e272408376794444f0b45ce3f0ee650aaf"
)
EXPANSION_SOURCE_FREEZE_REVISION_V3 = (
    "dea35b4c11d8de39b978bf3a4ba5f098cfab795b"
)
EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3 = (
    "f64bb5a63dbe9e9141f44840d55b33420decaca71cc108c2842e8d43175ec763"
)
EXPANSION_MODEL_ROOT_V3 = "artifacts/capable-collective/m2"
EXPANSION_RUNTIME_ROOT_V3 = (
    "artifacts/capable-collective/inference-runtime/llama.cpp-b10361-win-cuda12.4"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_load_runner_freeze_payload() -> dict[str, Any]:
    source_freeze = candidate_pool_v3_expansion_source_freeze_payload()
    scouts = {item["candidate_id"]: item for item in source_freeze["scouts"]}
    return {
        "schema": EXPANSION_LOAD_RUNNER_FREEZE_SCHEMA_V3,
        "scientific_status": (
            "v3-expansion-load-runner-frozen-before-new-model-inference"
        ),
        "predecessor_source_freeze_sha256": (
            EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
        ),
        "source_freeze_revision": EXPANSION_SOURCE_FREEZE_REVISION_V3,
        "runner": {
            "source_revision": EXPANSION_LOAD_RUNNER_SOURCE_REVISION_V3,
            "source_git_blob_sha1": EXPANSION_LOAD_RUNNER_SOURCE_GIT_BLOB_SHA1_V3,
            "test_git_blob_sha1": EXPANSION_LOAD_RUNNER_TEST_GIT_BLOB_SHA1_V3,
            "protocol_sha256": EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3,
        },
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "model_artifacts": [
            {
                "candidate_id": candidate_id,
                "artifact_size_bytes": scouts[candidate_id]["artifact_size_bytes"],
                "artifact_sha256": scouts[candidate_id]["artifact_sha256"],
            }
            for candidate_id in EXPANSION_SCOUT_IDS_V3
        ],
        "runtime": {
            "root": EXPANSION_RUNTIME_ROOT_V3,
            "llama_cpp_build": "b10361",
            "llama_cpp_revision": "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
            "device": "CUDA0",
        },
        "model_root": EXPANSION_MODEL_ROOT_V3,
        "artifact_root": EXPANSION_LOAD_ARTIFACT_ROOT_V3,
        "authorization": {
            "candidate_model_calls_consumed_before_freeze": 0,
            "candidate_model_calls_authorized": 3,
            "exact_artifact_downloads_authorized": True,
            "one_call_per_scout": True,
            "load_only": True,
            "capability_prompt": False,
            "max_attempts_per_scout": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "raw_stdout_stderr_before_classification": True,
            "full_gpu_offload_required": True,
            "candidate_specific_runtime_tuning": False,
            "automatic_reruns": False,
            "artifact_substitution": False,
            "scout_reordering": False,
            "first_invocation_requires_fresh_root": True,
            "selection_evidence": False,
        },
        "downstream": {
            "load_outcome_freeze_required_before_calibration_runner_authoring": True,
            "calibration_runner_authoring_authorized": False,
            "calibration_inference_authorized": False,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
        },
        "selection_evidence": False,
    }


def validate_candidate_pool_v3_expansion_load_runner_freeze() -> None:
    validate_candidate_pool_v3_expansion_source_freeze()
    if (
        expansion_load_runner_protocol_sha256_v3()
        != EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3
    ):
        raise RuntimeError("v3 expansion load-runner protocol identity drifted")
    protocol = expansion_load_runner_protocol_payload_v3()
    if tuple(protocol["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion load-runner scout order drifted")
    if protocol["pair_count"] != 3:
        raise RuntimeError("v3 expansion load-runner pair count drifted")

    payload = candidate_pool_v3_expansion_load_runner_freeze_payload()
    if payload["predecessor_source_freeze_sha256"] != (
        EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
    ):
        raise RuntimeError("v3 expansion load-runner freeze predecessor drifted")
    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion load-runner freeze scout order drifted")

    authorization = payload["authorization"]
    if authorization["candidate_model_calls_consumed_before_freeze"] != 0:
        raise RuntimeError("v3 expansion model calls occurred before load-runner freeze")
    if authorization["candidate_model_calls_authorized"] != 3:
        raise RuntimeError("v3 expansion load authorization must be exactly three calls")
    if authorization["max_attempts_per_scout"] != 1:
        raise RuntimeError("v3 expansion load attempts-per-scout drifted")
    if not authorization["load_only"] or authorization["capability_prompt"]:
        raise RuntimeError("v3 expansion authorization must remain load-only")
    if authorization["automatic_reruns"]:
        raise RuntimeError("v3 expansion load automatic reruns are forbidden")
    if authorization["candidate_specific_runtime_tuning"]:
        raise RuntimeError("v3 expansion load runtime tuning is forbidden")
    if authorization["artifact_substitution"] or authorization["scout_reordering"]:
        raise RuntimeError("v3 expansion scout substitution/reordering is forbidden")
    if authorization["selection_evidence"] or payload["selection_evidence"]:
        raise RuntimeError("v3 expansion load cannot be selection evidence")

    downstream = payload["downstream"]
    if not downstream[
        "load_outcome_freeze_required_before_calibration_runner_authoring"
    ]:
        raise RuntimeError("load outcome must be frozen before calibration authoring")
    for field in (
        "calibration_runner_authoring_authorized",
        "calibration_inference_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
    ):
        if downstream[field]:
            raise RuntimeError(f"v3 expansion load freeze improperly authorizes {field}")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3:
        raise RuntimeError(
            f"v3 expansion load-runner freeze identity drifted: {digest}"
        )


FINAL_CANDIDATE_POOL_V3_EXPANSION_LOAD_RUNNER_FREEZE = (
    candidate_pool_v3_expansion_load_runner_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_LOAD_RUNNER_FREEZE_SHA256 = (
    EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3
)

validate_candidate_pool_v3_expansion_load_runner_freeze()
