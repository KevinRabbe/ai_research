from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective import local_raw_calibration as v1
from plural_cognition.collective import local_raw_calibration_v3 as v3


def test_v3_protocol_changes_only_output_transport_identity() -> None:
    base = v1.calibration_protocol_payload()
    payload = v3.calibration_protocol_payload_v2()
    for key, value in base.items():
        if key == "schema":
            continue
        assert payload[key] == value
    assert payload["schema"] == v3.PROTOCOL_SCHEMA_V2
    assert payload["assistant_output_channel"] == "llama-cli-output-file-single-turn-v1"
    assert payload["process_stdout_role"] == "diagnostic-only"
    assert payload["reasoning_role"] == "preserved-diagnostic-not-answer"
    assert payload["simple_io"] is True
    assert v3.CALIBRATION_PROTOCOL_SHA256_V2 != v1.CALIBRATION_PROTOCOL_SHA256


def test_extract_assistant_content_without_reasoning() -> None:
    prompt = b"repair this\n"
    transcript = b"User:\nrepair this\n\n\nAssistant:\n--- a/app.py\n+++ b/app.py\n\n"
    assistant, reasoning = v3.extract_assistant_content(
        transcript=transcript,
        prompt=prompt,
    )
    assert assistant == b"--- a/app.py\n+++ b/app.py"
    assert reasoning is None


def test_extract_assistant_content_separates_reasoning_and_normalizes_crlf() -> None:
    prompt = b"repair this\n"
    transcript = (
        b"User:\r\nrepair this\r\n\r\n\r\nAssistant:\r\n"
        b"[Start thinking]\r\n\r\nreason here\r\n"
        b"[End thinking]\r\n\r\n"
        b"```diff\r\n--- a/app.py\r\n+++ b/app.py\r\n```\r\n\r\n"
    )
    assistant, reasoning = v3.extract_assistant_content(
        transcript=transcript,
        prompt=prompt,
    )
    assert assistant == b"```diff\n--- a/app.py\n+++ b/app.py\n```"
    assert reasoning == b"reason here\n"


def test_extract_assistant_content_rejects_wrong_prompt_binding() -> None:
    with pytest.raises(ValueError, match="does not bind"):
        v3.extract_assistant_content(
            transcript=b"User:\nother\n\nAssistant:\nanswer\n\n",
            prompt=b"expected",
        )


def test_extract_assistant_content_rejects_unterminated_reasoning() -> None:
    with pytest.raises(ValueError, match="unterminated reasoning"):
        v3.extract_assistant_content(
            transcript=(
                b"User:\nrepair\n\nAssistant:\n"
                b"[Start thinking]\n\nreason without end\n\n"
            ),
            prompt=b"repair",
        )


def test_capture_command_adds_output_file_and_simple_io(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(v3, "_ACTIVE_ARTIFACT_ROOT", tmp_path)
    command = v3._load_command_capture(
        cli=Path("llama-cli.exe"),
        model_path=tmp_path / "qwen3-8b-q8" / "model.gguf",
        prompt=b"test prompt",
    )
    assert command.count("--simple-io") == 1
    assert command.count("--output-file") == 1
    capture = Path(command[command.index("--output-file") + 1])
    assert capture.parent == tmp_path / "llama-output" / "qwen3-8b-q8"
    assert capture.name.endswith(".transcript.txt")
    assert command[command.index("-p") + 1] == "test prompt"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-c") + 1] == str(v1.CALIBRATION_CONTEXT_TOKENS)
    assert command[command.index("-n") + 1] == str(v1.CALIBRATION_PREDICT_TOKENS)


def test_run_load_capture_returns_only_assistant_and_preserves_diagnostics(
    tmp_path: Path, monkeypatch
) -> None:
    capture = tmp_path / "capture.transcript.txt"
    capture.write_bytes(
        b"User:\nprompt\n\nAssistant:\n"
        b"[Start thinking]\n\nreason\n[End thinking]\n\nanswer\n\n"
    )
    command = (
        "llama-cli.exe",
        "--output-file",
        str(capture),
        "-p",
        "prompt",
    )
    sentinel = object()

    def fake_run_load(command_arg, *, timeout_seconds):
        assert command_arg == command
        assert timeout_seconds == 10
        return sentinel, b"UI banner and prompt echo", b"offload evidence"

    monkeypatch.setattr(v3, "_BASE_RUN_LOAD", fake_run_load)
    load, assistant, stderr = v3._run_load_capture(command, timeout_seconds=10)
    assert load is sentinel
    assert assistant == b"answer"
    assert stderr == b"offload evidence"
    assert capture.with_suffix(".process-stdout.bin").read_bytes() == b"UI banner and prompt echo"
    assert capture.with_suffix(".assistant.txt").read_bytes() == b"answer"
    assert capture.with_suffix(".reasoning.txt").read_bytes() == b"reason\n"


def test_output_manifest_hashes_sidecars(tmp_path: Path) -> None:
    output = tmp_path / "llama-output" / "candidate"
    output.mkdir(parents=True)
    (output / "a.assistant.txt").write_bytes(b"answer")
    v3._write_output_manifest(tmp_path)
    manifest = (tmp_path / "output-channel-manifest.json").read_text("ascii")
    assert v3.OUTPUT_MANIFEST_SCHEMA in manifest
    assert "a.assistant.txt" in manifest
    assert v3.CALIBRATION_PROTOCOL_SHA256_V2 in manifest
