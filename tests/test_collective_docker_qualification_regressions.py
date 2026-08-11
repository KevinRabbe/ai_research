from __future__ import annotations

import pytest

from plural_cognition.collective.artifacts import ResourceUsage
from plural_cognition.collective.docker_qualification_model import QualificationFailure
from plural_cognition.collective.docker_qualification_parent_probe import (
    _PARENT_INTERFERENCE_SCRIPT,
    _parent_interference_verifier,
    parent_interference_probe_definition,
)
from plural_cognition.collective.docker_qualification_probes import _ISOLATION_SCRIPT
from plural_cognition.collective.docker_runner import (
    DockerRunnerError,
    _normalize_candidate_exit_code,
)
from plural_cognition.collective.sandbox import SandboxResult


def _clean_result() -> SandboxResult:
    return SandboxResult(
        request_sha256="a" * 64,
        exit_code=0,
        timed_out=False,
        memory_limit_exceeded=False,
        stdout_sha256="b" * 64,
        stderr_sha256="c" * 64,
        resources=ResourceUsage(),
    )


def test_output_overflow_normalizes_signal_exit_to_abnormal_result() -> None:
    assert (
        _normalize_candidate_exit_code(
            exit_code=-9,
            timed_out=False,
            stdout_limit_exceeded=True,
            stderr_limit_exceeded=False,
        )
        is None
    )
    assert (
        _normalize_candidate_exit_code(
            exit_code=-9,
            timed_out=False,
            stdout_limit_exceeded=False,
            stderr_limit_exceeded=True,
        )
        is None
    )


def test_non_overflow_non_timeout_requires_exit_code() -> None:
    with pytest.raises(DockerRunnerError, match="omitted exit code"):
        _normalize_candidate_exit_code(
            exit_code=None,
            timed_out=False,
            stdout_limit_exceeded=False,
            stderr_limit_exceeded=False,
        )


def test_timeout_rejects_reported_exit_code() -> None:
    with pytest.raises(DockerRunnerError, match="timed-out candidate"):
        _normalize_candidate_exit_code(
            exit_code=-9,
            timed_out=True,
            stdout_limit_exceeded=False,
            stderr_limit_exceeded=False,
        )


def test_isolation_probe_checks_root_material_access_not_path_existence() -> None:
    assert "root_docker_config_readable" in _ISOLATION_SCRIPT
    assert "root_gitconfig_readable" in _ISOLATION_SCRIPT
    assert "root_ssh_listable" in _ISOLATION_SCRIPT
    assert 'Path("/root/.docker/config.json").exists()' not in _ISOLATION_SCRIPT
    assert 'Path("/root/.gitconfig").exists()' not in _ISOLATION_SCRIPT
    assert 'Path("/root/.ssh").exists()' not in _ISOLATION_SCRIPT


def test_parent_interference_probe_targets_bootstrap_parent_with_sigkill() -> None:
    definition = parent_interference_probe_definition()
    assert definition.name == "bootstrap-parent-interference"
    assert "target_pid=os.getppid()" in _PARENT_INTERFERENCE_SCRIPT
    assert "signal_number=9" in _PARENT_INTERFERENCE_SCRIPT
    assert "os.kill(target_pid,signal_number)" in _PARENT_INTERFERENCE_SCRIPT


def test_parent_interference_probe_accepts_pid1_survival_after_successful_syscall() -> None:
    evidence = _parent_interference_verifier(
        _clean_result(),
        b'{"signal_errno":0,"signal_number":9,"target_pid":1}\n',
        b"",
        {},
    )
    assert evidence["signal_syscall_returned_success"] is True
    assert evidence["kernel_reported_eperm"] is False
    assert evidence["trusted_bootstrap_result_returned"] is True
    assert evidence["bootstrap_survived_parent_sigkill_attempt"] is True


def test_parent_interference_probe_accepts_pid1_survival_with_eperm() -> None:
    evidence = _parent_interference_verifier(
        _clean_result(),
        b'{"signal_errno":1,"signal_number":9,"target_pid":1}\n',
        b"",
        {},
    )
    assert evidence["signal_syscall_returned_success"] is False
    assert evidence["kernel_reported_eperm"] is True
    assert evidence["trusted_bootstrap_result_returned"] is True
    assert evidence["bootstrap_survived_parent_sigkill_attempt"] is True


def test_parent_interference_probe_rejects_unexpected_signal_errno() -> None:
    with pytest.raises(QualificationFailure, match="unexpected errno"):
        _parent_interference_verifier(
            _clean_result(),
            b'{"signal_errno":3,"signal_number":9,"target_pid":1}\n',
            b"",
            {},
        )
