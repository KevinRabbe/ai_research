from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from plural_cognition.collective.local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from plural_cognition.collective.local_operational_config import (
    LOCAL_CANDIDATE_OPERATIONAL_CONFIG_SCHEMA,
    LOCAL_OPERATIONAL_CONFIG_FREEZE_SCHEMA,
    LOCAL_RAW_PROTOCOL_SCHEMA,
    LocalCandidateOperationalConfig,
    LocalOperationalConfigFreeze,
    LocalRawMindProtocol,
)


def _digest(label: str) -> str:
    return sha256(label.encode("ascii")).hexdigest()


def _protocol() -> LocalRawMindProtocol:
    return LocalRawMindProtocol(
        context_tokens=4096,
        predict_tokens=1024,
        device="CUDA0",
        gpu_layers="all",
        fit="off",
        split_mode="none",
        main_gpu=0,
        cache_type_k="f16",
        cache_type_v="f16",
        load_mode="mmap",
        offline=True,
        temperature=0,
        seed=1,
        log_verbosity=4,
        cpu_threads=12,
        batch_tokens=512,
        microbatch_tokens=128,
        flash_attention=True,
    )


def _config(candidate_id: str = "qwen3-8b-q8") -> LocalCandidateOperationalConfig:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    source = freeze.candidate(candidate_id)
    return LocalCandidateOperationalConfig(
        candidate_id=candidate_id,
        model_source_freeze_sha256=freeze.sha256,
        model_source_sha256=source.sha256,
        runtime_sha256=freeze.runtime.sha256,
        protocol=_protocol(),
        prompt_protocol_sha256=_digest(f"prompt:{candidate_id}"),
        output_contract_sha256=_digest("unified-diff-output-v1"),
        resource_budget_sha256=_digest("raw-budget-v1"),
    )


def test_raw_protocol_is_content_addressed_and_explicit() -> None:
    protocol = _protocol()
    payload = protocol.canonical_payload()
    assert payload["schema"] == LOCAL_RAW_PROTOCOL_SCHEMA
    assert payload["single_turn"] is True
    assert payload["max_attempts"] == 1
    assert payload["cross_mind_communication"] is False
    assert payload["evaluator_access"] is False
    assert payload["mutable_memory"] is False
    assert payload["plural_synthesis"] is False
    assert len(protocol.sha256) == 64


def test_candidate_config_binds_exact_frozen_model_and_runtime() -> None:
    config = _config()
    config.validate_against()
    payload = config.canonical_payload()
    assert payload["schema"] == LOCAL_CANDIDATE_OPERATIONAL_CONFIG_SCHEMA
    assert payload["model_source_freeze_sha256"] == LOCAL_MODEL_SOURCE_FREEZE_V2.sha256
    assert payload["model_source_sha256"] == (
        LOCAL_MODEL_SOURCE_FREEZE_V2.candidate("qwen3-8b-q8").sha256
    )
    assert payload["runtime_sha256"] == LOCAL_MODEL_SOURCE_FREEZE_V2.runtime.sha256


def test_candidate_config_constructs_exact_mind_identity() -> None:
    config = _config("deepseek-coder-v2-lite-q5km")
    mind = config.mind_identity()
    source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(
        "deepseek-coder-v2-lite-q5km"
    )
    assert mind.mind_id == "deepseek-coder-v2-lite-q5km"
    assert mind.model_revision == source.artifact_sha256
    assert mind.configuration_sha256 == config.sha256
    assert "llama.cpp-b10361-cuda-12.4" == mind.backend_family


def test_operational_freeze_validates_candidate_bindings() -> None:
    configs = (_config("qwen3-8b-q8"), _config("gemma4-12b-it-qat-q4"))
    freeze = LocalOperationalConfigFreeze(
        model_source_freeze_sha256=LOCAL_MODEL_SOURCE_FREEZE_V2.sha256,
        calibration_evidence_sha256=_digest("calibration-evidence"),
        configs=configs,
    )
    freeze.validate_against()
    assert freeze.canonical_payload()["schema"] == LOCAL_OPERATIONAL_CONFIG_FREEZE_SCHEMA
    assert freeze.candidate_ids == ("qwen3-8b-q8", "gemma4-12b-it-qat-q4")
    assert freeze.config("gemma4-12b-it-qat-q4") == configs[1]
    assert len(freeze.sha256) == 64


def test_raw_protocol_rejects_retries_and_privileged_channels() -> None:
    protocol = _protocol()
    with pytest.raises(ValueError, match="exactly one primary attempt"):
        replace(protocol, max_attempts=2)
    with pytest.raises(ValueError, match="cannot communicate"):
        replace(protocol, cross_mind_communication=True)
    with pytest.raises(ValueError, match="protected evaluators"):
        replace(protocol, evaluator_access=True)
    with pytest.raises(ValueError, match="mutable memory"):
        replace(protocol, mutable_memory=True)
    with pytest.raises(ValueError, match="plural synthesis"):
        replace(protocol, plural_synthesis=True)


def test_candidate_config_fails_closed_on_model_or_runtime_drift() -> None:
    config = _config()
    with pytest.raises(ValueError, match="model-source identity drifted"):
        replace(config, model_source_sha256=_digest("wrong-source")).validate_against()
    with pytest.raises(ValueError, match="runtime identity drifted"):
        replace(config, runtime_sha256=_digest("wrong-runtime")).validate_against()


def test_operational_freeze_rejects_duplicate_candidate_ids() -> None:
    config = _config()
    with pytest.raises(ValueError, match="candidate IDs must be unique"):
        LocalOperationalConfigFreeze(
            model_source_freeze_sha256=LOCAL_MODEL_SOURCE_FREEZE_V2.sha256,
            calibration_evidence_sha256=_digest("calibration-evidence"),
            configs=(config, config),
        )


def test_operational_freeze_does_not_exist_until_calibration_is_bound() -> None:
    with pytest.raises(ValueError):
        LocalOperationalConfigFreeze(
            model_source_freeze_sha256=LOCAL_MODEL_SOURCE_FREEZE_V2.sha256,
            calibration_evidence_sha256="not-a-digest",
            configs=(_config(),),
        )
