"""Immutable target-qualified Repository Surgery selection-pack identity.

This module is created only after the untouched selection pack was qualified on
the target machine.  It binds the exact source revision that generated the pack,
the pack bytes, the qualification report bytes, the already-frozen operational
configuration, and the qualified Docker identity.  It contains no candidate
selection outputs and does not choose the final four minds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .content_store import validate_sha256
from .local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
from .qualified_docker import QUALIFIED_DOCKER
from .repository_surgery_calibration_matrix import calibration_blueprints
from .repository_surgery_selection_pack_v1 import SELECTION_TASK_COUNT, selection_blueprints

SELECTION_PACK_FREEZE_SCHEMA = "plural-cognition-repository-surgery-selection-pack-freeze-v1"
SELECTION_PACK_SOURCE_REVISION = "5b1c3724ba98f401b2367a1f8fa8bc10764fee0f"
SELECTION_PACK_SHA256 = "0530c682bbd4b4e7153142cba8350990ff3e2fad578cd765a4a2d9d8207d331d"
SELECTION_QUALIFICATION_REPORT_SHA256 = "c8f98e2f9458d86c29f0323f0873faad5c9c6fdb2ed2e0839e20fc5c59aa28dd"
SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256 = "448f72a61f320017138b5222cfed4673d001478e17bb7bc21185e04e8874066f"
SELECTION_QUALIFIED_DOCKER_REPORT_SHA256 = "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


@dataclass(frozen=True, slots=True)
class RepositorySurgerySelectionPackFreezeV1:
    source_revision: str = SELECTION_PACK_SOURCE_REVISION
    selection_pack_sha256: str = SELECTION_PACK_SHA256
    qualification_report_sha256: str = SELECTION_QUALIFICATION_REPORT_SHA256
    operational_config_freeze_sha256: str = SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256
    qualified_docker_report_sha256: str = SELECTION_QUALIFIED_DOCKER_REPORT_SHA256
    task_count: int = SELECTION_TASK_COUNT

    def __post_init__(self) -> None:
        if type(self.source_revision) is not str or len(self.source_revision) != 40:
            raise ValueError("source_revision must be a full Git SHA")
        try:
            int(self.source_revision, 16)
        except ValueError as exc:
            raise ValueError("source_revision must be hexadecimal") from exc
        if self.source_revision != self.source_revision.lower():
            raise ValueError("source_revision must use lowercase hexadecimal")
        for digest in (
            self.selection_pack_sha256,
            self.qualification_report_sha256,
            self.operational_config_freeze_sha256,
            self.qualified_docker_report_sha256,
        ):
            validate_sha256(digest)
        if type(self.task_count) is not int or self.task_count != SELECTION_TASK_COUNT:
            raise ValueError("selection freeze must bind the twelve-task pack")

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(item.task_id for item in selection_blueprints())

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_PACK_FREEZE_SCHEMA,
            "source_revision": self.source_revision,
            "selection_pack_sha256": self.selection_pack_sha256,
            "qualification_report_sha256": self.qualification_report_sha256,
            "operational_config_freeze_sha256": self.operational_config_freeze_sha256,
            "qualified_docker_report_sha256": self.qualified_docker_report_sha256,
            "task_count": self.task_count,
            "task_ids": list(self.task_ids),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()

    def validate_against_repository(self) -> None:
        if self.operational_config_freeze_sha256 != FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256:
            raise ValueError("selection freeze operational configuration drifted")
        if self.qualified_docker_report_sha256 != QUALIFIED_DOCKER.report_sha256:
            raise ValueError("selection freeze qualified Docker identity drifted")
        items = selection_blueprints()
        if len(items) != self.task_count:
            raise ValueError("selection task count drifted")
        ids = tuple(item.task_id for item in items)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("selection task ids must remain sorted and unique")
        calibration_ids = {item.task_id for item in calibration_blueprints()}
        if calibration_ids.intersection(ids):
            raise ValueError("selection pack overlaps calibration task ids")


FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1 = RepositorySurgerySelectionPackFreezeV1()
FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1.validate_against_repository()
FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256 = (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1.sha256
)
