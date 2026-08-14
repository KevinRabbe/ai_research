from __future__ import annotations

from pathlib import Path

from plural_cognition.collective.local_operational_freeze_v1 import (
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
    FINAL_RAW_MIND_PROTOCOL,
    FINAL_RESOURCE_BUDGET_SHA256,
)
from plural_cognition.collective.local_selection_bakeoff_v1 import (
    _candidate_models,
    _load_command,
    _solver_prompt,
)
from plural_cognition.collective.repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
)
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def _value(command: tuple[str, ...], flag: str) -> str:
    assert command.count(flag) == 1
    return command[command.index(flag) + 1]


def test_candidate_models_are_exactly_the_final_frozen_population() -> None:
    candidates = _candidate_models()
    assert tuple(item.candidate_id for item in candidates) == FINAL_CANDIDATE_IDS
    assert tuple(item.mind.configuration_sha256 for item in candidates) == tuple(
        item.sha256 for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs
    )
    assert all(item.context_tokens == 4096 for item in candidates)
    assert FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256 == (
        "7dea54974ee3ee86fedbac1b5ed85bffbe8dee6a31ee325cda2fc03c748c41d1"
    )


def test_selection_prompt_uses_frozen_v8_content_and_v4_terminal_lf_transport() -> None:
    prompt = _solver_prompt(selection_blueprints()[0])
    assert b"OUTPUT SCHEMA:" in prompt
    assert not prompt.endswith(b"\n")


def test_selection_command_explicitly_binds_final_resource_settings(tmp_path: Path) -> None:
    command = _load_command(
        cli=tmp_path / "llama-cli.exe",
        model_path=tmp_path / "model.gguf",
        prompt=b"prompt",
        capture=tmp_path / "answer.txt",
    )
    protocol = FINAL_RAW_MIND_PROTOCOL
    assert _value(command, "-c") == str(protocol.context_tokens) == "4096"
    assert _value(command, "-n") == str(protocol.predict_tokens) == "2048"
    assert _value(command, "-t") == str(protocol.cpu_threads) == "16"
    assert _value(command, "-tb") == str(protocol.cpu_threads_batch) == "16"
    assert _value(command, "-b") == str(protocol.batch_tokens) == "2048"
    assert _value(command, "-ub") == str(protocol.microbatch_tokens) == "512"
    assert _value(command, "-fa") == protocol.flash_attention_mode == "auto"
    assert _value(command, "--seed") == "1"
    assert _value(command, "--temp") == "0.0"
    assert "--offline" in command
    assert "-cnv" in command
    assert "--simple-io" in command
    assert "--no-escape" in command
    assert "-st" in command
    assert FINAL_RESOURCE_BUDGET_SHA256 == (
        "5508ba6ff0f093fd4cf10505513c41951bb1d454992fe6bb13a48bae83c803f7"
    )
