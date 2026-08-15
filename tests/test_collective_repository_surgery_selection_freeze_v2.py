from plural_cognition.collective.candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from plural_cognition.collective.qualified_docker import QUALIFIED_DOCKER
from plural_cognition.collective.repository_surgery_selection_freeze_v2 import (
    EXPECTED_SELECTION_PACK_FREEZE_SHA256_V2,
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_PACK_SOURCE_REVISION_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
    SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2,
    candidate_pool_v2_selection_pack_freeze_payload,
    validate_selection_pack_freeze_v2_against_repository,
)
from plural_cognition.collective.repository_surgery_selection_pack_v2 import (
    SELECTION_TASK_COUNT_V2,
    selection_blueprints_v2,
)


def test_candidate_pool_v2_selection_pack_freeze_is_exact_and_preselection() -> None:
    validate_selection_pack_freeze_v2_against_repository()
    payload = candidate_pool_v2_selection_pack_freeze_payload()

    assert FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2 == (
        EXPECTED_SELECTION_PACK_FREEZE_SHA256_V2
    )
    assert SELECTION_PACK_SOURCE_REVISION_V2 == "1e74b8234c21dc5a1bbf6b2c240e1407a0334479"
    assert SELECTION_PACK_SHA256_V2 == "e9bbd38067d5b18b043b2f6eecc87f8f3795fc37b43edcbd0bf391ef6f6212b4"
    assert SELECTION_QUALIFICATION_REPORT_SHA256_V2 == (
        "4e24679d44e63757c481cd2c21cd13d54d6b3aa4fcc780a26d4a6363c58c6134"
    )
    assert SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2 == (
        FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256
    )
    assert SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2 == QUALIFIED_DOCKER.report_sha256

    assert payload["candidate_ids"] == list(FINAL_CANDIDATE_IDS_V2)
    assert payload["task_count"] == SELECTION_TASK_COUNT_V2 == 12
    assert payload["task_ids"] == [item.task_id for item in selection_blueprints_v2()]
    assert payload["candidate_model_inference_performed"] is False
    assert payload["selection_outcomes_observed"] is False
    assert payload["selection_calls_consumed"] == 0
