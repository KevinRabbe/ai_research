from __future__ import annotations

import pytest

from plural_cognition.collective.artifacts import ResourceUsage, TaskIdentity
from plural_cognition.collective.sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
    SandboxRequest,
    SandboxResult,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64


def _limits() -> SandboxLimits:
    return SandboxLimits(
        wall_time_ms=30_000,
        cpu_time_ms=20_000,
        memory_bytes=1_000_000_000,
        writable_bytes=100_000_000,
        process_count=32,
        stdout_bytes=1_000_000,
        stderr_bytes=1_000_000,
    )


def _spec() -> ProtectedSandboxSpec:
    return ProtectedSandboxSpec(
        runner_id="isolated-runner-v0",
        runner_configuration_sha256=A,
        environment_image_sha256=B,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=("python", "-m", "pytest", "-q"),
        environment=(("PYTHONDONTWRITEBYTECODE", "1"),),
        limits=_limits(),
    )


def test_protected_sandbox_spec_is_content_addressed() -> None:
    spec = _spec()
    assert len(spec.sha256) == 64
    assert spec.canonical_payload()["network_policy"] == "disabled"
    changed = ProtectedSandboxSpec(
        runner_id=spec.runner_id,
        runner_configuration_sha256=spec.runner_configuration_sha256,
        environment_image_sha256=spec.environment_image_sha256,
        network_policy=spec.network_policy,
        command_argv=("python", "-m", "pytest", "-q", "tests"),
        environment=spec.environment,
        limits=spec.limits,
    )
    assert changed.sha256 != spec.sha256


def test_environment_must_be_sorted_and_unique() -> None:
    with pytest.raises(ValueError, match="sorted"):
        ProtectedSandboxSpec(
            runner_id="runner",
            runner_configuration_sha256=A,
            environment_image_sha256=B,
            network_policy=NetworkPolicy.DISABLED,
            command_argv=("python",),
            environment=(("Z", "1"), ("A", "2")),
            limits=_limits(),
        )


def test_sandbox_request_binds_patch_hidden_tests_and_spec() -> None:
    task = TaskIdentity("rs-001", "repository-surgery-v0", A)
    spec = _spec()
    request = SandboxRequest(
        task=task,
        submission_sha256=B,
        buggy_repository_sha256=C,
        patch_sha256=D,
        hidden_tests_sha256=E,
        sandbox_spec_sha256=spec.sha256,
    )
    assert len(request.sha256) == 64
    assert request.canonical_payload()["hidden_tests_sha256"] == E


def test_sandbox_result_rejects_exit_code_on_timeout() -> None:
    with pytest.raises(ValueError, match="timed-out"):
        SandboxResult(
            request_sha256=A,
            exit_code=1,
            timed_out=True,
            memory_limit_exceeded=False,
            stdout_sha256=B,
            stderr_sha256=C,
            resources=ResourceUsage(),
        )


def test_sandbox_result_reports_normal_completion() -> None:
    result = SandboxResult(
        request_sha256=A,
        exit_code=0,
        timed_out=False,
        memory_limit_exceeded=False,
        stdout_sha256=B,
        stderr_sha256=C,
        resources=ResourceUsage(
            verifier_calls=1,
            wall_time_ms=100,
            cpu_time_ms=80,
            peak_ram_bytes=1234,
        ),
    )
    assert result.completed_normally
    assert len(result.sha256) == 64
