from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from plural_cognition.collective import local_candidate_pool_v2_calibration as runner
from plural_cognition.collective.candidate_pool_v2_calibration_protocol import (
    CALIBRATION_TASK_IDS_V2,
    CANDIDATE_IDS_V2,
    FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
)


def test_v2_calibration_runner_uses_exact_six_by_six_matrix() -> None:
    assert len(CANDIDATE_IDS_V2) == 6
    assert len(CALIBRATION_TASK_IDS_V2) == 6
    assert tuple(item.task_id for item in runner._selected_blueprints()) == CALIBRATION_TASK_IDS_V2


def test_v2_calibration_candidate_sources_cover_incumbents_and_challengers() -> None:
    sources = runner._candidate_sources()
    assert tuple(sources) == CANDIDATE_IDS_V2
    assert sources["qwen3-8b-q8"]["artifact_sha256"] == "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6"
    assert sources["qwen2.5-coder-14b-q5km"]["artifact_sha256"] == "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775"
    assert sources["devstral-24b-q4km"]["artifact_sha256"] == "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b"
    assert sources["gpt-oss-20b-mxfp4"]["artifact_sha256"] == "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901"
    assert sources["phi-4-reasoning-plus-14b-q5km"]["artifact_sha256"] == "7d4dd651787f16365d6ceed9bcc42fe76e47204dedf9ac3539a749e1c3f3b6f7"
    assert sources["devstral-small-2-24b-q4km"]["artifact_sha256"] == "bfd11c8679c6b81eb43763505465d7dcfa72e460ab1c220ecc235a3efadd7f7f"


def test_v2_calibration_command_matches_frozen_resource_transport(tmp_path: Path) -> None:
    command = runner._load_command(
        cli=Path("C:/runtime/llama-cli.exe"),
        model_path=Path("C:/models/model.gguf"),
        prompt=b"prompt",
        capture=tmp_path / "capture.txt",
    )
    assert command[command.index("-c") + 1] == "4096"
    assert command[command.index("-n") + 1] == "2048"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-sm") + 1] == "none"
    assert command[command.index("-mg") + 1] == "0"
    assert command[command.index("-ctk") + 1] == "f16"
    assert command[command.index("-ctv") + 1] == "f16"
    assert command[command.index("-lm") + 1] == "mmap"
    assert command[command.index("-t") + 1] == "16"
    assert command[command.index("-tb") + 1] == "16"
    assert command[command.index("-b") + 1] == "2048"
    assert command[command.index("-ub") + 1] == "512"
    assert command[command.index("-fa") + 1] == "auto"
    assert command[command.index("--log-verbosity") + 1] == "4"
    for flag in ("--offline", "-cnv", "--simple-io", "--no-escape", "--no-display-prompt", "-st"):
        assert flag in command


def test_v2_calibration_gate_requires_both_parse_and_solve_thresholds() -> None:
    assert runner._candidate_passed(6, 4) is True
    assert runner._candidate_passed(6, 6) is True
    assert runner._candidate_passed(5, 6) is False
    assert runner._candidate_passed(6, 3) is False


def test_v2_pair_identity_is_deterministic_and_protocol_bound() -> None:
    first = runner._pair_id(CANDIDATE_IDS_V2[0], CALIBRATION_TASK_IDS_V2[0])
    second = runner._pair_id(CANDIDATE_IDS_V2[0], CALIBRATION_TASK_IDS_V2[0])
    other = runner._pair_id(CANDIDATE_IDS_V2[0], CALIBRATION_TASK_IDS_V2[1])
    assert first == second
    assert first != other
    assert len(first) == 64
    assert len(FINAL_CALIBRATION_PROTOCOL_SHA256_V2) == 64


def test_v2_pair_state_treats_any_nonfinal_directory_as_partial(tmp_path: Path) -> None:
    root = tmp_path / "pair"
    assert runner._pair_state(root) == "missing"
    root.mkdir()
    assert runner._pair_state(root) == "partial"
    (root / "attempt.json").write_text("{}", encoding="ascii")
    assert runner._pair_state(root) == "partial"
    (root / "result.json").write_text("{}", encoding="ascii")
    assert runner._pair_state(root) == "complete"


def test_v2_global_preflight_blocks_partial_pair_before_new_inference(tmp_path: Path) -> None:
    partial = runner._pair_root(tmp_path, CANDIDATE_IDS_V2[0], CALIBRATION_TASK_IDS_V2[0])
    partial.mkdir(parents=True)
    (partial / "attempt.json").write_text("{}", encoding="ascii")
    with pytest.raises(RuntimeError, match="blocks all new inference"):
        runner._preflight_pair_states(tmp_path, software_revision="0" * 40)


def test_v2_calibration_runner_has_no_selection_material_dependency() -> None:
    source = inspect.getsource(runner)
    assert "repository_surgery_selection" not in source
    assert "selection_blueprints" not in source
    assert "local_selection_bakeoff" not in source
