from __future__ import annotations

import hashlib
import json

from plural_cognition.collective import candidate_pool_v3_expansion_protocol as protocol


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def test_v3_expansion_protocol_has_exact_canonical_identity() -> None:
    payload = protocol.candidate_pool_v3_expansion_protocol_payload()
    assert _digest(payload) == protocol.EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256
    assert _digest(payload) == (
        "2ac18170b0dc5a1708f3974816dafdd28fa092f01d8170afc0e85d65dcbae4fc"
    )


def test_v3_expansion_protocol_binds_negative_calibration_outcome_and_deficit() -> None:
    payload = protocol.candidate_pool_v3_expansion_protocol_payload()
    assert payload["predecessor_calibration_outcome_revision"] == (
        "5433bc8d561ad025632e1af0b4658b8d37852fe9"
    )
    assert payload["predecessor_calibration_outcome_freeze_sha256"] == (
        "b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56"
    )
    assert payload["existing_eligible_candidate_ids"] == [
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    ]
    assert payload["required_population_size"] == 4
    assert payload["additional_eligible_candidates_required"] == 1


def test_v3_expansion_protocol_freezes_scouting_before_any_new_model_inference() -> None:
    scouting = protocol.candidate_pool_v3_expansion_protocol_payload()["scouting"]
    assert scouting["scout_count"] == 3
    assert scouting["candidate_identities_bound_by_this_protocol"] is False
    assert scouting["new_candidate_identity_observed_before_protocol_freeze"] is False
    assert scouting["new_candidate_calibration_outcome_observed_before_protocol_freeze"] is False
    assert scouting["new_artifact_identity_required"] is True
    assert scouting["previously_measured_candidate_artifact_reuse_forbidden"] is True
    assert scouting[
        "all_scout_ids_and_artifacts_frozen_together_before_new_model_inference"
    ] is True
    assert scouting["ordered_scout_list_frozen_before_new_model_inference"] is True


def test_v3_expansion_protocol_load_qualification_is_one_attempt_and_untuned() -> None:
    load = protocol.candidate_pool_v3_expansion_protocol_payload()["load_qualification"]
    assert load["formal_load_attempts_per_scout"] == 1
    assert load["load_only_no_capability_prompt"] is True
    assert load["full_gpu_offload_required"] is True
    assert load["fit_mode"] is False
    assert load["load_failure_terminal_for_frozen_artifact"] is True
    assert load["automatic_reruns"] is False
    assert load["candidate_specific_runtime_tuning"] is False
    assert load["load_outcome_freeze_required_before_calibration_inference"] is True


def test_v3_expansion_protocol_uses_sequential_minimal_calibration_budget() -> None:
    calibration = protocol.candidate_pool_v3_expansion_protocol_payload()["calibration"]
    assert calibration["task_ids_reused_from_completed_v3_development_calibration"] is True
    assert calibration["task_material_may_not_influence_scout_selection"] is True
    assert calibration["task_count_per_candidate"] == 6
    assert calibration["required_parse_valid_count"] == 6
    assert calibration["minimum_solved_count"] == 4
    assert calibration["ordered_sequential_evaluation"] is True
    assert calibration["max_candidates_calibrated"] == 3
    assert calibration["max_candidate_task_calls"] == 18
    assert calibration["stop_after_first_gate_pass"] is True
    assert calibration["max_attempts_per_pair"] == 1
    assert calibration["failed_candidate_rerun_authorized"] is False
    assert calibration["candidate_specific_prompt_tuning"] is False
    assert calibration["selection_evidence"] is False


def test_v3_expansion_protocol_authorizes_only_next_source_freeze_authoring() -> None:
    authorization = protocol.candidate_pool_v3_expansion_protocol_payload()[
        "stopping_and_authorization"
    ]
    assert authorization["source_scout_freeze_authoring_authorized_after_green"] is True
    assert authorization["new_model_inference_authorized_by_this_protocol"] is False
    assert authorization["gate_lowering_authorized"] is False
    assert authorization["ad_hoc_candidate_replacement_authorized"] is False
    assert authorization["selection_pack_authoring_authorized"] is False
    assert authorization["selection_inference_authorized"] is False
    assert authorization["plural_synthesis_authorized"] is False
