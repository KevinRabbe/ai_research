from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from plural_cognition.collective.local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from plural_cognition.collective.local_raw_calibration import (
    CALIBRATION_CONTEXT_TOKENS,
    CALIBRATION_LOG_VERBOSITY,
    CALIBRATION_PREDICT_TOKENS,
    CALIBRATION_PROTOCOL_SHA256,
    _candidate_probe_configuration_sha256,
    _load_command,
    _selected_blueprints,
    build_solver_prompt,
    calibration_protocol_payload,
    extract_unified_diff,
    validate_patch_against_blueprint,
)
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration_matrix import (
    CalibrationBlueprint,
    calibration_blueprints,
)


def _blueprint() -> CalibrationBlueprint:
    return CalibrationBlueprint(
        task_id="repository-surgery-calibration-test-0001",
        mutation_kind=MutationKind.LOCAL_LOGIC,
        generation_seed=99,
        clean_files=(("app.py", b"print('clean-secret')\n"),),
        buggy_files=(("app.py", b"print('buggy-visible')\n"),),
        gold_patch=(
            b"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
            b"-print('buggy-visible')\n+print('gold-secret')\n"
        ),
        issue_prompt=b"Repair the visible bug and return a unified diff only.\n",
        public_cases=(
            {"input": {"visible": 1}, "expected": {"visible": 2}},
        ),
        protected_cases=(
            (
                "case-secret",
                {"protected-input-secret": 7},
                {"protected-expectation-secret": 8},
            ),
        ),
        mutation_configuration={"secret-mutation-config": True},
    )


def test_solver_prompt_contains_only_solver_visible_calibration_material() -> None:
    prompt = build_solver_prompt(_blueprint()).decode("utf-8")
    assert "buggy-visible" in prompt
    assert "Repair the visible bug" in prompt
    assert '"visible":1' in prompt
    assert "clean-secret" not in prompt
    assert "gold-secret" not in prompt
    assert "protected-input-secret" not in prompt
    assert "protected-expectation-secret" not in prompt
    assert "secret-mutation-config" not in prompt


def test_raw_unified_diff_is_accepted() -> None:
    raw = (
        b"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        b"-print('bad')\n+print('good')\n"
    )
    patch, mode = extract_unified_diff(raw)
    assert patch == raw
    assert mode == "raw-diff"


def test_git_style_unified_diff_metadata_is_accepted() -> None:
    raw = (
        b"diff --git a/app.py b/app.py\n"
        b"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        b"-print('bad')\n+print('good')\n"
    )
    patch, mode = extract_unified_diff(raw)
    assert patch == raw
    assert mode == "raw-diff"


def test_single_diff_fence_is_accepted_and_removed() -> None:
    raw = (
        b"```diff\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        b"-print('bad')\n+print('good')\n```\n"
    )
    patch, mode = extract_unified_diff(raw)
    assert patch.startswith(b"--- a/app.py\n")
    assert patch.endswith(b"+print('good')\n")
    assert b"```" not in patch
    assert mode == "diff-fence"


@pytest.mark.parametrize(
    "raw, match",
    [
        (
            b"Here is the patch:\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-a\n+b\n",
            "does not begin",
        ),
        (b"```python\nprint('x')\n```", "unsupported markdown"),
        (
            b"--- a/../escape.py\n+++ b/../escape.py\n@@ -1 +1 @@\n-a\n+b\n",
            "unsafe components",
        ),
        (
            b"--- C:/escape.py\n+++ C:/escape.py\n@@ -1 +1 @@\n-a\n+b\n",
            "unsafe components",
        ),
        (
            b"--- a/app.py\n+++ b/app.py\n-a\n+b\n",
            "at least one hunk",
        ),
        (
            b"--- a/app.py\n+++ b/app.py\n@@ -1,2 +1 @@\n-a\n+b\n",
            "hunk counts",
        ),
    ],
)
def test_invalid_or_unsafe_model_output_is_rejected(raw: bytes, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        extract_unified_diff(raw)


def test_patch_context_is_validated_against_solver_visible_repository() -> None:
    blueprint = _blueprint()
    valid = (
        b"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        b"-print('buggy-visible')\n+print('fixed')\n"
    )
    validate_patch_against_blueprint(valid, blueprint)

    wrong_context = (
        b"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        b"-print('not-in-repository')\n+print('fixed')\n"
    )
    with pytest.raises(ValueError, match="context does not match"):
        validate_patch_against_blueprint(wrong_context, blueprint)


def test_calibration_probe_rejects_file_creation_before_docker() -> None:
    patch = (
        b"--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n"
        b"+print('new')\n"
    )
    with pytest.raises(ValueError, match="file creation or deletion"):
        validate_patch_against_blueprint(patch, _blueprint())


def test_task_filter_can_select_only_existing_calibration_tasks() -> None:
    first = calibration_blueprints()[0]
    assert _selected_blueprints((first.task_id,)) == (first,)
    with pytest.raises(ValueError, match="not a frozen calibration task"):
        _selected_blueprints(("selection-task-0001",))
    with pytest.raises(ValueError, match="task IDs must be unique"):
        _selected_blueprints((first.task_id, first.task_id))


def test_calibration_protocol_preserves_raw_mind_boundary() -> None:
    payload = calibration_protocol_payload()
    assert len(CALIBRATION_PROTOCOL_SHA256) == 64
    assert payload["task_split"] == "calibration-only"
    assert payload["context_tokens"] == 4096
    assert payload["predict_tokens"] == 2048
    assert payload["gpu_layers"] == "all"
    assert payload["device"] == "CUDA0"
    assert payload["offline"] is True
    assert payload["single_turn"] is True
    assert payload["conversation_mode"] is True
    assert payload["max_attempts"] == 1
    assert payload["cross_mind_communication"] is False
    assert payload["evaluator_access"] is False
    assert payload["mutable_memory"] is False
    assert payload["plural_synthesis"] is False
    assert payload["patch_validation"] == "qualified-docker-unified-diff-grammar-v1"


def test_llama_command_is_single_turn_offline_full_offload_chat() -> None:
    candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidates[0]
    command = _load_command(
        cli=Path("llama-cli.exe"),
        model_path=Path(candidate.filename),
        prompt=b"test prompt",
    )
    assert command[command.index("-c") + 1] == str(CALIBRATION_CONTEXT_TOKENS)
    assert command[command.index("-n") + 1] == str(CALIBRATION_PREDICT_TOKENS)
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("--log-verbosity") + 1] == str(
        CALIBRATION_LOG_VERBOSITY
    )
    assert "--offline" in command
    assert "-cnv" in command
    assert "-st" in command
    assert command.count("-p") == 1
    assert command[command.index("-p") + 1] == "test prompt"


def test_probe_configuration_is_candidate_specific_and_source_bound() -> None:
    first, second = LOCAL_MODEL_SOURCE_FREEZE_V2.candidates[:2]
    first_hash = _candidate_probe_configuration_sha256(first)
    second_hash = _candidate_probe_configuration_sha256(second)
    assert len(first_hash) == 64
    assert first_hash != second_hash
    changed = replace(first, artifact_sha256="0" * 64)
    assert _candidate_probe_configuration_sha256(changed) != first_hash
