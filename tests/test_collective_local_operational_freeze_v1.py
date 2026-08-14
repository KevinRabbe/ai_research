from dataclasses import replace

import pytest

from plural_cognition.collective.local_operational_freeze_v1 import (
    FINAL_CALIBRATION_EVIDENCE_SHA256,
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
    FINAL_OUTPUT_CONTRACT_SHA256,
    FINAL_PROMPT_PROTOCOL_SHA256,
    FINAL_RAW_MIND_PROTOCOL,
    FINAL_RESOURCE_BUDGET_SHA256,
    V8_REPORT_SHA256,
    V9_REPORT_SHA256,
    final_calibration_evidence_payload,
)


def test_final_freeze_binds_completed_calibration_evidence() -> None:
    payload = final_calibration_evidence_payload()
    assert payload["v8_matrix"]["report_sha256"] == V8_REPORT_SHA256
    assert payload["v8_matrix"]["result_count"] == 30
    assert payload["v8_matrix"]["parsed_count"] == 24
    assert payload["v8_matrix"]["solved_count"] == 20
    assert payload["v9_gemma_probe"]["report_sha256"] == V9_REPORT_SHA256
    assert payload["v9_gemma_probe"]["parsed_count"] == 0
    assert payload["v9_gemma_probe"]["decision"] == "reject-gemma-4096-override-retain-shared-2048-v1"
    assert len(FINAL_CALIBRATION_EVIDENCE_SHA256) == 64


def test_final_freeze_preserves_all_five_candidates_without_calibration_selection() -> None:
    freeze = FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
    freeze.validate_against()
    assert freeze.candidate_ids == FINAL_CANDIDATE_IDS
    assert len(freeze.configs) == 5
    assert len({config.sha256 for config in freeze.configs}) == 5


def test_final_protocol_matches_observed_v8_runtime_knobs() -> None:
    protocol = FINAL_RAW_MIND_PROTOCOL
    assert protocol.context_tokens == 4096
    assert protocol.predict_tokens == 2048
    assert protocol.cpu_threads == 16
    assert protocol.cpu_threads_batch == 16
    assert protocol.batch_tokens == 2048
    assert protocol.microbatch_tokens == 512
    assert protocol.flash_attention_mode == "auto"
    assert protocol.temperature == 0.0
    assert protocol.seed == 1
    assert protocol.max_attempts == 1
    assert protocol.cross_mind_communication is False
    assert protocol.evaluator_access is False
    assert protocol.mutable_memory is False
    assert protocol.plural_synthesis is False


def test_every_candidate_binds_same_frozen_prompt_output_and_resource_contracts() -> None:
    for config in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs:
        config.validate_against()
        assert config.prompt_protocol_sha256 == FINAL_PROMPT_PROTOCOL_SHA256
        assert config.output_contract_sha256 == FINAL_OUTPUT_CONTRACT_SHA256
        assert config.resource_budget_sha256 == FINAL_RESOURCE_BUDGET_SHA256
        assert config.protocol == FINAL_RAW_MIND_PROTOCOL
        assert config.mind_identity().configuration_sha256 == config.sha256


def test_final_freeze_rejects_post_calibration_resource_drift() -> None:
    config = FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs[0]
    drifted = replace(config, protocol=replace(config.protocol, predict_tokens=4096))
    with pytest.raises(ValueError, match="raw protocol drifted"):
        drifted.validate_against()


def test_flash_attention_freezes_requested_auto_mode_not_observed_fallback() -> None:
    assert FINAL_RAW_MIND_PROTOCOL.flash_attention_mode == "auto"
    with pytest.raises(ValueError, match="auto, on, or off"):
        replace(FINAL_RAW_MIND_PROTOCOL, flash_attention_mode="enabled")
