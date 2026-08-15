"""Immutable qualified Repository Surgery selection-pack identity for candidate-pool v2.

This module is created only after the fresh twelve-task v2 selection pack was
qualified on the target machine. It binds the exact source revision that generated
the pack, the pack bytes, the qualification-report bytes, the already-frozen
five-survivor operational configuration, the qualified Docker identity, and the
exact task/candidate sets. It contains no candidate selection outputs and does not
choose the final four minds.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
    validate_operational_freeze_against_repository,
)
from .content_store import validate_sha256
from .qualified_docker import QUALIFIED_DOCKER
from .repository_surgery_selection_pack_v2 import (
    SELECTION_TASK_COUNT_V2,
    selection_blueprints_v2,
    validate_selection_pack_v2_freshness,
)

SELECTION_PACK_FREEZE_SCHEMA_V2 = "plural-cognition-repository-surgery-selection-pack-freeze-v2"
SELECTION_PACK_SOURCE_REVISION_V2 = "1e74b8234c21dc5a1bbf6b2c240e1407a0334479"
SELECTION_PACK_SHA256_V2 = "e9bbd38067d5b18b043b2f6eecc87f8f3795fc37b43edcbd0bf391ef6f6212b4"
SELECTION_QUALIFICATION_REPORT_SHA256_V2 = "4e24679d44e63757c481cd2c21cd13d54d6b3aa4fcc780a26d4a6363c58c6134"
SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2 = "9fabeaaed55d4dfd8a500dec5346450cf5a497ed8f7fb3a65d5fec6b2307380b"
SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2 = "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"
EXPECTED_SELECTION_PACK_FREEZE_SHA256_V2 = "1fb5ff94d0e36ece19c64819e737172d2cd55f620273334f58ee6f940324d10a"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_selection_pack_freeze_payload() -> dict[str, Any]:
    tasks = selection_blueprints_v2()
    return {
        "schema": SELECTION_PACK_FREEZE_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-qualified-selection-pack-pre-selection",
        "source_revision": SELECTION_PACK_SOURCE_REVISION_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualification_report_sha256": SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        "operational_config_freeze_sha256": SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
        "qualified_docker_report_sha256": SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2,
        "task_count": SELECTION_TASK_COUNT_V2,
        "candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
        "task_ids": [item.task_id for item in tasks],
        "candidate_model_inference_performed": False,
        "selection_outcomes_observed": False,
        "selection_calls_consumed": 0,
    }


FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_selection_pack_freeze_payload())
).hexdigest()


def validate_selection_pack_freeze_v2_against_repository() -> None:
    validate_operational_freeze_against_repository()
    validate_selection_pack_v2_freshness()

    for digest in (
        SELECTION_PACK_SHA256_V2,
        SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
        SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2,
        EXPECTED_SELECTION_PACK_FREEZE_SHA256_V2,
    ):
        validate_sha256(digest)

    if SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2 != FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256:
        raise AssertionError("v2 selection freeze operational configuration drifted")
    if SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2 != QUALIFIED_DOCKER.report_sha256:
        raise AssertionError("v2 selection freeze qualified Docker identity drifted")

    tasks = selection_blueprints_v2()
    if len(tasks) != SELECTION_TASK_COUNT_V2:
        raise AssertionError("v2 selection task count drifted")
    task_ids = tuple(item.task_id for item in tasks)
    if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
        raise AssertionError("v2 selection task IDs must remain sorted and unique")
    if len(FINAL_CANDIDATE_IDS_V2) != 5 or len(set(FINAL_CANDIDATE_IDS_V2)) != 5:
        raise AssertionError("v2 selection candidate set drifted")
    if FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2 != EXPECTED_SELECTION_PACK_FREEZE_SHA256_V2:
        raise AssertionError("v2 selection-pack freeze identity drifted")


validate_selection_pack_freeze_v2_against_repository()
