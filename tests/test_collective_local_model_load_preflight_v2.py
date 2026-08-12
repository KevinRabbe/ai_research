from __future__ import annotations

from pathlib import Path

from plural_cognition.collective.local_model_load_preflight_v2 import (
    LOG_VERBOSITY,
    REPORT_SCHEMA,
    _load_command,
)


def test_v2_load_command_exposes_offload_evidence() -> None:
    command = _load_command(
        Path("C:/runtime/llama-cli.exe"),
        Path("C:/models/Qwen3-8B-Q8_0.gguf"),
        context_tokens=4096,
        predict_tokens=32,
    )
    assert REPORT_SCHEMA == "plural-cognition-local-model-load-preflight-v2"
    assert LOG_VERBOSITY == 4
    assert command[command.index("--log-verbosity") + 1] == "4"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-c") + 1] == "4096"
    assert command[command.index("-n") + 1] == "32"
    assert command[command.index("--temp") + 1] == "0"
    assert command[command.index("--seed") + 1] == "1"


def test_v2_delta_from_v1_is_explicit_log_verbosity() -> None:
    from plural_cognition.collective.local_model_load_preflight import (
        _load_command as v1_load_command,
    )

    v1 = v1_load_command(
        Path("C:/runtime/llama-cli.exe"),
        Path("C:/models/Qwen3-8B-Q8_0.gguf"),
        context_tokens=4096,
        predict_tokens=32,
    )
    v2 = _load_command(
        Path("C:/runtime/llama-cli.exe"),
        Path("C:/models/Qwen3-8B-Q8_0.gguf"),
        context_tokens=4096,
        predict_tokens=32,
    )

    assert "--log-verbosity" not in v1
    idx = v2.index("--log-verbosity")
    assert v2[idx : idx + 2] == ("--log-verbosity", "4")
    assert v2[:idx] + v2[idx + 2 :] == v1
