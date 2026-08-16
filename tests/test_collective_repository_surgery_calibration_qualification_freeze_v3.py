import hashlib
import json

from plural_cognition.collective.repository_surgery_calibration_qualification_freeze_v3 import (
    CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3,
    CALIBRATION_TASK_DIAGNOSTICS_V3,
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    FAILED_C3Q_FILE_COUNT_V3,
    FAILED_C3Q_MANIFEST_SHA256_V3,
    QUALIFIED_DOCKER_REPORT_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3,
    REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3,
    REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3,
    REPAIR_RECORD_CANONICAL_SHA256_V3,
    REPAIR_RECORD_FILE_SHA256_V3,
    calibration_qualification_freeze_payload_v3,
    validate_calibration_qualification_freeze_v3,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def test_v3_calibration_qualification_freeze_exact_identity() -> None:
    validate_calibration_qualification_freeze_v3()
    payload = calibration_qualification_freeze_payload_v3()
    assert hashlib.sha256(_canonical(payload)).hexdigest() == (
        EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
    )
    assert CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3 == (
        "9dd4648f904df55dad3411c709d4f50f5a569a16"
    )
    assert REPAIR_RECORD_CANONICAL_SHA256_V3 == (
        "93a28f3e3f810182e4ce018aeab4f44103359e2f4251e9566e29335214d61bea"
    )
    assert REPAIR_RECORD_FILE_SHA256_V3 == (
        "67042427cb8d4620265a13446073cfc4e73a3f4dc2b71a88e0cf3484b057a410"
    )
    assert REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3 == (
        "c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513"
    )
    assert REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3 == (
        "75fa710ada934da9e465721e38313ff1157c7b89963b18d760d1eca6703d43b0"
    )
    assert REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3 == (
        "255f7a1dadf12e0dfd5107ab21c48cbaa07fe91ae937095001f00249750b2923"
    )
    assert REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3 == (
        "732ebf9d9df79d00bda9de6ab0229784533a8ffad485aa4967bf746971be1ba1"
    )
    assert QUALIFIED_DOCKER_REPORT_SHA256_V3 == (
        "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"
    )


def test_v3_calibration_qualification_freeze_preserves_failed_evidence() -> None:
    payload = calibration_qualification_freeze_payload_v3()
    assert FAILED_C3Q_MANIFEST_SHA256_V3 == (
        "10389a3bdd0c0db45d23a3a248a8a237906adac602433cd9033ceae499e4a276"
    )
    assert FAILED_C3Q_FILE_COUNT_V3 == 10
    assert payload["failed_evidence"] == {
        "root": "artifacts/capable-collective/c3q",
        "manifest_sha256_before": FAILED_C3Q_MANIFEST_SHA256_V3,
        "manifest_sha256_after": FAILED_C3Q_MANIFEST_SHA256_V3,
        "file_count": 10,
        "preserved": True,
    }
    assert payload["repaired_evidence_root"] == "artifacts/capable-collective/c3q-r1"
    assert payload["qualification"]["failed_artifact_root_reused"] is False


def test_v3_calibration_qualification_freeze_has_six_real_defects_and_exact_gold() -> None:
    assert len(CALIBRATION_TASK_DIAGNOSTICS_V3) == 6
    for _task_id, baseline_exact, _baseline_valid, gold_exact, gold_valid in (
        CALIBRATION_TASK_DIAGNOSTICS_V3
    ):
        assert baseline_exact < 1.0
        assert gold_exact == 1.0
        assert gold_valid == 1.0

    assert CALIBRATION_TASK_DIAGNOSTICS_V3 == (
        ("repository-surgery-calibration-v3-api-contract-0001", 0.5, 0.5, 1.0, 1.0),
        ("repository-surgery-calibration-v3-boundary-0001", 0.75, 1.0, 1.0, 1.0),
        ("repository-surgery-calibration-v3-error-handling-0001", 0.5, 0.75, 1.0, 1.0),
        ("repository-surgery-calibration-v3-local-logic-0001", 0.25, 1.0, 1.0, 1.0),
        ("repository-surgery-calibration-v3-multi-file-0001", 0.0, 1.0, 1.0, 1.0),
        ("repository-surgery-calibration-v3-state-management-0001", 0.0, 1.0, 1.0, 1.0),
    )


def test_v3_calibration_qualification_freeze_authorizes_no_model_calls() -> None:
    payload = calibration_qualification_freeze_payload_v3()
    assert payload["candidate_model_calls_consumed"] == 0
    assert payload["candidate_model_inference_performed"] is False
    assert payload["calibration_candidate_outcomes_observed"] is False
    assert payload["selection_outcomes_observed"] is False
    assert payload["selection_evidence"] is False
    assert payload["candidate_model_calls_authorized_by_this_freeze"] is False
    assert payload["future_calibration"] == {
        "pair_count": 24,
        "tasks_per_candidate": 6,
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
        "max_attempts_per_pair": 1,
        "candidate_specific_tuning": False,
        "reruns": False,
        "selection_evidence": False,
    }
