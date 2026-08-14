from __future__ import annotations

from plural_cognition.collective.local_operational_freeze_v1 import (
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
)
from plural_cognition.collective.qualified_docker import QUALIFIED_DOCKER
from plural_cognition.collective.repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1,
    SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256,
    SELECTION_PACK_SHA256,
    SELECTION_PACK_SOURCE_REVISION,
    SELECTION_QUALIFICATION_REPORT_SHA256,
    SELECTION_QUALIFIED_DOCKER_REPORT_SHA256,
)
from plural_cognition.collective.repository_surgery_selection_pack_v1 import (
    SELECTION_TASK_COUNT,
    selection_blueprints,
)


def test_selection_pack_freeze_binds_target_qualification_evidence() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1
    freeze.validate_against_repository()
    assert freeze.source_revision == SELECTION_PACK_SOURCE_REVISION
    assert freeze.selection_pack_sha256 == SELECTION_PACK_SHA256
    assert freeze.qualification_report_sha256 == SELECTION_QUALIFICATION_REPORT_SHA256
    assert freeze.operational_config_freeze_sha256 == SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256
    assert freeze.qualified_docker_report_sha256 == SELECTION_QUALIFIED_DOCKER_REPORT_SHA256
    assert freeze.operational_config_freeze_sha256 == FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256
    assert freeze.qualified_docker_report_sha256 == QUALIFIED_DOCKER.report_sha256


def test_selection_pack_freeze_preserves_exact_twelve_task_identity() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1
    assert freeze.task_count == SELECTION_TASK_COUNT == 12
    assert freeze.task_ids == tuple(item.task_id for item in selection_blueprints())
    assert len(set(freeze.task_ids)) == 12
    assert all(task_id.startswith("repository-surgery-selection-") for task_id in freeze.task_ids)


def test_selection_pack_freeze_is_content_addressed() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1
    assert len(FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256) == 64
    assert freeze.sha256 == FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256
    assert freeze.canonical_payload()["selection_pack_sha256"] == (
        "0530c682bbd4b4e7153142cba8350990ff3e2fad578cd765a4a2d9d8207d331d"
    )
    assert freeze.canonical_payload()["qualification_report_sha256"] == (
        "c8f98e2f9458d86c29f0323f0873faad5c9c6fdb2ed2e0839e20fc5c59aa28dd"
    )
