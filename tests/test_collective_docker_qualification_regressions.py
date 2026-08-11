from __future__ import annotations

import pytest

from plural_cognition.collective.docker_qualification_probes import _ISOLATION_SCRIPT
from plural_cognition.collective.docker_runner import (
    DockerRunnerError,
    _normalize_candidate_exit_code,
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
