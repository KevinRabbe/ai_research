from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plural_cognition.collective.local_model_load_preflight import (
    OFFLOAD_PATTERN,
    REPORT_SCHEMA,
    _load_command,
    _verify_exact_file,
)
from plural_cognition.collective.local_models import LOCAL_MODEL_SOURCE_FREEZE_V2


def test_load_command_freezes_single_gpu_full_offload_and_context() -> None:
    command = _load_command(
        Path("C:/runtime/llama-cli.exe"),
        Path("C:/models/Qwen3-8B-Q8_0.gguf"),
        context_tokens=4096,
        predict_tokens=32,
    )
    assert command[:3] == (
        "C:/runtime/llama-cli.exe",
        "-m",
        "C:/models/Qwen3-8B-Q8_0.gguf",
    )
    assert ("-c", "4096") == command[3:5]
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-sm") + 1] == "none"
    assert command[command.index("-mg") + 1] == "0"
    assert command[command.index("-ctk") + 1] == "f16"
    assert command[command.index("-ctv") + 1] == "f16"
    assert command[command.index("-lm") + 1] == "mmap"
    assert "--offline" in command
    assert command[command.index("--temp") + 1] == "0"
    assert command[command.index("--seed") + 1] == "1"
    assert "-st" in command


def test_offload_log_pattern_captures_full_layer_counts() -> None:
    match = OFFLOAD_PATTERN.search(
        "llama_model_load: offloaded 37/37 layers to GPU"
    )
    assert match is not None
    assert match.groups() == ("37", "37")


def test_exact_file_verifier_accepts_expected_content(tmp_path: Path) -> None:
    path = tmp_path / "artifact.gguf"
    content = b"frozen-artifact"
    path.write_bytes(content)
    _verify_exact_file(
        path,
        size_bytes=len(content),
        expected_sha256=hashlib.sha256(content).hexdigest(),
    )


def test_exact_file_verifier_rejects_size_drift(tmp_path: Path) -> None:
    path = tmp_path / "artifact.gguf"
    path.write_bytes(b"abc")
    with pytest.raises(RuntimeError, match="size mismatch"):
        _verify_exact_file(
            path,
            size_bytes=4,
            expected_sha256=hashlib.sha256(b"abc").hexdigest(),
        )


def test_exact_file_verifier_rejects_hash_drift(tmp_path: Path) -> None:
    path = tmp_path / "artifact.gguf"
    path.write_bytes(b"abc")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        _verify_exact_file(
            path,
            size_bytes=3,
            expected_sha256=hashlib.sha256(b"different").hexdigest(),
        )


def test_first_load_candidate_is_frozen_qwen3_q8() -> None:
    candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate("qwen3-8b-q8")
    assert candidate.filename == "Qwen3-8B-Q8_0.gguf"
    assert candidate.size_bytes == 8_709_518_112
    assert candidate.artifact_sha256 == (
        "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6"
    )
    assert REPORT_SCHEMA == "plural-cognition-local-model-load-preflight-v1"
