"""Freeze and authorize the exact candidate-pool v3 calibration runner.

This freeze is created after the repaired calibration pack/qualification freeze
and after the restart-safe 4 x 6 runner passed the full test suite, but before any
v3 candidate-calibration inference.  It authorizes at most one development-only
model call for each of the 24 frozen candidate/task pairs.  It does not authorize
selection inference, reruns, candidate-specific tuning, or reuse of a partial
pair.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v2_calibration_protocol import (
    INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2,
)
from .candidate_pool_v2_source_freeze import (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
)
from .local_candidate_pool_v3_calibration import (
    PAIR_COUNT_V3,
    calibration_runner_protocol_payload_v3,
    calibration_runner_protocol_sha256_v3,
    candidate_sources_v3,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3
from .repository_surgery_calibration_qualification_freeze_v3 import (
    CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3,
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    QUALIFIED_DOCKER_REPORT_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
    REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3,
    REPAIR_RECORD_CANONICAL_SHA256_V3,
    validate_calibration_qualification_freeze_v3,
)

CALIBRATION_RUNNER_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-calibration-runner-freeze-v1"
)
CALIBRATION_RUNNER_SOURCE_REVISION_V3 = (
    "0aec10cb4dc72c54dc933439c0e4e653edfcccd7"
)
CALIBRATION_RUNNER_SOURCE_GIT_BLOB_SHA1_V3 = (
    "e4e03da726ecf0ce2694c49b69a3c32896dfbaa3"
)
CALIBRATION_RUNNER_TEST_GIT_BLOB_SHA1_V3 = (
    "189b1b91fc25e662fa6ce7bc0cc37508b0f2e30b"
)
EXPECTED_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3 = (
    "2e3984de232ddab4b9a96f8363a331b013ce1c68f9a1b91bc651f1312ad9b600"
)
EXPECTED_CALIBRATION_RUNNER_FREEZE_SHA256_V3 = (
    "6a2b815a3d2cd6b21c77f10bcd4725c05ba34a9a4605506940d85e72c5373cf9"
)
CALIBRATION_ARTIFACT_ROOT_V3 = "artifacts/capable-collective/c3"
CALIBRATION_QUALIFICATION_ROOT_V3 = "artifacts/capable-collective/c3q-r1"

_EXPECTED_MODEL_ARTIFACTS_V3 = (
    (
        "qwen3-8b-q8",
        8_709_518_112,
        "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6",
    ),
    (
        "qwen2.5-coder-14b-q5km",
        10_508_873_152,
        "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775",
    ),
    (
        "devstral-24b-q4km",
        14_333_908_960,
        "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b",
    ),
    (
        "gpt-oss-20b-mxfp4",
        12_109_566_624,
        "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901",
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


def candidate_pool_v3_calibration_runner_freeze_payload() -> dict[str, Any]:
    return {
        "schema": CALIBRATION_RUNNER_FREEZE_SCHEMA_V3,
        "scientific_status": (
            "v3-development-calibration-runner-frozen-before-candidate-inference"
        ),
        "predecessor_qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "runner": {
            "source_revision": CALIBRATION_RUNNER_SOURCE_REVISION_V3,
            "source_git_blob_sha1": CALIBRATION_RUNNER_SOURCE_GIT_BLOB_SHA1_V3,
            "test_git_blob_sha1": CALIBRATION_RUNNER_TEST_GIT_BLOB_SHA1_V3,
            "protocol_sha256": EXPECTED_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
        },
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification": {
            "software_revision": CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3,
            "repair_record_sha256": REPAIR_RECORD_CANONICAL_SHA256_V3,
            "repaired_pack_sha256": REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
            "repaired_qualification_sha256": (
                REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3
            ),
            "qualified_docker_report_sha256": QUALIFIED_DOCKER_REPORT_SHA256_V3,
            "evidence_root": CALIBRATION_QUALIFICATION_ROOT_V3,
        },
        "source_freezes": {
            "incumbent_model_source_freeze_sha256": (
                INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2
            ),
            "challenger_source_freeze_sha256": (
                FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
            ),
        },
        "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
        "model_artifacts": [
            {
                "candidate_id": candidate_id,
                "artifact_size_bytes": size_bytes,
                "artifact_sha256": artifact_sha256,
            }
            for candidate_id, size_bytes, artifact_sha256 in _EXPECTED_MODEL_ARTIFACTS_V3
        ],
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "authorization": {
            "pair_count": PAIR_COUNT_V3,
            "candidate_model_calls_consumed_before_freeze": 0,
            "candidate_model_calls_authorized": PAIR_COUNT_V3,
            "one_call_per_pair": True,
            "max_attempts_per_pair": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "candidate_specific_tuning": False,
            "automatic_reruns": False,
            "artifact_root": CALIBRATION_ARTIFACT_ROOT_V3,
            "first_invocation_requires_fresh_root": True,
            "selection_evidence": False,
        },
        "selection_evidence": False,
    }


def validate_candidate_pool_v3_calibration_runner_freeze() -> None:
    validate_calibration_qualification_freeze_v3()
    runner_protocol = calibration_runner_protocol_payload_v3()
    if (
        calibration_runner_protocol_sha256_v3()
        != EXPECTED_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3
    ):
        raise RuntimeError("v3 calibration runner protocol identity drifted")
    if runner_protocol["pair_count"] != PAIR_COUNT_V3 or PAIR_COUNT_V3 != 24:
        raise RuntimeError("v3 calibration runner matrix dimensions drifted")
    if tuple(runner_protocol["candidate_ids"]) != V3_DEVELOPMENT_CANDIDATE_IDS:
        raise RuntimeError("v3 calibration runner candidate identities drifted")
    if tuple(runner_protocol["task_ids"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("v3 calibration runner task identities drifted")
    if LOCAL_MODEL_SOURCE_FREEZE_V2.sha256 != INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2:
        raise RuntimeError("incumbent model source freeze identity drifted")

    sources = candidate_sources_v3()
    observed_models = tuple(
        (
            candidate_id,
            int(sources[candidate_id]["artifact_size_bytes"]),
            sources[candidate_id]["artifact_sha256"],
        )
        for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS
    )
    if observed_models != _EXPECTED_MODEL_ARTIFACTS_V3:
        raise RuntimeError("v3 calibration model artifact identities drifted")

    payload = candidate_pool_v3_calibration_runner_freeze_payload()
    authorization = payload["authorization"]
    if authorization["candidate_model_calls_consumed_before_freeze"] != 0:
        raise RuntimeError("v3 calibration model calls occurred before runner freeze")
    if authorization["candidate_model_calls_authorized"] != 24:
        raise RuntimeError("v3 calibration authorization is not exactly 24 pairs")
    if authorization["max_attempts_per_pair"] != 1:
        raise RuntimeError("v3 calibration attempts-per-pair drifted")
    if authorization["automatic_reruns"]:
        raise RuntimeError("v3 calibration runner freeze must forbid automatic reruns")
    if authorization["candidate_specific_tuning"]:
        raise RuntimeError("v3 calibration runner freeze must forbid candidate tuning")
    if authorization["selection_evidence"] or payload["selection_evidence"]:
        raise RuntimeError("v3 calibration runner freeze cannot be selection evidence")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_CALIBRATION_RUNNER_FREEZE_SHA256_V3:
        raise RuntimeError("v3 calibration runner freeze identity drifted")


validate_candidate_pool_v3_calibration_runner_freeze()
