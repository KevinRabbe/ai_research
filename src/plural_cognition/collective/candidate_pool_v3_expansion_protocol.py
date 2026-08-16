"""Prefreeze protocol for candidate-pool v3 expansion after calibration infeasibility.

The completed v3 calibration left three eligible candidates for a four-member
population. This protocol is intentionally frozen before any new challenger identity
is selected or tested. It authorizes only source-scout freeze authoring. New model
inference remains unauthorized until a later source/load qualification chain is
itself frozen.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_calibration_outcome_freeze import (
    CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3,
    CALIBRATION_REQUIRED_POPULATION_SIZE_V3,
    FINAL_CANDIDATE_POOL_V3_CALIBRATION_OUTCOME_FREEZE_SHA256,
    validate_candidate_pool_v3_calibration_outcome_freeze,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
)

CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SCHEMA = (
    "plural-cognition-candidate-pool-v3-expansion-protocol-v1"
)
CANDIDATE_POOL_V3_EXPANSION_PREDECESSOR_REVISION = (
    "5433bc8d561ad025632e1af0b4658b8d37852fe9"
)
EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256 = (
    "2ac18170b0dc5a1708f3974816dafdd28fa092f01d8170afc0e85d65dcbae4fc"
)
EXPANSION_SCOUT_COUNT_V3 = 3
EXPANSION_REQUIRED_ADDITIONAL_ELIGIBLE_V3 = 1
EXPANSION_MAX_CALIBRATION_CANDIDATES_V3 = 3
EXPANSION_MAX_CANDIDATE_TASK_CALLS_V3 = 18


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_protocol_payload() -> dict[str, Any]:
    return {
        "schema": CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SCHEMA,
        "scientific_status": (
            "candidate-pool-v3-expansion-prefreeze-before-new-candidate-identity"
        ),
        "predecessor_calibration_outcome_revision": (
            CANDIDATE_POOL_V3_EXPANSION_PREDECESSOR_REVISION
        ),
        "predecessor_calibration_outcome_freeze_sha256": (
            FINAL_CANDIDATE_POOL_V3_CALIBRATION_OUTCOME_FREEZE_SHA256
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "existing_eligible_candidate_ids": list(
            CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3
        ),
        "required_population_size": CALIBRATION_REQUIRED_POPULATION_SIZE_V3,
        "additional_eligible_candidates_required": (
            EXPANSION_REQUIRED_ADDITIONAL_ELIGIBLE_V3
        ),
        "scouting": {
            "scout_count": EXPANSION_SCOUT_COUNT_V3,
            "candidate_identities_bound_by_this_protocol": False,
            "new_candidate_identity_observed_before_protocol_freeze": False,
            "new_candidate_calibration_outcome_observed_before_protocol_freeze": False,
            "new_artifact_identity_required": True,
            "previously_measured_candidate_artifact_reuse_forbidden": True,
            "all_scout_ids_and_artifacts_frozen_together_before_new_model_inference": True,
            "ordered_scout_list_frozen_before_new_model_inference": True,
            "allowed_selection_basis": [
                "first-party-source-provenance",
                "license-compatibility",
                "llama-cpp-runtime-compatibility",
                "full-gpu-fit-plausibility-under-frozen-hardware",
                "general-or-code-instruction-suitability-without-task-specific-evaluation",
            ],
            "forbidden_selection_basis": [
                "candidate-performance-on-consumed-v3-calibration-tasks",
                "candidate-specific-prompt-tuning-on-consumed-v3-calibration-tasks",
                "post-calibration-candidate-substitution",
                "selection-evidence",
            ],
        },
        "source_qualification": {
            "exact_first_party_source_revision_required": True,
            "exact_artifact_revision_required": True,
            "exact_artifact_sha256_required": True,
            "artifact_size_bytes_required_before_load": True,
            "community_quantization_allowed_only_with_first_party_source_binding": True,
            "moving_revision_urls_forbidden": True,
            "source_freeze_required_before_load_inference": True,
            "artifact_substitution_after_source_freeze": False,
        },
        "load_qualification": {
            "formal_load_attempts_per_scout": 1,
            "load_only_no_capability_prompt": True,
            "same_runtime_and_resource_budget_as_v3_representation_protocol": True,
            "full_gpu_offload_required": True,
            "fit_mode": False,
            "load_failure_terminal_for_frozen_artifact": True,
            "automatic_reruns": False,
            "candidate_specific_runtime_tuning": False,
            "load_outcome_freeze_required_before_calibration_inference": True,
        },
        "calibration": {
            "task_ids_reused_from_completed_v3_development_calibration": True,
            "task_count_per_candidate": 6,
            "task_material_may_not_influence_scout_selection": True,
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
            "ordered_sequential_evaluation": True,
            "max_candidates_calibrated": EXPANSION_MAX_CALIBRATION_CANDIDATES_V3,
            "max_candidate_task_calls": EXPANSION_MAX_CANDIDATE_TASK_CALLS_V3,
            "stop_after_first_gate_pass": True,
            "one_call_per_pair": True,
            "max_attempts_per_pair": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "failed_candidate_rerun_authorized": False,
            "candidate_specific_prompt_tuning": False,
            "selection_evidence": False,
        },
        "stopping_and_authorization": {
            "if_first_scout_passes_stop_without_calibrating_later_scouts": True,
            "if_scout_fails_continue_only_to_next_prefrozen_load_qualified_scout": True,
            "if_no_prefrozen_scout_passes_freeze_negative_expansion_outcome_and_stop": True,
            "gate_lowering_authorized": False,
            "ad_hoc_candidate_replacement_authorized": False,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
            "selection_requires_expansion_outcome_freeze_with_at_least_four_eligible_candidates": True,
            "source_scout_freeze_authoring_authorized_after_green": True,
            "new_model_inference_authorized_by_this_protocol": False,
        },
    }


def validate_candidate_pool_v3_expansion_protocol() -> None:
    validate_candidate_pool_v3_calibration_outcome_freeze()
    payload = candidate_pool_v3_expansion_protocol_payload()

    if payload["predecessor_calibration_outcome_freeze_sha256"] != (
        FINAL_CANDIDATE_POOL_V3_CALIBRATION_OUTCOME_FREEZE_SHA256
    ):
        raise RuntimeError("v3 expansion predecessor outcome identity drifted")
    if tuple(payload["existing_eligible_candidate_ids"]) != (
        CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3
    ):
        raise RuntimeError("v3 expansion existing eligible population drifted")
    if payload["required_population_size"] != 4:
        raise RuntimeError("v3 expansion population size must remain four")
    if len(payload["existing_eligible_candidate_ids"]) != 3:
        raise RuntimeError("v3 expansion must begin with exactly three eligible candidates")
    if payload["additional_eligible_candidates_required"] != 1:
        raise RuntimeError("v3 expansion deficit must remain exactly one candidate")

    scouting = payload["scouting"]
    if scouting["scout_count"] != 3:
        raise RuntimeError("v3 expansion must predeclare exactly three scouts")
    if scouting["candidate_identities_bound_by_this_protocol"]:
        raise RuntimeError("protocol freeze must precede scout identity selection")
    if scouting["new_candidate_identity_observed_before_protocol_freeze"]:
        raise RuntimeError("new candidate identity was observed before protocol freeze")
    if scouting["new_candidate_calibration_outcome_observed_before_protocol_freeze"]:
        raise RuntimeError("new candidate outcome was observed before protocol freeze")
    if not scouting[
        "all_scout_ids_and_artifacts_frozen_together_before_new_model_inference"
    ]:
        raise RuntimeError("all scout identities must be source-frozen before inference")

    load = payload["load_qualification"]
    if load["formal_load_attempts_per_scout"] != 1:
        raise RuntimeError("v3 expansion load attempts must remain one per scout")
    if not load["full_gpu_offload_required"] or load["fit_mode"]:
        raise RuntimeError("v3 expansion load resource envelope drifted")
    if load["automatic_reruns"] or load["candidate_specific_runtime_tuning"]:
        raise RuntimeError("v3 expansion cannot authorize load retries or tuning")

    calibration = payload["calibration"]
    if calibration["required_parse_valid_count"] != 6:
        raise RuntimeError("v3 expansion parse-valid gate drifted")
    if calibration["minimum_solved_count"] != 4:
        raise RuntimeError("v3 expansion solved gate drifted")
    if calibration["max_candidates_calibrated"] != 3:
        raise RuntimeError("v3 expansion calibration candidate cap drifted")
    if calibration["max_candidate_task_calls"] != 18:
        raise RuntimeError("v3 expansion inference budget drifted")
    if not calibration["stop_after_first_gate_pass"]:
        raise RuntimeError("v3 expansion must stop after the first passing scout")
    if calibration["failed_candidate_rerun_authorized"]:
        raise RuntimeError("failed expansion candidates cannot be rerun")
    if calibration["candidate_specific_prompt_tuning"]:
        raise RuntimeError("candidate-specific task tuning remains forbidden")
    if calibration["selection_evidence"]:
        raise RuntimeError("expansion calibration cannot become selection evidence")

    authorization = payload["stopping_and_authorization"]
    forbidden = (
        "gate_lowering_authorized",
        "ad_hoc_candidate_replacement_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
        "new_model_inference_authorized_by_this_protocol",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("v3 expansion protocol improperly authorizes inference/selection")
    if not authorization["source_scout_freeze_authoring_authorized_after_green"]:
        raise RuntimeError("green protocol must authorize only source-scout freeze authoring")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256:
        raise RuntimeError("candidate-pool v3 expansion protocol identity drifted")


FINAL_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL = (
    candidate_pool_v3_expansion_protocol_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256 = (
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256
)

validate_candidate_pool_v3_expansion_protocol()
