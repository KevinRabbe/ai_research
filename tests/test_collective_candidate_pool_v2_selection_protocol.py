from plural_cognition.collective.candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
)
from plural_cognition.collective.candidate_pool_v2_selection_protocol import (
    EXPECTED_SELECTION_PROTOCOL_SHA256_V2,
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    SELECTION_MIN_VALID_RATE_V2,
    SELECTION_PAIR_COUNT_V2,
    SELECTION_POPULATION_SIZE_V2,
    SELECTION_TASK_IDS_V2,
    candidate_pool_v2_selection_protocol_payload,
    validate_selection_protocol_v2,
)
from plural_cognition.collective.repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
)


def test_candidate_pool_v2_selection_protocol_is_exact_one_shot_contract() -> None:
    validate_selection_protocol_v2()
    payload = candidate_pool_v2_selection_protocol_payload()

    assert FINAL_SELECTION_PROTOCOL_SHA256_V2 == EXPECTED_SELECTION_PROTOCOL_SHA256_V2
    assert payload["selection_pack_freeze_sha256"] == (
        FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2
    )
    assert payload["candidate_ids"] == list(FINAL_CANDIDATE_IDS_V2)
    assert payload["task_ids"] == list(SELECTION_TASK_IDS_V2)
    assert len(SELECTION_TASK_IDS_V2) == 12
    assert SELECTION_PAIR_COUNT_V2 == 60
    assert SELECTION_MIN_VALID_RATE_V2 == 0.95
    assert SELECTION_POPULATION_SIZE_V2 == 4

    representation = payload["representation"]
    assert representation["output_contract"] == "raw-full-file-replacement-v1"
    assert representation["max_attempts"] == 1
    assert representation["self_review"] is False
    assert representation["candidate_output_repair"] is False
    assert representation["fuzzy_matching"] is False

    selection = payload["selection"]
    assert selection["selection_run_count"] == 1
    assert selection["threshold_lowering_after_outcome"] is False
    assert selection["require_strongest_member"] is True

    evidence = payload["evidence_policy"]
    assert evidence["pair_attempt_marker_before_inference"] is True
    assert evidence["completed_pair_reused_without_inference"] is True
    assert evidence["partial_pair_blocks_all_new_inference"] is True
    assert evidence["raw_streams_persisted_before_classification"] is True
    assert evidence["completed_suite_reused_verbatim"] is True
    assert evidence["selection_evidence"] is True
