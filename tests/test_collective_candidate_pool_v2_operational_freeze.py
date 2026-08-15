from __future__ import annotations

from plural_cognition.collective import candidate_pool_v2_operational_freeze as freeze


def test_v2_operational_freeze_identity_and_population() -> None:
    payload = freeze.candidate_pool_v2_operational_freeze_payload()
    assert freeze.FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256 == freeze.EXPECTED_OPERATIONAL_FREEZE_SHA256_V2
    assert freeze.FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256 == "9fabeaaed55d4dfd8a500dec5346450cf5a497ed8f7fb3a65d5fec6b2307380b"
    assert tuple(payload["calibration"]["eligible_candidate_ids"]) == freeze.FINAL_CANDIDATE_IDS_V2
    assert tuple(payload["calibration"]["eliminated_candidate_ids"]) == freeze.ELIMINATED_CANDIDATE_IDS_V2
    assert freeze.ELIMINATED_CANDIDATE_IDS_V2 == ("phi-4-reasoning-plus-14b-q5km",)
    assert len(freeze.FINAL_CANDIDATE_IDS_V2) == 5
    assert "phi-4-reasoning-plus-14b-q5km" not in freeze.FINAL_CANDIDATE_IDS_V2


def test_v2_operational_freeze_binds_completed_calibration_and_selection_rule() -> None:
    payload = freeze.candidate_pool_v2_operational_freeze_payload()
    calibration = payload["calibration"]
    assert calibration["software_revision"] == "bf12017cbd288ac52fb9ff674ca998bc0073068e"
    assert calibration["suite_file_sha256"] == "1b7b60ee662213af0ab4bf0f80eb90d848aa5bd215b19cd90a696aca34ad84ff"
    assert calibration["suite_report_sha256"] == "b779a411f0b809c40cea1a4b3ecd635a1856fe68ab6741cff11b4396f01bffdc"
    assert calibration["pair_count"] == 36
    assert calibration["selection_evidence"] is False
    selection = payload["selection_v2"]
    assert selection == {
        "task_count": 12,
        "min_valid_rate": 0.95,
        "population_size": 4,
        "selection_run_count": 1,
        "threshold_lowering_after_outcome": False,
        "requires_fresh_untouched_pack": True,
    }


def test_v2_operational_freeze_preserves_exact_execution_contract() -> None:
    execution = freeze.candidate_pool_v2_operational_freeze_payload()["execution_protocol"]
    assert execution["output_contract"] == "raw-full-file-replacement-v1"
    assert execution["candidate_output_interpreter"] == "deterministic-full-file-unified-diff-v1"
    assert execution["self_review"] is False
    assert execution["candidate_output_repair"] is False
    assert execution["fuzzy_matching"] is False
    assert execution["max_attempts"] == 1
