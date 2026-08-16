from __future__ import annotations

import hashlib
import json

from plural_cognition.collective.candidate_pool_v3_expansion_calibration_runner_freeze import (
    EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3,
    candidate_pool_v3_expansion_calibration_runner_freeze_payload,
    validate_candidate_pool_v3_expansion_calibration_runner_freeze,
)


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def test_expansion_calibration_runner_freeze_validates() -> None:
    validate_candidate_pool_v3_expansion_calibration_runner_freeze()


def test_expansion_calibration_runner_freeze_identity_is_exact() -> None:
    payload = candidate_pool_v3_expansion_calibration_runner_freeze_payload()
    assert _canonical_sha256(payload) == (
        EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3
    )


def test_expansion_calibration_runner_freeze_authorizes_only_sequential_calibration() -> None:
    payload = candidate_pool_v3_expansion_calibration_runner_freeze_payload()
    authorization = payload["authorization"]
    assert authorization["candidate_model_calls_consumed_before_freeze"] == 0
    assert authorization["candidate_model_calls_authorized_upper_bound"] == 18
    assert authorization["sequential_candidate_batch_size"] == 6
    assert authorization["stop_after_first_gate_pass"] is True
    assert authorization["max_attempts_per_pair"] == 1
    assert authorization["attempt_marker_before_inference"] is True
    assert authorization["partial_pair_blocks_all_new_inference"] is True
    assert authorization["completed_result_reused_verbatim"] is True
    assert authorization["calibration_inference_authorized_after_green"] is True
    for field in (
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
    ):
        assert authorization[field] is False
    assert payload["selection_evidence"] is False
