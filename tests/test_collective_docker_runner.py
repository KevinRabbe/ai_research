from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from plural_cognition.collective.artifacts import TaskIdentity
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.docker_bootstrap_guard import BOOTSTRAP_RESULT_SCHEMA
from plural_cognition.collective.docker_candidate import (
    DOCKER_RUNNER_ID,
    DockerRunnerConfiguration,
)
from plural_cognition.collective.docker_runner import (
    DockerCommandResult,
    DockerRunnerError,
    DockerSandboxRunner,
)
from plural_cognition.collective.repository import snapshot_directory
from plural_cognition.collective.sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
    SandboxRequest,
)


IMAGE = "8" * 64
PATCHED = "9" * 64


def _canonical_line(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _case(tmp_path: Path, executor):
    store = FileContentStore(tmp_path / "store")
    repository_root = tmp_path / "repository-source"
    repository_root.mkdir()
    (repository_root / "module.py").write_bytes(b"VALUE = 1\n")
    repository = snapshot_directory(repository_root, store)

    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    limits = SandboxLimits(
        wall_time_ms=1_000,
        cpu_time_ms=500,
        memory_bytes=64_000_000,
        writable_bytes=8_000_000,
        process_count=8,
        stdout_bytes=1_024,
        stderr_bytes=1_024,
    )
    spec = ProtectedSandboxSpec(
        runner_id=DOCKER_RUNNER_ID,
        runner_configuration_sha256=configuration.sha256,
        environment_image_sha256=configuration.environment_image_sha256,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=("python", "-c", "print('ok')"),
        environment=(),
        limits=limits,
    )
    patch_sha = store.put_bytes(
        b"--- a/module.py\n"
        b"+++ b/module.py\n"
        b"@@ -1 +1 @@\n"
        b"-VALUE = 1\n"
        b"+VALUE = 2\n"
    )
    request = SandboxRequest(
        task=TaskIdentity("rs-runner-001", "repository-surgery-v0", "a" * 64),
        submission_sha256=store.put_bytes(b'{"submission":"visible"}'),
        buggy_repository_sha256=repository.manifest_sha256,
        patch_sha256=patch_sha,
        runtime_input_sha256=store.put_bytes(b"input\n"),
        sandbox_spec_sha256=spec.sha256,
    )
    runner = DockerSandboxRunner(
        spec=spec,
        configuration=configuration,
        store=store,
        staging_root=tmp_path / "staging",
        command_executor=executor,
    )
    return store, request, runner


class _SuccessfulExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], float]] = []
        self.request_sha256: str | None = None
        self.noncanonical = False
        self.remove_failure = False
        self.memory_limit_exceeded = False
        self.oom_kill_events = 0
        self.container_oom_killed = False

    def __call__(self, argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
        self.calls.append((argv, timeout_seconds))
        operation = argv[1]
        if operation == "create":
            return DockerCommandResult(argv, 0, b"container-id\n", b"")
        if operation == "start":
            assert self.request_sha256 is not None
            envelope = {
                "schema": BOOTSTRAP_RESULT_SCHEMA,
                "status": "candidate-result",
                "request_sha256": self.request_sha256,
                "patched_repository_sha256": PATCHED,
                "exit_code": 0,
                "timed_out": False,
                "stdout_limit_exceeded": False,
                "stderr_limit_exceeded": False,
                "memory_limit_exceeded": self.memory_limit_exceeded,
                "oom_kill_events": self.oom_kill_events,
                "stdout_base64": base64.b64encode(b"candidate-out\n").decode("ascii"),
                "stderr_base64": base64.b64encode(b"").decode("ascii"),
                "wall_time_ms": 23,
                "cpu_time_ms": 7,
                "peak_memory_bytes": 123_456,
            }
            if self.noncanonical:
                stdout = json.dumps(envelope, sort_keys=True).encode("ascii") + b"\n"
            else:
                stdout = _canonical_line(envelope)
            return DockerCommandResult(argv, 0, stdout, b"")
        if operation == "inspect":
            state = {
                "Running": False,
                "OOMKilled": self.container_oom_killed,
                "ExitCode": 0,
            }
            return DockerCommandResult(argv, 0, json.dumps(state).encode("ascii"), b"")
        if operation == "rm":
            if self.remove_failure:
                return DockerCommandResult(argv, 1, b"", b"remove failed")
            return DockerCommandResult(argv, 0, b"name\n", b"")
        raise AssertionError(f"unexpected Docker operation: {argv}")


def test_concrete_runner_parses_canonical_bootstrap_result_and_cleans_up(tmp_path: Path) -> None:
    executor = _SuccessfulExecutor()
    store, request, runner = _case(tmp_path, executor)
    executor.request_sha256 = request.sha256

    result = runner.run(request)

    assert result.request_sha256 == request.sha256
    assert result.exit_code == 0
    assert not result.timed_out
    assert not result.memory_limit_exceeded
    assert store.get_bytes(result.stdout_sha256) == b"candidate-out\n"
    assert store.get_bytes(result.stderr_sha256) == b""
    assert result.resources.wall_time_ms == 23
    assert result.resources.cpu_time_ms == 7
    assert result.resources.peak_ram_bytes == 123_456
    assert [call[0][1] for call in executor.calls] == ["create", "start", "inspect", "rm"]
    start_timeout = next(timeout for argv, timeout in executor.calls if argv[1] == "start")
    assert start_timeout == 6.0
    assert list((tmp_path / "staging").iterdir()) == []


def test_concrete_runner_uses_bootstrap_child_oom_evidence(tmp_path: Path) -> None:
    executor = _SuccessfulExecutor()
    _, request, runner = _case(tmp_path, executor)
    executor.request_sha256 = request.sha256
    executor.memory_limit_exceeded = True
    executor.oom_kill_events = 1

    result = runner.run(request)

    assert result.memory_limit_exceeded is True
    assert executor.container_oom_killed is False


def test_concrete_runner_rejects_inconsistent_oom_evidence(tmp_path: Path) -> None:
    executor = _SuccessfulExecutor()
    _, request, runner = _case(tmp_path, executor)
    executor.request_sha256 = request.sha256
    executor.memory_limit_exceeded = False
    executor.oom_kill_events = 1

    with pytest.raises(DockerRunnerError, match="OOM fields are inconsistent"):
        runner.run(request)

    assert executor.calls[-1][0][1] == "rm"


def test_concrete_runner_outer_timeout_forces_container_removal(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def executor(argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
        calls.append(argv)
        if argv[1] == "create":
            return DockerCommandResult(argv, 0, b"container-id\n", b"")
        if argv[1] == "start":
            return DockerCommandResult(argv, None, b"", b"", timed_out=True)
        if argv[1] == "rm":
            return DockerCommandResult(argv, 0, b"name\n", b"")
        raise AssertionError(f"unexpected Docker operation: {argv}")

    _, request, runner = _case(tmp_path, executor)

    with pytest.raises(DockerRunnerError, match="outer wall-time"):
        runner.run(request)

    assert [argv[1] for argv in calls] == ["create", "start", "rm"]
    assert list((tmp_path / "staging").iterdir()) == []


def test_concrete_runner_rejects_noncanonical_bootstrap_and_still_cleans_up(tmp_path: Path) -> None:
    executor = _SuccessfulExecutor()
    _, request, runner = _case(tmp_path, executor)
    executor.request_sha256 = request.sha256
    executor.noncanonical = True

    with pytest.raises(DockerRunnerError, match="not canonical"):
        runner.run(request)

    assert executor.calls[-1][0][1] == "rm"
    assert list((tmp_path / "staging").iterdir()) == []


def test_concrete_runner_fails_closed_when_forced_cleanup_fails(tmp_path: Path) -> None:
    executor = _SuccessfulExecutor()
    _, request, runner = _case(tmp_path, executor)
    executor.request_sha256 = request.sha256
    executor.remove_failure = True

    with pytest.raises(DockerRunnerError, match="container cleanup failed"):
        runner.run(request)

    assert executor.calls[-1][0][1] == "rm"
    assert list((tmp_path / "staging").iterdir()) == []
