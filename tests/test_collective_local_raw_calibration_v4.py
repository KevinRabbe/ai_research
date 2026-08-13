from __future__ import annotations

from pathlib import Path

from plural_cognition.collective import local_raw_calibration as v1
from plural_cognition.collective import local_raw_calibration_v3 as v3
from plural_cognition.collective import local_raw_calibration_v4 as v4
from plural_cognition.collective.repository_surgery_calibration_matrix import (
    calibration_blueprints,
)


def _boundary_blueprint():
    return next(
        item
        for item in calibration_blueprints()
        if item.task_id == "repository-surgery-calibration-boundary-0001"
    )


def test_v4_protocol_preserves_raw_condition_and_freezes_literal_transport() -> None:
    base = v1.calibration_protocol_payload()
    payload = v4.calibration_protocol_payload_v3()
    for key, value in base.items():
        if key == "schema":
            continue
        assert payload[key] == value
    assert payload["schema"] == v4.PROTOCOL_SCHEMA_V3
    assert payload["assistant_output_channel"] == "llama-cli-output-file-single-turn-v1"
    assert payload["process_stdout_role"] == "diagnostic-only"
    assert payload["reasoning_role"] == "preserved-diagnostic-not-answer"
    assert payload["simple_io"] is True
    assert payload["prompt_transport"] == "literal-argv-no-escape-v1"
    assert payload["escape_processing"] is False
    assert payload["terminal_prompt_lf"] is False
    assert v4.CALIBRATION_PROTOCOL_SHA256_V3 != v3.CALIBRATION_PROTOCOL_SHA256_V2


def test_v4_prompt_identity_matches_runtime_user_message_bytes() -> None:
    blueprint = _boundary_blueprint()
    base = v1.build_solver_prompt(blueprint)
    prompt = v4.build_solver_prompt_literal(blueprint)

    assert base.endswith(b"\n")
    assert prompt == base[:-1]
    assert not prompt.endswith(b"\n")
    # Solver-visible source contains a literal Python backslash-n sequence.  It
    # must remain two bytes in the prompt rather than becoming a newline.
    assert b'+ "\\n")' in prompt


def test_v4_capture_command_disables_escape_processing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(v3, "_ACTIVE_ARTIFACT_ROOT", tmp_path)
    command = v4._load_command_literal_capture(
        cli=Path("llama-cli.exe"),
        model_path=tmp_path / "qwen3-8b-q8" / "model.gguf",
        prompt=b'code = "\\n"',
    )

    assert command.count("--no-escape") == 1
    assert "--escape" not in command
    assert command.count("--simple-io") == 1
    assert command.count("--output-file") == 1
    assert command[command.index("-p") + 1] == 'code = "\\n"'
    assert command.index("--no-escape") < command.index("-p")


def test_v3_output_parser_accepts_literal_v4_prompt_binding() -> None:
    prompt = b'code = "\\n"'
    transcript = (
        b'User:\r\ncode = "\\n"\r\n\r\nAssistant:\r\n'
        b'```diff\r\n--- a/app.py\r\n+++ b/app.py\r\n```\r\n\r\n'
    )

    assistant, reasoning = v3.extract_assistant_content(
        transcript=transcript,
        prompt=prompt,
    )

    assert assistant == b"```diff\n--- a/app.py\n+++ b/app.py\n```"
    assert reasoning is None
