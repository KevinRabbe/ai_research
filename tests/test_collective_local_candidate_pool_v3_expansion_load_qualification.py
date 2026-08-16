from __future__ import annotations

import json
from pathlib import Path

import pytest

from plural_cognition.collective import (
    local_candidate_pool_v3_expansion_load_qualification as runner,
)
from plural_cognition.collective.local_candidate_pool_v2_load_observer_repair import (
    RecoveryAttemptObservation,
)
from plural_cognition.collective.local_model_load_preflight import RuntimeObservation


REVISION = "0123456789abcdef0123456789abcdef01234567"


def _runtime_observation() -> RuntimeObservation:
    return RuntimeObservation(
        version_output="version: 10361 14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
        device_output="CUDA0: NVIDIA GeForce RTX 4060 Ti",
    )


def _successful_observation(command: tuple[str, ...]) -> RecoveryAttemptObservation:
    return RecoveryAttemptObservation(
        command=command,
        exit_code=0,
        timed_out=False,
        elapsed_seconds=1.0,
        stdout_sha256="0" * 64,
        stderr_sha256="1" * 64,
        stdout_bytes=0,
        stderr_bytes=32,
        baseline_gpu_used_mib=100,
        peak_gpu_used_mib=12000,
        peak_process_rss_bytes=1234,
        monitor_error=None,
    )


def _install_common_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_git_revision", lambda: REVISION)
    monkeypatch.setattr(runner, "_verify_runtime_archives", lambda _root: None)
    monkeypatch.setattr(runner, "_runtime_observation", lambda _cli: _runtime_observation())
    monkeypatch.setattr(
        runner,
        "_verify_model_file",
        lambda _path, source: (
            source["artifact_sha256"],
            source["artifact_size_bytes"],
        ),
    )


def test_v3_expansion_load_runner_protocol_has_exact_identity() -> None:
    payload = runner.expansion_load_runner_protocol_payload_v3()
    assert runner.expansion_load_runner_protocol_sha256_v3() == (
        "6670ae531b31bd0548947bcc4ce0b8248204648f0bd3d280c68e1211bed340a4"
    )
    assert payload["predecessor_expansion_source_freeze_sha256"] == (
        "7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03"
    )
    assert payload["source_freeze_revision"] == (
        "dea35b4c11d8de39b978bf3a4ba5f098cfab795b"
    )
    assert payload["scout_ids"] == [
        "qwen3-14b-q5km",
        "ministral-3-14b-instruct-2512-q5km",
        "ministral-3-8b-instruct-2512-q5km",
    ]
    assert payload["pair_count"] == 3
    assert payload["selection_evidence"] is False


def test_v3_expansion_load_command_is_load_only_and_uses_frozen_resources(tmp_path: Path) -> None:
    command = runner._load_only_command(
        tmp_path / "llama-cli.exe", tmp_path / "model.gguf"
    )
    assert command[command.index("-n") + 1] == "0"
    assert command[command.index("-c") + 1] == "4096"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-sm") + 1] == "none"
    assert command[command.index("-mg") + 1] == "0"
    assert command[command.index("-ctk") + 1] == "f16"
    assert command[command.index("-ctv") + 1] == "f16"
    assert command[command.index("-t") + 1] == "16"
    assert command[command.index("-tb") + 1] == "16"
    assert command[command.index("-b") + 1] == "2048"
    assert command[command.index("-ub") + 1] == "512"
    assert command[command.index("-fa") + 1] == "auto"
    assert command[command.index("--log-verbosity") + 1] == "4"
    assert command[command.index("-p") + 1] == "."
    assert "-cnv" not in command
    assert "--simple-io" not in command
    assert "--output-file" not in command


def test_v3_expansion_load_attempt_marker_precedes_every_model_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_common_mocks(monkeypatch)
    artifact_root = tmp_path / "e3l"
    launches: list[str] = []

    def fake_raw(command: tuple[str, ...], *, timeout_seconds: int):
        del timeout_seconds
        model_path = Path(command[command.index("-m") + 1])
        sources = runner.expansion_scout_sources_v3()
        candidate_id = next(
            candidate_id
            for candidate_id, source in sources.items()
            if source["artifact_filename"] == model_path.name
        )
        attempt_path = artifact_root / candidate_id / "attempt.json"
        assert attempt_path.is_file()
        attempt = json.loads(attempt_path.read_text(encoding="ascii"))
        assert attempt["candidate_id"] == candidate_id
        assert attempt["max_attempts"] == 1
        assert attempt["load_only"] is True
        assert attempt["capability_prompt"] is False
        launches.append(candidate_id)
        observation = _successful_observation(command)
        return observation, b"", b"offloaded 42/42 layers to GPU\n"

    monkeypatch.setattr(runner, "_run_raw_attempt", fake_raw)
    suite = runner.run_suite(
        runtime_root=tmp_path / "runtime",
        model_root=tmp_path / "models",
        artifact_root=artifact_root,
        software_revision=REVISION,
    )

    assert launches == list(runner.EXPANSION_SCOUT_IDS_V3)
    assert suite["qualified_count"] == 3
    assert suite["failed_count"] == 0
    assert suite["new_model_launch_count_this_invocation"] == 3
    assert all((artifact_root / item / "result.json").is_file() for item in launches)


