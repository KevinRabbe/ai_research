from __future__ import annotations

import hashlib
import json

from plural_cognition.collective.candidate_pool_v3_expansion_load_outcome_freeze import (
    EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3,
    candidate_pool_v3_expansion_load_outcome_freeze_payload,
    validate_candidate_pool_v3_expansion_load_outcome_freeze,
)
from plural_cognition.collective.candidate_pool_v3_expansion_source_freeze import (
    EXPANSION_SCOUT_IDS_V3,
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


def test_v3_expansion_load_outcome_freeze_validates() -> None:
    validate_candidate_pool_v3_expansion_load_outcome_freeze()


def test_v3_expansion_load_outcome_freeze_identity_is_exact() -> None:
    payload = candidate_pool_v3_expansion_load_outcome_freeze_payload()
    assert _canonical_sha256(payload) == EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3


def test_v3_expansion_load_outcome_freezes_three_full_offload_passes() -> None:
    payload = candidate_pool_v3_expansion_load_outcome_freeze_payload()
    assert tuple(payload["scout_ids"]) == EXPANSION_SCOUT_IDS_V3
    assert payload["result_count"] == 3
    assert payload["qualified_count"] == 3
    assert payload["failed_count"] == 0
    assert payload["new_model_launch_count"] == 3
    assert payload["attempt_marker_count"] == 3
    assert payload["completed_result_count"] == 3
    assert payload["partial_result_count"] == 0
    assert all(item["status"] == "LOCAL_MODEL_LOAD_PASS" for item in payload["results"])
    assert all(
        item["offloaded_layers"] == item["total_layers"]
        for item in payload["results"]
    )


def test_v3_expansion_load_outcome_only_authorizes_calibration_runner_authoring() -> None:
    authorization = candidate_pool_v3_expansion_load_outcome_freeze_payload()["authorization"]
    assert authorization == {
        "load_rerun_authorized": False,
        "artifact_substitution_authorized": False,
        "scout_reordering_authorized": False,
        "candidate_specific_runtime_tuning_authorized": False,
        "calibration_runner_authoring_authorized_after_green": True,
        "calibration_inference_authorized": False,
        "selection_pack_authoring_authorized": False,
        "selection_inference_authorized": False,
        "plural_synthesis_authorized": False,
    }
