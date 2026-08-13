from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plural_cognition.collective import local_raw_calibration_v2 as module


def _completed(argv: list[str], stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def test_run_probe_retries_one_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(argv))
        assert kwargs["timeout"] == module.RUNTIME_PROBE_TIMEOUT_SECONDS
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(argv, module.RUNTIME_PROBE_TIMEOUT_SECONDS)
        return _completed(argv, "ok")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    result = module._run_probe(["llama-cli.exe", "--version"])
    assert result.stdout == "ok"
    assert len(calls) == 2


def test_run_probe_fails_cleanly_after_bounded_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(argv, module.RUNTIME_PROBE_TIMEOUT_SECONDS)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="runtime probe timed out"):
        module._run_probe(["llama-cli.exe", "--version"])
    assert calls == module.RUNTIME_PROBE_ATTEMPTS


def test_resilient_runtime_observation_preserves_frozen_identity_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli = tmp_path / "llama-cli.exe"
    cli.write_bytes(b"stub")
    outputs = iter(
        (
            "version: 10361 (14e78ddef)\nbuilt with Clang 20.1.8 for Windows x86_64",
            "Available devices:\n  CUDA0: NVIDIA GeForce RTX 4060 Ti (16379 MiB, 15233 MiB free)",
        )
    )

    def fake_probe(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return _completed(argv, next(outputs))

    monkeypatch.setattr(module, "_run_probe", fake_probe)
    observation = module._runtime_observation_resilient(cli)
    assert "version: 10361" in observation.version_output
    assert "14e78ddef" in observation.version_output
    assert "CUDA0:" in observation.device_output


def test_resilient_runtime_observation_rejects_wrong_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli = tmp_path / "llama-cli.exe"
    cli.write_bytes(b"stub")
    monkeypatch.setattr(
        module,
        "_run_probe",
        lambda argv: _completed(argv, "version: 99999 (deadbeef)"),
    )
    with pytest.raises(RuntimeError, match="does not match"):
        module._runtime_observation_resilient(cli)
