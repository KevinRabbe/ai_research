"""Immutable negative outcome of the fresh candidate-pool v2 selection run.

The qualified twelve-task v2 selection pack was consumed exactly once by the five
post-calibration candidates. The predeclared 95% operational-validity threshold
left only qwen3-8b-q8 eligible, so the frozen four-member population could not be
instantiated. This module records that negative evidence without lowering the
threshold, changing candidates/tasks, rerunning any pair, or selecting a population
post hoc.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .bakeoff import PopulationSelectionStatus
from .candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from .candidate_pool_v2_selection_protocol import (
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    SELECTION_MIN_VALID_RATE_V2,
    SELECTION_PAIR_COUNT_V2,
    SELECTION_POPULATION_SIZE_V2,
)
from .content_store import validate_sha256
from .repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
)

SELECTION_OUTCOME_FREEZE_SCHEMA_V2 = (
    "plural-cognition-repository-surgery-selection-outcome-freeze-v2"
)
SELECTION_OUTCOME_SOFTWARE_REVISION_V2 = (
    "3f67203429c31ab05970bbe476b965b5c1c1213c"
)
SELECTION_SUITE_FILE_SHA256_V2 = (
    "ac77effa62f42cd6914b8a67765a2318b72281f59edc94e3a8e5cbc114c41fce"
)
SELECTION_REPORT_SHA256_V2 = (
    "713f25bc8635914bb8c491eb291f6355998995bb237d3d929a58d83a0db7a01c"
)
SELECTION_PARSED_COUNT_V2 = 33
SELECTION_SOLVED_COUNT_V2 = 30
EXPECTED_SELECTION_OUTCOME_FREEZE_SHA256_V2 = (
    "b22e5c6fded1e9d0bd94fd4a8cd45bd4712ea9782d58a1f8820a6fdcb35d9517"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


@dataclass(frozen=True, slots=True)
class SelectionCandidateDiagnosticFreezeV2:
    candidate_id: str
    task_count: int
    valid_count: int
    pass_count: int
    accelerator_time_ms: int
    total_tokens: int

    def __post_init__(self) -> None:
        if self.candidate_id not in FINAL_CANDIDATE_IDS_V2:
            raise ValueError("v2 selection diagnostic candidate is outside frozen pool")
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
            raise ValueError("v2 selection diagnostic must cover twelve tasks")
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
class RepositorySurgerySelectionOutcomeFreezeV2:
    software_revision: str
    selection_suite_file_sha256: str
    selection_report_sha256: str
    selection_protocol_sha256: str
    selection_pack_freeze_sha256: str
    selection_pack_sha256: str
    qualification_report_sha256: str
    operational_config_freeze_sha256: str
    pair_count: int
    parsed_count: int
    solved_count: int
    min_valid_rate: float
    population_size: int
    selection_status: PopulationSelectionStatus
    eligible_candidate_ids: tuple[str, ...]
    strongest_candidate_id: str | None
    selected_candidate_ids: tuple[str, ...]
    diagnostics: tuple[SelectionCandidateDiagnosticFreezeV2, ...]
    selection_calls_consumed: int
    threshold_lowering_authorized: bool
    rerun_authorized: bool
    selection_evidence: bool

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
            self.selection_suite_file_sha256,
            self.selection_report_sha256,
            self.selection_protocol_sha256,
            self.selection_pack_freeze_sha256,
            self.selection_pack_sha256,
            self.qualification_report_sha256,
            self.operational_config_freeze_sha256,
        ):
            validate_sha256(digest)
        if self.pair_count != SELECTION_PAIR_COUNT_V2 or self.pair_count != 60:
            raise ValueError("v2 selection outcome must contain sixty pairs")
        if type(self.parsed_count) is not int or not 0 <= self.parsed_count <= self.pair_count:
            raise ValueError("parsed_count must be in [0, pair_count]")
        if type(self.solved_count) is not int or not 0 <= self.solved_count <= self.parsed_count:
            raise ValueError("solved_count must be in [0, parsed_count]")
        if float(self.min_valid_rate) != SELECTION_MIN_VALID_RATE_V2 or float(self.min_valid_rate) != 0.95:
            raise ValueError("v2 selection min_valid_rate must remain 0.95")
        if self.population_size != SELECTION_POPULATION_SIZE_V2 or self.population_size != 4:
            raise ValueError("v2 selection population_size must remain four")
        if self.selection_status is not PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE:
            raise ValueError("v2 selection outcome must preserve insufficient-eligible")
        if self.strongest_candidate_id is not None:
            raise ValueError("insufficient-eligible path must not designate strongest member")
        if self.selected_candidate_ids:
            raise ValueError("insufficient-eligible path must not designate a population")
        if tuple(item.candidate_id for item in self.diagnostics) != FINAL_CANDIDATE_IDS_V2:
            raise ValueError("v2 selection diagnostics must preserve frozen candidate order")
        if sum(item.valid_count for item in self.diagnostics) != self.parsed_count:
            raise ValueError("v2 selection parsed-count evidence is inconsistent")
        if sum(item.pass_count for item in self.diagnostics) != self.solved_count:
            raise ValueError("v2 selection solved-count evidence is inconsistent")
        eligible = tuple(
            item.candidate_id
            for item in self.diagnostics
            if item.valid_rate >= float(self.min_valid_rate)
        )
        if eligible != self.eligible_candidate_ids:
            raise ValueError("eligible candidate IDs do not follow frozen validity threshold")
        if len(eligible) >= self.population_size:
            raise ValueError("insufficient-eligible outcome contradicts diagnostic counts")
        if self.selection_calls_consumed != self.pair_count:
            raise ValueError("all sixty v2 selection calls must remain consumed")
        if self.threshold_lowering_authorized is not False:
            raise ValueError("threshold lowering after v2 selection is forbidden")
        if self.rerun_authorized is not False:
            raise ValueError("v2 selection rerun must remain forbidden")
        if self.selection_evidence is not True:
            raise ValueError("v2 selection outcome must remain selection evidence")

    def validate_against_repository(self) -> None:
        if self.software_revision != SELECTION_OUTCOME_SOFTWARE_REVISION_V2:
            raise ValueError("v2 selection outcome software revision drifted")
        if self.selection_suite_file_sha256 != SELECTION_SUITE_FILE_SHA256_V2:
            raise ValueError("v2 selection suite file identity drifted")
        if self.selection_report_sha256 != SELECTION_REPORT_SHA256_V2:
            raise ValueError("v2 selection report identity drifted")
        if self.selection_protocol_sha256 != FINAL_SELECTION_PROTOCOL_SHA256_V2:
            raise ValueError("v2 selection protocol identity drifted")
        if self.selection_pack_freeze_sha256 != FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2:
            raise ValueError("v2 selection-pack freeze identity drifted")
        if self.selection_pack_sha256 != SELECTION_PACK_SHA256_V2:
            raise ValueError("v2 selection-pack identity drifted")
        if self.qualification_report_sha256 != SELECTION_QUALIFICATION_REPORT_SHA256_V2:
            raise ValueError("v2 selection qualification identity drifted")
        if self.operational_config_freeze_sha256 != FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256:
            raise ValueError("v2 selection operational freeze identity drifted")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_OUTCOME_FREEZE_SCHEMA_V2,
            "scientific_status": "candidate-pool-v2-frozen-negative-selection-outcome",
            "software_revision": self.software_revision,
            "selection_suite_file_sha256": self.selection_suite_file_sha256,
            "selection_report_sha256": self.selection_report_sha256,
            "selection_protocol_sha256": self.selection_protocol_sha256,
            "selection_pack_freeze_sha256": self.selection_pack_freeze_sha256,
            "selection_pack_sha256": self.selection_pack_sha256,
            "qualification_report_sha256": self.qualification_report_sha256,
            "operational_config_freeze_sha256": self.operational_config_freeze_sha256,
            "pair_count": self.pair_count,
            "parsed_count": self.parsed_count,
            "solved_count": self.solved_count,
            "min_valid_rate": float(self.min_valid_rate),
            "population_size": self.population_size,
            "selection_status": self.selection_status.value,
            "eligible_candidate_ids": list(self.eligible_candidate_ids),
            "strongest_candidate_id": self.strongest_candidate_id,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "diagnostics": [item.canonical_payload() for item in self.diagnostics],
            "selection_calls_consumed": self.selection_calls_consumed,
            "threshold_lowering_authorized": self.threshold_lowering_authorized,
            "rerun_authorized": self.rerun_authorized,
            "selection_evidence": self.selection_evidence,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2 = (
    RepositorySurgerySelectionOutcomeFreezeV2(
        software_revision=SELECTION_OUTCOME_SOFTWARE_REVISION_V2,
        selection_suite_file_sha256=SELECTION_SUITE_FILE_SHA256_V2,
        selection_report_sha256=SELECTION_REPORT_SHA256_V2,
        selection_protocol_sha256=FINAL_SELECTION_PROTOCOL_SHA256_V2,
        selection_pack_freeze_sha256=FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        selection_pack_sha256=SELECTION_PACK_SHA256_V2,
        qualification_report_sha256=SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        operational_config_freeze_sha256=FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
        pair_count=SELECTION_PAIR_COUNT_V2,
        parsed_count=SELECTION_PARSED_COUNT_V2,
        solved_count=SELECTION_SOLVED_COUNT_V2,
        min_valid_rate=SELECTION_MIN_VALID_RATE_V2,
        population_size=SELECTION_POPULATION_SIZE_V2,
        selection_status=PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE,
        eligible_candidate_ids=("qwen3-8b-q8",),
        strongest_candidate_id=None,
        selected_candidate_ids=(),
        diagnostics=(
            SelectionCandidateDiagnosticFreezeV2("qwen3-8b-q8", 12, 12, 10, 308774, 0),
            SelectionCandidateDiagnosticFreezeV2("qwen2.5-coder-14b-q5km", 12, 11, 10, 127614, 0),
            SelectionCandidateDiagnosticFreezeV2("devstral-24b-q4km", 12, 8, 8, 344101, 0),
            SelectionCandidateDiagnosticFreezeV2("gpt-oss-20b-mxfp4", 12, 2, 2, 138091, 0),
            SelectionCandidateDiagnosticFreezeV2("devstral-small-2-24b-q4km", 12, 0, 0, 264873, 0),
        ),
        selection_calls_consumed=60,
        threshold_lowering_authorized=False,
        rerun_authorized=False,
        selection_evidence=True,
    )
)
FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.validate_against_repository()
FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256_V2 = (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.sha256
)
if FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256_V2 != EXPECTED_SELECTION_OUTCOME_FREEZE_SHA256_V2:
    raise AssertionError("candidate-pool v2 selection outcome freeze identity drifted")
