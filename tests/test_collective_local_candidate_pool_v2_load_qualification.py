from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plural_cognition.collective.local_candidate_pool_v2_load_qualification import (
    CHALLENGER_IDS_V2,
    EXPECTED_LOAD_PLAN_SHA256_V2,
    FINAL_LOAD_PLAN_SHA256_V2,
    LOAD_CONTEXT_TOKENS_V2,
    LOAD_PREDICT_TOKENS_V2,
    _candidate_load_failure,
    _challengers,
    _verify_challenger_file,
    load_qualification_plan_payload_v2,
)
from plural_cognition.collective.local_model_load_preflight import _load_command


def test_v2_load_plan_identity_and_exact_three_candidates() -> None:
    payload = load_qualification_plan_payload_v2()
    assert FINAL_LOAD_PLAN_SHA256_V2 == EXPECTED_LOAD_PLAN_SHA256_V2
    assert tuple(payload["challenger_ids"]) == CHALLENGER_IDS_V2
    assert payload["load_probe"]["attempts_per_challenger"] == 1
    assert payload["load_probe"]["full_gpu_offload_required"] is True
    assert payload["evidence_policy"]["completed_report_reused_without_inference"] is True
    assert payload["evidence_policy"]["partial_attempt_blocks_rerun"] is True
    assert payload["evidence_policy"]["artifact_substitution_after_outcome"] is False
    assert payload["evidence_policy"]["selection_evidence"] is False


def test_v2_load_probe_reuses_formal_single_gpu_command() -> None:
    command = _load_command(
        Path("C:/runtime/llama-cli.exe"),
        Path("C:/models/model.gguf"),
        context_tokens=LOAD_CONTEXT_TOKENS_V2,
        predict_tokens=LOAD_PREDICT_TOKENS_V2,
    )
    assert command[command.index("-c") + 1] == "4096"
    assert command[command.index("-n") + 1] == "32"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-sm") + 1] == "none"
    assert command[command.index("-mg") + 1] == "0"
    assert command[command.index("--temp") + 1] == "0"
    assert command[command.index("--seed") + 1] == "1"
    assert "--offline" in command


def test_v2_challenger_file_verifier_accepts_hash_and_optional_size(tmp_path: Path) -> None:
    raw = b"frozen-challenger"
    path = tmp_path / "candidate.gguf"
    path.write_bytes(raw)
    candidate = {
        "candidate_id": "test-candidate",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_size_bytes": None,
    }
    digest, size = _verify_challenger_file(path, candidate)
    assert digest == candidate["artifact_sha256"]
    assert size == len(raw)
    candidate["artifact_size_bytes"] = len(raw)
    assert _verify_challenger_file(path, candidate) == (digest, len(raw))


def test_v2_challenger_file_verifier_rejects_size_or_hash_drift(tmp_path: Path) -> None:
    path = tmp_path / "candidate.gguf"
    path.write_bytes(b"abc")
    with pytest.raises(RuntimeError, match="size mismatch"):
        _verify_challenger_file(
            path,
            {
                "candidate_id": "x",
                "artifact_sha256": hashlib.sha256(b"abc").hexdigest(),
                "artifact_size_bytes": 4,
            },
        )
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        _verify_challenger_file(
            path,
            {
                "candidate_id": "x",
                "artifact_sha256": hashlib.sha256(b"different").hexdigest(),
                "artifact_size_bytes": None,
            },
        )


def test_v2_failure_classifier_separates_candidate_outcome_from_infrastructure() -> None:
    for message in (
        "llama-cli load/generation failed with exit 1: unsupported model",
        "llama-cli load/generation exceeded 900 seconds",
        "llama-cli produced no generated stdout",
        "llama-cli log did not prove GPU layer offload",
        "model was not fully offloaded to GPU: 20/30 layers",
    ):
        assert _candidate_load_failure(RuntimeError(message)) is True
    assert _candidate_load_failure(RuntimeError("resource monitor failed: nvidia-smi")) is False


def test_v2_source_freeze_challenger_paths_are_fixed() -> None:
    challengers = _challengers()
    assert tuple(challengers) == CHALLENGER_IDS_V2
    assert challengers["gpt-oss-20b-mxfp4"]["filename"] == "gpt-oss-20b-MXFP4.gguf"
    assert challengers["phi-4-reasoning-plus-14b-q5km"]["filename"].endswith("Q5_K_M.gguf")
    assert challengers["devstral-small-2-24b-q4km"]["filename"].endswith("Q4_K_M.gguf")
