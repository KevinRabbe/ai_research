from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from plural_cognition.collective.sandbox_preflight import (
    BackendProbe,
    ProbeStatus,
    SandboxPreflightReport,
    probe_docker,
    probe_windows_sandbox,
    write_report,
)


def _completed(argv, stdout: str, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def test_docker_probe_reports_unavailable_without_cli() -> None:
    with patch("shutil.which", return_value=None):
        probe = probe_docker()
    assert probe.backend_id == "docker"
    assert probe.status is ProbeStatus.UNAVAILABLE
    assert probe.executable_path is None


def test_docker_probe_requires_reachable_engine_for_engine_available() -> None:
    version_payload = {
        "Client": {"Version": "29.0.0"},
        "Server": {"Version": "29.0.0"},
    }
    info_payload = {
        "Architecture": "x86_64",
        "CgroupDriver": "cgroupfs",
        "DockerRootDir": "/var/lib/docker",
        "KernelVersion": "6.6",
        "OperatingSystem": "Docker Desktop",
        "OSType": "linux",
        "SecurityOptions": ["name=seccomp"],
        "ServerVersion": "29.0.0",
    }
    with patch("shutil.which", return_value="C:/Docker/docker.exe"), patch(
        "subprocess.run",
        side_effect=(
            _completed([], json.dumps(version_payload)),
            _completed([], json.dumps(info_payload)),
        ),
    ):
        probe = probe_docker()
    assert probe.status is ProbeStatus.ENGINE_AVAILABLE
    assert dict(probe.details)["os_type"] == "linux"
    assert dict(probe.details)["server_version"] == "29.0.0"


def test_docker_probe_distinguishes_cli_from_unreachable_engine() -> None:
    version_payload = {
        "Client": {"Version": "29.0.0"},
        "Server": {"Version": "29.0.0"},
    }
    with patch("shutil.which", return_value="docker"), patch(
        "subprocess.run",
        side_effect=(
            _completed([], json.dumps(version_payload)),
            _completed([], "", returncode=1, stderr="daemon unavailable"),
        ),
    ):
        probe = probe_docker()
    assert probe.status is ProbeStatus.CLI_AVAILABLE
    assert probe.error == "daemon unavailable"


def test_windows_sandbox_is_not_applicable_off_windows() -> None:
    probe = probe_windows_sandbox(system="Linux")
    assert probe.status is ProbeStatus.NOT_APPLICABLE


def test_windows_sandbox_probe_checks_cli_without_starting_session() -> None:
    help_text = "Commands: start list exec stop share connect ip"
    with patch("shutil.which", return_value="C:/Windows/System32/wsb.exe"), patch(
        "subprocess.run",
        return_value=_completed([], help_text),
    ) as run:
        probe = probe_windows_sandbox(system="Windows")
    assert probe.status is ProbeStatus.CLI_AVAILABLE
    assert dict(probe.details)["supports_exec_token"] == "true"
    assert dict(probe.details)["supports_start_token"] == "true"
    invoked = run.call_args.args[0]
    assert invoked[-1] == "--help"
    assert "start" not in invoked[1:]


def test_preflight_report_is_canonical_and_atomic(tmp_path: Path) -> None:
    report = SandboxPreflightReport(
        software_revision="1" * 40,
        platform_system="Windows",
        platform_release="11",
        platform_version="test",
        machine="AMD64",
        probes=(
            BackendProbe("docker", ProbeStatus.UNAVAILABLE, None),
            BackendProbe("windows-sandbox", ProbeStatus.CLI_AVAILABLE, "wsb"),
        ),
    )
    path = tmp_path / "preflight.json"
    write_report(path, report)
    assert path.read_bytes() == report.canonical_bytes() + b"\n"
    assert len(report.sha256) == 64
