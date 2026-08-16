"""Freeze the successfully repaired candidate-pool v3 calibration qualification.

This record is created after deterministic Docker baseline/gold qualification and
before any candidate inference on the fresh v3 development-calibration tasks. It
binds the repaired pack, repair record, qualification report, Docker identity,
failed-evidence preservation proof, task diagnostics, and future 4 x 6 gate.

This freeze does not itself authorize candidate-model calls.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_FRESH_CALIBRATION_TASK_COUNT,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
    validate_v3_representation_protocol,
)
from .qualified_docker import QUALIFIED_DOCKER
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3
from .repository_surgery_calibration_pack_v3_repair import (
    FAILED_PACK_REVISION_V3,
    repair_record_sha256_v3,
    validate_repaired_calibration_pack_v3,
)

CALIBRATION_QUALIFICATION_FREEZE_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-calibration-qualification-freeze-v3"
)
CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3 = (
    "9dd4648f904df55dad3411c709d4f50f5a569a16"
)
EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3 = (
    "b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593"
)

REPAIR_RECORD_CANONICAL_SHA256_V3 = (
    "93a28f3e3f810182e4ce018aeab4f44103359e2f4251e9566e29335214d61bea"
)
REPAIR_RECORD_FILE_SHA256_V3 = (
    "67042427cb8d4620265a13446073cfc4e73a3f4dc2b71a88e0cf3484b057a410"
)
REPAIRED_CALIBRATION_PACK_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-calibration-pack-v3-repair-v1"
)
REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3 = (
    "c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513"
)
REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3 = (
    "75fa710ada934da9e465721e38313ff1157c7b89963b18d760d1eca6703d43b0"
)
REPAIRED_CALIBRATION_QUALIFICATION_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-calibration-qualification-v3-repair-v1"
)
REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3 = (
    "255f7a1dadf12e0dfd5107ab21c48cbaa07fe91ae937095001f00249750b2923"
)
REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3 = (
    "732ebf9d9df79d00bda9de6ab0229784533a8ffad485aa4967bf746971be1ba1"
)
QUALIFIED_DOCKER_REPORT_SHA256_V3 = (
    "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"
)
FAILED_C3Q_MANIFEST_SHA256_V3 = (
    "10389a3bdd0c0db45d23a3a248a8a237906adac602433cd9033ceae499e4a276"
)
FAILED_C3Q_FILE_COUNT_V3 = 10
FAILED_C3Q_ROOT_V3 = "artifacts/capable-collective/c3q"
REPAIRED_C3Q_ROOT_V3 = "artifacts/capable-collective/c3q-r1"

CALIBRATION_TASK_DIAGNOSTICS_V3 = (
    (
        "repository-surgery-calibration-v3-api-contract-0001",
        0.5,
        0.5,
        1.0,
        1.0,
    ),
    (
        "repository-surgery-calibration-v3-boundary-0001",
        0.75,
        1.0,
        1.0,
        1.0,
    ),
    (
        "repository-surgery-calibration-v3-error-handling-0001",
        0.5,
        0.75,
        1.0,
        1.0,
    ),
    (
        "repository-surgery-calibration-v3-local-logic-0001",
        0.25,
        1.0,
        1.0,
        1.0,
    ),
    (
        "repository-surgery-calibration-v3-multi-file-0001",
        0.0,
        1.0,
        1.0,
        1.0,
    ),
    (
        "repository-surgery-calibration-v3-state-management-0001",
        0.0,
        1.0,
        1.0,
        1.0,
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


def calibration_qualification_freeze_payload_v3() -> dict[str, Any]:
    return {
        "schema": CALIBRATION_QUALIFICATION_FREEZE_SCHEMA_V3,
        "scientific_status": (
            "v3-repaired-calibration-pack-qualified-frozen-before-candidate-inference"
        ),
        "software_revision": CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3,
        "failed_pack_revision": FAILED_PACK_REVISION_V3,
        "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
        "repair_record": {
            "canonical_sha256": REPAIR_RECORD_CANONICAL_SHA256_V3,
            "file_sha256": REPAIR_RECORD_FILE_SHA256_V3,
        },
        "calibration_pack": {
            "schema": REPAIRED_CALIBRATION_PACK_SCHEMA_V3,
            "canonical_sha256": REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
            "file_sha256": REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3,
        },
        "qualification": {
            "schema": REPAIRED_CALIBRATION_QUALIFICATION_SCHEMA_V3,
            "canonical_sha256": REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3,
            "file_sha256": REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER_REPORT_SHA256_V3,
            "failed_artifact_root_reused": False,
        },
        "failed_evidence": {
            "root": FAILED_C3Q_ROOT_V3,
            "manifest_sha256_before": FAILED_C3Q_MANIFEST_SHA256_V3,
            "manifest_sha256_after": FAILED_C3Q_MANIFEST_SHA256_V3,
            "file_count": FAILED_C3Q_FILE_COUNT_V3,
            "preserved": True,
        },
        "repaired_evidence_root": REPAIRED_C3Q_ROOT_V3,
        "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
        "task_count": V3_FRESH_CALIBRATION_TASK_COUNT,
        "tasks": [
            {
                "task_id": task_id,
                "baseline_exact_accuracy": baseline_exact,
                "baseline_valid_rate": baseline_valid,
                "gold_exact_accuracy": gold_exact,
                "gold_valid_rate": gold_valid,
            }
            for task_id, baseline_exact, baseline_valid, gold_exact, gold_valid
            in CALIBRATION_TASK_DIAGNOSTICS_V3
        ],
        "future_calibration": {
            "pair_count": len(V3_DEVELOPMENT_CANDIDATE_IDS)
            * V3_FRESH_CALIBRATION_TASK_COUNT,
            "tasks_per_candidate": V3_FRESH_CALIBRATION_TASK_COUNT,
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
            "max_attempts_per_pair": 1,
            "candidate_specific_tuning": False,
            "reruns": False,
            "selection_evidence": False,
        },
        "candidate_model_calls_consumed": 0,
        "candidate_model_inference_performed": False,
        "calibration_candidate_outcomes_observed": False,
        "selection_outcomes_observed": False,
        "selection_evidence": False,
        "candidate_model_calls_authorized_by_this_freeze": False,
    }


def validate_calibration_qualification_freeze_v3() -> None:
    validate_v3_representation_protocol()
    validate_repaired_calibration_pack_v3()

    if FAILED_PACK_REVISION_V3 != "2fd0654aae7f4f8a336b509e3b6247833ee3b54f":
        raise RuntimeError("failed v3 pack revision drifted")
    if repair_record_sha256_v3() != REPAIR_RECORD_CANONICAL_SHA256_V3:
        raise RuntimeError("v3 calibration repair-record identity drifted")
    if QUALIFIED_DOCKER.report_sha256 != QUALIFIED_DOCKER_REPORT_SHA256_V3:
        raise RuntimeError("qualified Docker identity drifted")
    if tuple(item[0] for item in CALIBRATION_TASK_DIAGNOSTICS_V3) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("v3 calibration qualification task identities drifted")
    if FAILED_C3Q_FILE_COUNT_V3 <= 0:
        raise RuntimeError("failed c3q evidence must be nonempty")
    if V3_FRESH_CALIBRATION_TASK_COUNT != 6 or len(V3_DEVELOPMENT_CANDIDATE_IDS) != 4:
        raise RuntimeError("v3 calibration matrix dimensions drifted")

    for task_id, baseline_exact, _baseline_valid, gold_exact, gold_valid in (
        CALIBRATION_TASK_DIAGNOSTICS_V3
    ):
        if baseline_exact >= 1.0:
            raise RuntimeError(f"frozen baseline is not observably defective: {task_id}")
        if gold_exact != 1.0 or gold_valid != 1.0:
            raise RuntimeError(f"frozen gold qualification is incomplete: {task_id}")

    payload = calibration_qualification_freeze_payload_v3()
    if payload["qualification"]["failed_artifact_root_reused"]:
        raise RuntimeError("failed c3q evidence was incorrectly marked reused")
    if not payload["failed_evidence"]["preserved"]:
        raise RuntimeError("failed c3q preservation proof is missing")
    if (
        payload["failed_evidence"]["manifest_sha256_before"]
        != payload["failed_evidence"]["manifest_sha256_after"]
    ):
        raise RuntimeError("failed c3q evidence changed during repaired qualification")
    if payload["candidate_model_calls_consumed"] != 0:
        raise RuntimeError("candidate model calls occurred before qualification freeze")
    if payload["candidate_model_calls_authorized_by_this_freeze"]:
        raise RuntimeError("qualification freeze must not itself authorize inference")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3:
        raise RuntimeError("v3 calibration qualification freeze identity drifted")


validate_calibration_qualification_freeze_v3()
