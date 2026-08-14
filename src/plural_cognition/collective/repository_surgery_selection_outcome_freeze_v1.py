"""Immutable evidence for the first frozen Repository Surgery selection bakeoff.

The v1 selection pack was consumed exactly once by the five frozen candidate
configurations.  The predeclared population rule returned insufficient eligible
candidates, so this module records that negative result without changing the
selection threshold, candidate pool, task pack, prompt/output protocol, or
resource settings.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .bakeoff import PopulationSelectionStatus
from .content_store import validate_sha256
from .local_operational_freeze_v1 import (
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
)
from .repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
)

SELECTION_OUTCOME_FREEZE_SCHEMA = (
    "plural-cognition-repository-surgery-selection-outcome-freeze-v1"
)
SELECTION_BAKEOFF_SOFTWARE_REVISION = (
    "5e79a7b448ad3bdccbeb17132ce44861593f6ff9"
)
SELECTION_BAKEOFF_REPORT_SHA256 = (
    "cfb56dd84564db7de09be590c93107cf7d2c7e76f8971eabbe41a2f8926826fd"
)
SELECTION_BAKEOFF_PLAN_SHA256 = (
    "88183d2393942608c5953740cefb5ebfc6be5c493f323b9c8b8daffa75b58e69"
)
SELECTION_BAKEOFF_OUTPUT_MANIFEST_SHA256 = (
    "fa80dcc9fa8939d0d5585dee2912757860dd2596c75bd9a94274320fdf51f2d2"
)
SELECTION_BAKEOFF_RESULT_COUNT = 60
SELECTION_BAKEOFF_PARSED_COUNT = 45
SELECTION_BAKEOFF_SOLVED_COUNT = 44
SELECTION_BAKEOFF_MIN_VALID_RATE = 0.95
SELECTION_BAKEOFF_POPULATION_SIZE = 4


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


@dataclass(frozen=True, slots=True)
class SelectionCandidateDiagnosticFreezeV1:
    candidate_id: str
    task_count: int
    valid_count: int
    pass_count: int
    accelerator_time_ms: int
    total_tokens: int

    def __post_init__(self) -> None:
        if self.candidate_id not in FINAL_CANDIDATE_IDS:
            raise ValueError("selection diagnostic candidate is outside frozen pool")
        for field in (
            "task_count",
            "valid_count",
            "pass_count",
            "accelerator_time_ms",
            "total_tokens",
        ):
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field} must be a nonnegative integer")
        if self.task_count != 12:
            raise ValueError("v1 selection diagnostic must cover twelve tasks")
        if self.valid_count > self.task_count:
            raise ValueError("valid_count cannot exceed task_count")
        if self.pass_count > self.valid_count:
            raise ValueError("pass_count cannot exceed valid_count")

    @property
    def score(self) -> float:
        return self.pass_count / self.task_count

    @property
    def valid_rate(self) -> float:
        return self.valid_count / self.task_count

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "task_count": self.task_count,
            "valid_count": self.valid_count,
            "pass_count": self.pass_count,
            "score": self.score,
            "valid_rate": self.valid_rate,
            "accelerator_time_ms": self.accelerator_time_ms,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class RepositorySurgerySelectionOutcomeFreezeV1:
    software_revision: str
    report_sha256: str
    bakeoff_plan_sha256: str
    selection_pack_freeze_sha256: str
    operational_config_freeze_sha256: str
    output_manifest_sha256: str
    result_count: int
    parsed_count: int
    solved_count: int
    min_valid_rate: float
    population_size: int
    selection_status: PopulationSelectionStatus
    eligible_candidate_ids: tuple[str, ...]
    strongest_candidate_id: str | None
    selected_candidate_ids: tuple[str, ...]
    diagnostics: tuple[SelectionCandidateDiagnosticFreezeV1, ...]

    def __post_init__(self) -> None:
        if type(self.software_revision) is not str or len(self.software_revision) != 40:
            raise ValueError("software_revision must be a full Git SHA")
        try:
            int(self.software_revision, 16)
        except ValueError as exc:
            raise ValueError("software_revision must be hexadecimal") from exc
        if self.software_revision != self.software_revision.lower():
            raise ValueError("software_revision must use lowercase hexadecimal")
        for digest in (
            self.report_sha256,
            self.bakeoff_plan_sha256,
            self.selection_pack_freeze_sha256,
            self.operational_config_freeze_sha256,
            self.output_manifest_sha256,
        ):
            validate_sha256(digest)
        if type(self.result_count) is not int or self.result_count != 60:
            raise ValueError("v1 selection outcome must contain sixty results")
        if type(self.parsed_count) is not int or not 0 <= self.parsed_count <= 60:
            raise ValueError("parsed_count must be in [0, 60]")
        if type(self.solved_count) is not int or not 0 <= self.solved_count <= self.parsed_count:
            raise ValueError("solved_count must be in [0, parsed_count]")
        if type(self.min_valid_rate) not in (int, float) or float(self.min_valid_rate) != 0.95:
            raise ValueError("v1 selection min_valid_rate must remain 0.95")
        if type(self.population_size) is not int or self.population_size != 4:
            raise ValueError("v1 selection population_size must remain four")
        if not isinstance(self.selection_status, PopulationSelectionStatus):
            raise TypeError("selection_status must be PopulationSelectionStatus")
        if self.selection_status is not PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE:
            raise ValueError("v1 selection outcome must preserve insufficient-eligible")
        if self.strongest_candidate_id is not None:
            raise ValueError("insufficient-eligible path must not designate strongest member")
        if self.selected_candidate_ids:
            raise ValueError("insufficient-eligible path must not designate a population")
        if tuple(item.candidate_id for item in self.diagnostics) != FINAL_CANDIDATE_IDS:
            raise ValueError("selection diagnostics must preserve frozen candidate order")
        if sum(item.valid_count for item in self.diagnostics) != self.parsed_count:
            raise ValueError("selection parsed-count evidence is inconsistent")
        if sum(item.pass_count for item in self.diagnostics) != self.solved_count:
            raise ValueError("selection solved-count evidence is inconsistent")
        eligible = tuple(
            item.candidate_id
            for item in self.diagnostics
            if item.valid_rate >= float(self.min_valid_rate)
        )
        if eligible != self.eligible_candidate_ids:
            raise ValueError("eligible candidate IDs do not follow frozen validity threshold")
        if len(eligible) >= self.population_size:
            raise ValueError("insufficient-eligible outcome contradicts diagnostic counts")

    def validate_against_repository(self) -> None:
        if self.selection_pack_freeze_sha256 != FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256:
            raise ValueError("selection outcome pack freeze drifted")
        if self.operational_config_freeze_sha256 != FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256:
            raise ValueError("selection outcome operational freeze drifted")
        if self.software_revision != SELECTION_BAKEOFF_SOFTWARE_REVISION:
            raise ValueError("selection outcome software revision drifted")
        if self.report_sha256 != SELECTION_BAKEOFF_REPORT_SHA256:
            raise ValueError("selection outcome report identity drifted")
        if self.bakeoff_plan_sha256 != SELECTION_BAKEOFF_PLAN_SHA256:
            raise ValueError("selection outcome plan identity drifted")
        if self.output_manifest_sha256 != SELECTION_BAKEOFF_OUTPUT_MANIFEST_SHA256:
            raise ValueError("selection outcome output manifest drifted")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_OUTCOME_FREEZE_SCHEMA,
            "software_revision": self.software_revision,
            "report_sha256": self.report_sha256,
            "bakeoff_plan_sha256": self.bakeoff_plan_sha256,
            "selection_pack_freeze_sha256": self.selection_pack_freeze_sha256,
            "operational_config_freeze_sha256": self.operational_config_freeze_sha256,
            "output_manifest_sha256": self.output_manifest_sha256,
            "result_count": self.result_count,
            "parsed_count": self.parsed_count,
            "solved_count": self.solved_count,
            "min_valid_rate": float(self.min_valid_rate),
            "population_size": self.population_size,
            "selection_status": self.selection_status.value,
            "eligible_candidate_ids": list(self.eligible_candidate_ids),
            "strongest_candidate_id": self.strongest_candidate_id,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "diagnostics": [item.canonical_payload() for item in self.diagnostics],
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()


FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1 = (
    RepositorySurgerySelectionOutcomeFreezeV1(
        software_revision=SELECTION_BAKEOFF_SOFTWARE_REVISION,
        report_sha256=SELECTION_BAKEOFF_REPORT_SHA256,
        bakeoff_plan_sha256=SELECTION_BAKEOFF_PLAN_SHA256,
        selection_pack_freeze_sha256=FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        operational_config_freeze_sha256=FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        output_manifest_sha256=SELECTION_BAKEOFF_OUTPUT_MANIFEST_SHA256,
        result_count=SELECTION_BAKEOFF_RESULT_COUNT,
        parsed_count=SELECTION_BAKEOFF_PARSED_COUNT,
        solved_count=SELECTION_BAKEOFF_SOLVED_COUNT,
        min_valid_rate=SELECTION_BAKEOFF_MIN_VALID_RATE,
        population_size=SELECTION_BAKEOFF_POPULATION_SIZE,
        selection_status=PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE,
        eligible_candidate_ids=("deepseek-coder-v2-lite-q5km",),
        strongest_candidate_id=None,
        selected_candidate_ids=(),
        diagnostics=(
            SelectionCandidateDiagnosticFreezeV1(
                "qwen3-8b-q8", 12, 9, 9, 347696, 0
            ),
            SelectionCandidateDiagnosticFreezeV1(
                "qwen2.5-coder-14b-q5km", 12, 11, 11, 95272, 0
            ),
            SelectionCandidateDiagnosticFreezeV1(
                "gemma4-12b-it-qat-q4", 12, 2, 2, 753765, 0
            ),
            SelectionCandidateDiagnosticFreezeV1(
                "devstral-24b-q4km", 12, 11, 11, 149033, 0
            ),
            SelectionCandidateDiagnosticFreezeV1(
                "deepseek-coder-v2-lite-q5km", 12, 12, 11, 85595, 0
            ),
        ),
    )
)
FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1.validate_against_repository()
FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256 = (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1.sha256
)
