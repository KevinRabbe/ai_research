"""Safe target-machine preflight for candidate protected-execution backends.

The preflight performs availability/introspection commands only. It never starts a
container, Windows Sandbox session, or untrusted process.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence

SANDBOX_PREFLIGHT_SCHEMA = "plural-cognition-sandbox-preflight-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    value = completed.stdout.strip()
    return value or "unknown"


class ProbeStatus(str, Enum):
    NOT_APPLICABLE = "not-applicable"
    UNAVAILABLE = "unavailable"
    CLI_AVAILABLE = "cli-available"
    ENGINE_AVAILABLE = "engine-available"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BackendProbe:
    backend_id: str
    status: ProbeStatus
    executable_path: str | None
    details: tuple[tuple[str, str], ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if type(self.backend_id) is not str or not self.backend_id:
            raise ValueError("backend_id must be a non-empty string")
        if not isinstance(self.status, ProbeStatus):
            raise TypeError("status must be ProbeStatus")
        if self.executable_path is not None and (
            type(self.executable_path) is not str or not self.executable_path
        ):
            raise ValueError("executable_path must be a non-empty string or None")
        keys = tuple(key for key, _ in self.details)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("probe detail keys must be sorted and unique")
        for key, value in self.details:
            if type(key) is not str or not key or type(value) is not str:
                raise ValueError("probe details must contain non-empty string keys and string values")
        if self.error is not None and type(self.error) is not str:
            raise TypeError("error must be str or None")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "status": self.status.value,
            "executable_path": self.executable_path,
            "details": [[key, value] for key, value in self.details],
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class SandboxPreflightReport:
    software_revision: str
    platform_system: str
    platform_release: str
    platform_version: str
    machine: str
    probes: tuple[BackendProbe, ...]

    def __post_init__(self) -> None:
        if not self.probes:
            raise ValueError("preflight report requires at least one backend probe")
        ids = tuple(probe.backend_id for probe in self.probes)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("backend probes must be sorted by unique backend_id")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_PREFLIGHT_SCHEMA,
            "software_revision": self.software_revision,
            "platform_system": self.platform_system,
            "platform_release": self.platform_release,
            "platform_version": self.platform_version,
            "machine": self.machine,
            "probes": [probe.canonical_payload() for probe in self.probes],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return str(value)


def _run_json_command(argv: Sequence[str], *, timeout: float = 10.0) -> tuple[dict[str, Any] | None, str | None]:
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        return None, detail[:4000]
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON output: {exc}"
    if type(payload) is not dict:
        return None, "JSON command did not return an object"
    return payload, None


def probe_docker() -> BackendProbe:
    executable = shutil.which("docker")
    if executable is None:
        return BackendProbe("docker", ProbeStatus.UNAVAILABLE, None)

    version, error = _run_json_command(
        (executable, "version", "--format", "{{json .}}")
    )
    if version is None:
        return BackendProbe(
            "docker",
            ProbeStatus.CLI_AVAILABLE,
            executable,
            error=error,
        )

    info, info_error = _run_json_command(
        (executable, "info", "--format", "{{json .}}")
    )
    if info is None:
        details = tuple(
            sorted(
                {
                    "client_version": _safe_text(version.get("Client", {}).get("Version") if isinstance(version.get("Client"), dict) else ""),
                    "server_version": _safe_text(version.get("Server", {}).get("Version") if isinstance(version.get("Server"), dict) else ""),
                }.items()
            )
        )
        return BackendProbe(
            "docker",
            ProbeStatus.CLI_AVAILABLE,
            executable,
            details=details,
            error=info_error,
        )

    client = version.get("Client") if isinstance(version.get("Client"), dict) else {}
    server = version.get("Server") if isinstance(version.get("Server"), dict) else {}
    details_dict = {
        "architecture": _safe_text(info.get("Architecture")),
        "cgroup_driver": _safe_text(info.get("CgroupDriver")),
        "client_version": _safe_text(client.get("Version")),
        "docker_root_dir": _safe_text(info.get("DockerRootDir")),
        "kernel_version": _safe_text(info.get("KernelVersion")),
        "operating_system": _safe_text(info.get("OperatingSystem")),
        "os_type": _safe_text(info.get("OSType")),
        "security_options": _safe_text(info.get("SecurityOptions")),
        "server_version": _safe_text(server.get("Version") or info.get("ServerVersion")),
    }
    return BackendProbe(
        "docker",
        ProbeStatus.ENGINE_AVAILABLE,
        executable,
        details=tuple(sorted(details_dict.items())),
    )


def probe_windows_sandbox(*, system: str | None = None) -> BackendProbe:
    system_name = platform.system() if system is None else system
    if system_name != "Windows":
        return BackendProbe(
            "windows-sandbox",
            ProbeStatus.NOT_APPLICABLE,
            None,
        )
    executable = shutil.which("wsb")
    if executable is None:
        return BackendProbe("windows-sandbox", ProbeStatus.UNAVAILABLE, None)
    try:
        completed = subprocess.run(
            [executable, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return BackendProbe(
            "windows-sandbox",
            ProbeStatus.ERROR,
            executable,
            error=f"{type(exc).__name__}: {exc}",
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return BackendProbe(
            "windows-sandbox",
            ProbeStatus.ERROR,
            executable,
            error=detail[:4000],
        )
    help_text = completed.stdout + completed.stderr
    details = (
        ("cli_help_sha256", sha256(help_text.encode("utf-8")).hexdigest()),
        ("supports_exec_token", str("exec" in help_text.lower()).lower()),
        ("supports_share_token", str("share" in help_text.lower()).lower()),
        ("supports_start_token", str("start" in help_text.lower()).lower()),
    )
    return BackendProbe(
        "windows-sandbox",
        ProbeStatus.CLI_AVAILABLE,
        executable,
        details=details,
    )


def run_sandbox_preflight() -> SandboxPreflightReport:
    system_name = platform.system()
    probes = tuple(
        sorted(
            (
                probe_docker(),
                probe_windows_sandbox(system=system_name),
            ),
            key=lambda probe: probe.backend_id,
        )
    )
    return SandboxPreflightReport(
        software_revision=_git_commit(),
        platform_system=system_name,
        platform_release=platform.release(),
        platform_version=platform.version(),
        machine=platform.machine(),
        probes=probes,
    )


def write_report(path: str | Path, report: SandboxPreflightReport) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    data = report.canonical_bytes()
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect available protected-execution backends without starting one."
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_sandbox_preflight()
    write_report(args.output, report)
    for probe in report.probes:
        print(f"{probe.backend_id}: {probe.status.value}")
        if probe.error:
            print(f"  {probe.error}")
    print(f"report_sha256={report.sha256}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