def test_v3_expansion_load_partial_evidence_blocks_all_new_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_common_mocks(monkeypatch)
    artifact_root = tmp_path / "e3l"
    partial = artifact_root / runner.EXPANSION_SCOUT_IDS_V3[1]
    partial.mkdir(parents=True)
    (partial / "attempt.json").write_text("{}\n", encoding="ascii")

    def forbidden_raw(*_args, **_kwargs):
        raise AssertionError("model launch must not occur when any partial evidence exists")

    monkeypatch.setattr(runner, "_run_raw_attempt", forbidden_raw)
    with pytest.raises(RuntimeError, match="partial v3 expansion load evidence exists"):
        runner.run_suite(
            runtime_root=tmp_path / "runtime",
            model_root=tmp_path / "models",
            artifact_root=artifact_root,
            software_revision=REVISION,
        )


def test_v3_expansion_load_completed_suite_is_reused_without_new_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_common_mocks(monkeypatch)
    artifact_root = tmp_path / "e3l"
    launch_count = 0

    def fake_raw(command: tuple[str, ...], *, timeout_seconds: int):
        nonlocal launch_count
        del timeout_seconds
        launch_count += 1
        return (
            _successful_observation(command),
            b"",
            b"offloaded 50/50 layers to GPU\n",
        )

    monkeypatch.setattr(runner, "_run_raw_attempt", fake_raw)
    first = runner.run_suite(
        runtime_root=tmp_path / "runtime",
        model_root=tmp_path / "models",
        artifact_root=artifact_root,
        software_revision=REVISION,
    )
    assert launch_count == 3

    second = runner.run_suite(
        runtime_root=tmp_path / "runtime",
        model_root=tmp_path / "models",
        artifact_root=artifact_root,
        software_revision=REVISION,
    )
    assert launch_count == 3
    assert second == first


def test_v3_expansion_load_failure_is_terminal_evidence_and_suite_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_common_mocks(monkeypatch)
    artifact_root = tmp_path / "e3l"
    calls = 0

    def fake_raw(command: tuple[str, ...], *, timeout_seconds: int):
        nonlocal calls
        del timeout_seconds
        calls += 1
        observation = _successful_observation(command)
        if calls == 1:
            return observation, b"", b"no offload line\n"
        return observation, b"", b"offloaded 40/40 layers to GPU\n"

    monkeypatch.setattr(runner, "_run_raw_attempt", fake_raw)
    suite = runner.run_suite(
        runtime_root=tmp_path / "runtime",
        model_root=tmp_path / "models",
        artifact_root=artifact_root,
        software_revision=REVISION,
    )
    assert calls == 3
    assert suite["qualified_count"] == 2
    assert suite["failed_count"] == 1
    first = json.loads(
        (artifact_root / runner.EXPANSION_SCOUT_IDS_V3[0] / "result.json").read_text(
            encoding="ascii"
        )
    )
    assert first["status"] == "LOCAL_MODEL_LOAD_FAIL"
    assert first["failure"] == "llama-cli trace log did not prove GPU layer offload"
    assert first["attempt_count"] == 1
    assert first["selection_evidence"] is False


def test_v3_expansion_load_verifies_all_models_before_first_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_common_mocks(monkeypatch)
    verified: list[str] = []
    sources = runner.expansion_scout_sources_v3()

    def verify(path: Path, source: dict[str, object]):
        del path
        verified.append(str(source["candidate_id"]))
        return str(source["artifact_sha256"]), int(source["artifact_size_bytes"])

    def fake_raw(command: tuple[str, ...], *, timeout_seconds: int):
        del timeout_seconds
        assert verified[:3] == list(runner.EXPANSION_SCOUT_IDS_V3)
        return _successful_observation(command), b"", b"offloaded 40/40 layers to GPU\n"

    monkeypatch.setattr(runner, "_verify_model_file", verify)
    monkeypatch.setattr(runner, "_run_raw_attempt", fake_raw)
    runner.run_suite(
        runtime_root=tmp_path / "runtime",
        model_root=tmp_path / "models",
        artifact_root=tmp_path / "e3l",
        software_revision=REVISION,
    )
    assert verified[:3] == list(runner.EXPANSION_SCOUT_IDS_V3)
    assert set(verified) == set(sources)
