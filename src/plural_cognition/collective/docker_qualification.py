"""Target-machine adversarial qualification for the protected Docker runner.

This module is the first project component that deliberately executes containers.
It runs only deterministic project-authored probes. It never executes a model-
generated patch and never receives protected expectations or grader state.

Qualification is exact-scope evidence, not a general Docker security claim. The
report binds the engine fingerprint, immutable local runner image, sandbox
contract, runner configuration, qualification source, and software revision.
Every required probe must pass; any failure produces REJECTED.
"""

from __future__ import annotations

import argparse
import errno
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Sequence

from .artifacts import TaskIdentity
from .content_store import FileContentStore, content_sha256, validate_sha256
from .docker_bootstrap_guard import _EXPECTED_CORE_SHA256
from .docker_candidate import DOCKER_RUNNER_ID, DockerRunnerConfiguration
from .docker_identity import DockerEngineIdentity, probe_docker_qualification_identity
from .docker_local_image import DockerLocalImageIdentity, probe_local_qualification_image
from .docker_runner import DockerCommandResult, DockerSandboxRunner
from .repository import snapshot_directory
from .sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
    SandboxRequest,
    SandboxResult,
)

DOCKER_QUALIFICATION_REPORT_SCHEMA = "plural-cognition-docker-runner-qualification-v1"
DOCKER_QUALIFICATION_PROBE_SCHEMA = "plural-cognition-docker-runner-probe-v1"
QUALIFICATION_SCOPE = "repository-surgery-v0"
QUALIFIED = "QUALIFIED"
REJECTED = "REJECTED"

_BASE_IMAGE = (
    "python@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3"
)
_REQUIRED_INPUT_ENTRIES = (
    "bundle-manifest.json",
    "candidate.patch",
    "repository",
    "request.json",
    "runtime-input.bin",
    "sandbox-spec.json",
    "submission.json",
)
_FORBIDDEN_ENVIRONMENT_NAMES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AZURE_CLIENT_SECRET",
    "DOCKER_HOST",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY",
    "SSH_AUTH_SOCK",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"qualification source file does not exist: {path}")
    return sha256(path.read_bytes()).hexdigest()


def _cpu_quota_text(cpu_time_ms: int, wall_time_ms: int) -> str:
    ratio = Decimal(cpu_time_ms) / Decimal(wall_time_ms)
    rounded = ratio.quantize(Decimal("0.000001"), rounding=ROUND_UP)
    if rounded <= 0:
        rounded = Decimal("0.000001")
    return format(rounded, "f")


def _expected_nano_cpus(limits: SandboxLimits) -> int:
    return int(Decimal(_cpu_quota_text(limits.cpu_time_ms, limits.wall_time_ms)) * Decimal(1_000_000_000))


@dataclass(frozen=True, slots=True)
class QualificationProbeRecord:
    name: str
    passed: bool
    request_sha256: str | None
    sandbox_result: dict[str, Any] | None
    evidence: dict[str, Any]
    error: str | None = None

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name:
            raise ValueError("probe name must be non-empty")
        if type(self.passed) is not bool:
            raise TypeError("passed must be bool")
        if self.request_sha256 is not None:
            validate_sha256(self.request_sha256)
        if self.sandbox_result is not None and type(self.sandbox_result) is not dict:
            raise TypeError("sandbox_result must be dict or None")
        if type(self.evidence) is not dict:
            raise TypeError("evidence must be dict")
        if self.error is not None and type(self.error) is not str:
            raise TypeError("error must be str or None")
        if self.passed and self.error is not None:
            raise ValueError("passed probe must not carry an error")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_QUALIFICATION_PROBE_SCHEMA,
            "name": self.name,
            "passed": self.passed,
            "request_sha256": self.request_sha256,
            "sandbox_result": self.sandbox_result,
            "evidence": self.evidence,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class DockerQualificationReport:
    software_revision: str
    engine_sha256: str
    image_identity_sha256: str
    immutable_image: str
    runner_configuration_sha256: str
    sandbox_contract_sha256: str
    qualification_source_sha256: str
    bootstrap_core_sha256: str
    bootstrap_guard_sha256: str
    dockerfile_sha256: str
    probes: tuple[QualificationProbeRecord, ...]

    def __post_init__(self) -> None:
        _git_revision(self.software_revision)
        for digest in (
            self.engine_sha256,
            self.image_identity_sha256,
            self.runner_configuration_sha256,
            self.sandbox_contract_sha256,
            self.qualification_source_sha256,
            self.bootstrap_core_sha256,
            self.bootstrap_guard_sha256,
            self.dockerfile_sha256,
        ):
            validate_sha256(digest)
        if not self.immutable_image.startswith("sha256:"):
            raise ValueError("immutable_image must be a local sha256 image reference")
        validate_sha256(self.immutable_image.split(":", 1)[1])
        if not self.probes:
            raise ValueError("qualification report requires probes")
        if len({probe.name for probe in self.probes}) != len(self.probes):
            raise ValueError("qualification probe names must be unique")

    @property
    def status(self) -> str:
        return QUALIFIED if all(probe.passed for probe in self.probes) else REJECTED

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_QUALIFICATION_REPORT_SCHEMA,
            "scope": QUALIFICATION_SCOPE,
            "status": self.status,
            "software_revision": self.software_revision,
            "engine_sha256": self.engine_sha256,
            "image_identity_sha256": self.image_identity_sha256,
            "immutable_image": self.immutable_image,
            "runner_configuration_sha256": self.runner_configuration_sha256,
            "sandbox_contract_sha256": self.sandbox_contract_sha256,
            "qualification_source_sha256": self.qualification_source_sha256,
            "bootstrap_core_sha256": self.bootstrap_core_sha256,
            "bootstrap_guard_sha256": self.bootstrap_guard_sha256,
            "dockerfile_sha256": self.dockerfile_sha256,
            "probes": [probe.canonical_payload() for probe in self.probes],
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


class QualificationFailure(RuntimeError):
    pass


def _host_execute(argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
    try:
        completed = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return DockerCommandResult(
            argv=argv,
            returncode=None,
            stdout=exc.stdout or b"",
            stderr=exc.stderr or b"",
            timed_out=True,
        )
    return DockerCommandResult(
        argv=argv,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _json_host_command(argv: tuple[str, ...], timeout_seconds: float = 15.0) -> Any:
    result = _host_execute(argv, timeout_seconds)
    if result.timed_out or result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:1024]
        raise QualificationFailure(f"host Docker diagnostic failed: {argv!r}: {detail}")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationFailure(f"host Docker diagnostic returned invalid JSON: {argv!r}") from exc


class _AuditedDockerExecutor:
    """Execute runner argv while recording sanitized post-create Docker policy."""

    def __init__(self, docker_executable: str) -> None:
        self.docker_executable = docker_executable
        self.container_name: str | None = None
        self.create_audit: dict[str, Any] | None = None

    def __call__(self, argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
        result = _host_execute(argv, timeout_seconds)
        if len(argv) > 1 and argv[1] == "create" and not result.timed_out and result.returncode == 0:
            try:
                index = argv.index("--name")
                self.container_name = argv[index + 1]
            except (ValueError, IndexError) as exc:
                raise QualificationFailure("Docker create argv lacks a container name") from exc
            raw = _json_host_command(
                (
                    self.docker_executable,
                    "inspect",
                    "--format",
                    "{{json .}}",
                    self.container_name,
                )
            )
            if type(raw) is not dict:
                raise QualificationFailure("docker inspect create audit is not an object")
            self.create_audit = _sanitize_create_audit(raw)
        return result


def _sanitize_create_audit(raw: dict[str, Any]) -> dict[str, Any]:
    config = raw.get("Config")
    host = raw.get("HostConfig")
    mounts = raw.get("Mounts")
    if type(config) is not dict or type(host) is not dict or type(mounts) is not list:
        raise QualificationFailure("docker inspect lacks Config/HostConfig/Mounts")

    sanitized_mounts: list[dict[str, Any]] = []
    for mount in mounts:
        if type(mount) is not dict:
            raise QualificationFailure("docker inspect Mounts contains a non-object")
        sanitized_mounts.append(
            {
                "type": mount.get("Type"),
                "destination": mount.get("Destination"),
                "rw": mount.get("RW"),
            }
        )
    sanitized_mounts.sort(key=lambda item: str(item["destination"]))

    restart = host.get("RestartPolicy")
    if type(restart) is not dict:
        raise QualificationFailure("docker inspect RestartPolicy is missing")

    def _list(name: str) -> list[Any]:
        value = host.get(name)
        return [] if value is None else list(value)

    tmpfs = host.get("Tmpfs")
    if tmpfs is None:
        tmpfs = {}
    if type(tmpfs) is not dict:
        raise QualificationFailure("docker inspect Tmpfs is not an object")

    return {
        "user": config.get("User"),
        "network_mode": host.get("NetworkMode"),
        "ipc_mode": host.get("IpcMode"),
        "pid_mode": host.get("PidMode"),
        "cgroupns_mode": host.get("CgroupnsMode"),
        "privileged": host.get("Privileged"),
        "readonly_rootfs": host.get("ReadonlyRootfs"),
        "pids_limit": host.get("PidsLimit"),
        "memory": host.get("Memory"),
        "memory_swap": host.get("MemorySwap"),
        "nano_cpus": host.get("NanoCpus"),
        "restart_policy": restart.get("Name"),
        "cap_drop": sorted(str(item) for item in _list("CapDrop")),
        "security_opt": sorted(str(item) for item in _list("SecurityOpt")),
        "devices": _list("Devices"),
        "device_requests": _list("DeviceRequests"),
        "port_bindings": host.get("PortBindings") or {},
        "mounts": sanitized_mounts,
        "tmpfs": {str(key): str(value) for key, value in sorted(tmpfs.items())},
    }


def _verify_create_audit(
    audit: dict[str, Any],
    *,
    configuration: DockerRunnerConfiguration,
    limits: SandboxLimits,
) -> dict[str, Any]:
    checks = {
        "user": audit.get("user") == f"{configuration.candidate_uid}:{configuration.candidate_gid}",
        "network_none": audit.get("network_mode") == "none",
        "ipc_none": audit.get("ipc_mode") == "none",
        "pid_namespace_not_host": audit.get("pid_mode") != "host",
        "cgroup_namespace_not_host": audit.get("cgroupns_mode") != "host",
        "not_privileged": audit.get("privileged") is False,
        "readonly_rootfs": audit.get("readonly_rootfs") is True,
        "pids_limit": audit.get("pids_limit") == limits.process_count,
        "memory_limit": audit.get("memory") == limits.memory_bytes,
        "memory_swap_limit": audit.get("memory_swap") == limits.memory_bytes,
        "cpu_quota": audit.get("nano_cpus") == _expected_nano_cpus(limits),
        "restart_disabled": audit.get("restart_policy") == "no",
        "capabilities_dropped": any(str(item).upper() == "ALL" for item in audit.get("cap_drop", [])),
        "no_new_privileges": any(
            str(item).replace(":", "=").lower() == "no-new-privileges=true"
            for item in audit.get("security_opt", [])
        ),
        "no_devices": audit.get("devices") == [] and audit.get("device_requests") == [],
        "no_ports": audit.get("port_bindings") == {},
    }

    mounts = audit.get("mounts")
    checks["only_readonly_input_bind"] = mounts == [
        {"type": "bind", "destination": configuration.input_mount_target, "rw": False}
    ]
    tmpfs = audit.get("tmpfs")
    tmpfs_value = tmpfs.get(configuration.workspace_target, "") if type(tmpfs) is dict else ""
    checks["bounded_workspace_tmpfs"] = all(
        token in tmpfs_value
        for token in (
            "noexec",
            "nosuid",
            f"size={limits.writable_bytes}",
        )
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise QualificationFailure("Docker create policy mismatch: " + ", ".join(failed))
    return checks


def _canonical_probe_json(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise QualificationFailure("probe stdout must be exactly one JSON line")
    body = raw[:-1]
    try:
        payload = json.loads(body.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationFailure("probe stdout is not ASCII JSON") from exc
    if type(payload) is not dict or _canonical_json_bytes(payload) != body:
        raise QualificationFailure("probe stdout is not canonical JSON")
    return payload


def _limits(
    *,
    wall: int = 5_000,
    cpu: int = 5_000,
    memory: int = 134_217_728,
    writable: int = 8_388_608,
    processes: int = 16,
    stdout: int = 16_384,
    stderr: int = 16_384,
) -> SandboxLimits:
    return SandboxLimits(
        wall_time_ms=wall,
        cpu_time_ms=cpu,
        memory_bytes=memory,
        writable_bytes=writable,
        process_count=processes,
        stdout_bytes=stdout,
        stderr_bytes=stderr,
    )


def _prepare_case(
    *,
    name: str,
    command_argv: tuple[str, ...],
    limits: SandboxLimits,
    configuration: DockerRunnerConfiguration,
    store: FileContentStore,
    work_root: Path,
) -> tuple[ProtectedSandboxSpec, SandboxRequest]:
    repository_root = work_root / name
    if repository_root.exists():
        shutil.rmtree(repository_root)
    repository_root.mkdir(parents=True)
    (repository_root / "module.py").write_bytes(b"VALUE = 1\n")
    repository = snapshot_directory(repository_root, store)

    spec = ProtectedSandboxSpec(
        runner_id=DOCKER_RUNNER_ID,
        runner_configuration_sha256=configuration.sha256,
        environment_image_sha256=configuration.environment_image_sha256,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=command_argv,
        environment=(),
        limits=limits,
    )
    visible_payload = _canonical_json_bytes({"probe": name})
    task_payload_sha256 = content_sha256(visible_payload)
    request = SandboxRequest(
        task=TaskIdentity(
            task_id=f"docker-qualification-{name}",
            task_family="docker-qualification-v1",
            payload_sha256=task_payload_sha256,
        ),
        submission_sha256=store.put_bytes(visible_payload),
        buggy_repository_sha256=repository.manifest_sha256,
        patch_sha256=store.put_bytes(b""),
        runtime_input_sha256=store.put_bytes(b"qualification-input\n"),
        sandbox_spec_sha256=spec.sha256,
    )
    return spec, request


def _cleanup_evidence(
    *,
    docker_executable: str,
    request: SandboxRequest,
    staging_root: Path,
) -> dict[str, Any]:
    prefix = f"pc-{request.sha256[:20]}-"
    command = (
        docker_executable,
        "ps",
        "-aq",
        "--filter",
        f"name={prefix}",
    )
    result = _host_execute(command, 15.0)
    if result.timed_out or result.returncode != 0:
        raise QualificationFailure("could not verify container cleanup")
    stale = [line for line in result.stdout.decode("ascii", errors="strict").splitlines() if line]
    staging_entries = sorted(path.name for path in staging_root.iterdir()) if staging_root.exists() else []
    evidence = {
        "stale_container_count": len(stale),
        "staging_entry_count": len(staging_entries),
    }
    if stale or staging_entries:
        raise QualificationFailure("runner cleanup left container or staging residue")
    return evidence


Verifier = Callable[[SandboxResult, bytes, bytes, dict[str, Any]], dict[str, Any]]


def _execute_probe(
    *,
    name: str,
    command_argv: tuple[str, ...],
    limits: SandboxLimits,
    verifier: Verifier,
    configuration: DockerRunnerConfiguration,
    store: FileContentStore,
    work_root: Path,
    staging_root: Path,
    docker_executable: str,
) -> QualificationProbeRecord:
    spec, request = _prepare_case(
        name=name,
        command_argv=command_argv,
        limits=limits,
        configuration=configuration,
        store=store,
        work_root=work_root,
    )
    executor = _AuditedDockerExecutor(docker_executable)
    runner = DockerSandboxRunner(
        spec=spec,
        configuration=configuration,
        store=store,
        staging_root=staging_root,
        docker_executable=docker_executable,
        command_executor=executor,
    )
    result: SandboxResult | None = None
    evidence: dict[str, Any] = {}
    error: str | None = None

    try:
        result = runner.run(request)
        if executor.create_audit is None:
            raise QualificationFailure("runner did not produce a create-time audit")
        evidence["create_policy"] = _verify_create_audit(
            executor.create_audit,
            configuration=configuration,
            limits=limits,
        )
        stdout = store.get_bytes(result.stdout_sha256)
        stderr = store.get_bytes(result.stderr_sha256)
        evidence["probe"] = verifier(result, stdout, stderr, executor.create_audit)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"[:4096]

    try:
        evidence["cleanup"] = _cleanup_evidence(
            docker_executable=docker_executable,
            request=request,
            staging_root=staging_root,
        )
    except BaseException as exc:
        cleanup_error = f"{type(exc).__name__}: {exc}"[:2048]
        error = cleanup_error if error is None else error + "; " + cleanup_error

    return QualificationProbeRecord(
        name=name,
        passed=error is None,
        request_sha256=request.sha256,
        sandbox_result=None if result is None else result.canonical_payload(),
        evidence=evidence,
        error=error,
    )


def _baseline_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 7 or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure("baseline exit/termination capture mismatch")
    if stdout != b"qualification-stdout\n" or stderr != b"qualification-stderr\n":
        raise QualificationFailure("baseline stdout/stderr capture mismatch")
    return {
        "exit_code": result.exit_code,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


_ISOLATION_SCRIPT = r'''
import errno,json,os
from pathlib import Path

def write_errno(path):
    try:
        Path(path).write_bytes(b"x")
        return 0
    except OSError as exc:
        return int(exc.errno or -1)

status={}
for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
    if line.startswith("CapEff:"):
        status["cap_eff"]=line.split(":",1)[1].strip()
    elif line.startswith("NoNewPrivs:"):
        status["no_new_privs"]=int(line.split(":",1)[1].strip())
secrets=Path("/run/secrets")
payload={
    "uid":os.getuid(),
    "gid":os.getgid(),
    "cap_eff":status.get("cap_eff"),
    "no_new_privs":status.get("no_new_privs"),
    "root_write_errno":write_errno("/qualification-root-write"),
    "input_write_errno":write_errno("/pc-input/runtime-input.bin"),
    "input_entries":sorted(item.name for item in Path("/pc-input").iterdir()),
    "runtime_entries":sorted(item.name for item in Path("/opt/plural-cognition").iterdir()),
    "environment_names":sorted(os.environ),
    "docker_socket_exists":Path("/var/run/docker.sock").exists() or Path("/run/docker.sock").exists(),
    "secret_entries":sorted(item.name for item in secrets.iterdir()) if secrets.exists() else [],
    "root_docker_config_exists":Path("/root/.docker/config.json").exists(),
    "root_gitconfig_exists":Path("/root/.gitconfig").exists(),
    "root_ssh_exists":Path("/root/.ssh").exists(),
}
print(json.dumps(payload,sort_keys=True,separators=(",",":")))
'''.strip()


def _isolation_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("isolation-surface candidate did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    if payload.get("uid") != 65534 or payload.get("gid") != 65534:
        raise QualificationFailure("candidate did not run as nobody:nogroup identity")
    if payload.get("cap_eff") != "0000000000000000" or payload.get("no_new_privs") != 1:
        raise QualificationFailure("candidate retained capabilities or lacks no-new-privileges")
    if payload.get("root_write_errno") == 0 or payload.get("input_write_errno") == 0:
        raise QualificationFailure("candidate could write rootfs or immutable input mount")
    if payload.get("input_entries") != list(_REQUIRED_INPUT_ENTRIES):
        raise QualificationFailure("candidate input surface differs from frozen allow-list")
    runtime_entries = payload.get("runtime_entries")
    if runtime_entries != ["bootstrap.py", "bootstrap_core.py"]:
        raise QualificationFailure("candidate runtime contains unexpected project files")
    env_names = payload.get("environment_names")
    if type(env_names) is not list:
        raise QualificationFailure("candidate environment-name evidence is malformed")
    leaked = sorted(set(env_names).intersection(_FORBIDDEN_ENVIRONMENT_NAMES))
    if leaked:
        raise QualificationFailure("candidate inherited forbidden credential environment names")
    if payload.get("docker_socket_exists"):
        raise QualificationFailure("candidate can see a Docker socket")
    if payload.get("secret_entries"):
        raise QualificationFailure("candidate can see mounted runtime secrets")
    if payload.get("root_docker_config_exists") or payload.get("root_gitconfig_exists") or payload.get("root_ssh_exists"):
        raise QualificationFailure("candidate image exposes root credential/config material")
    return {
        "uid": payload["uid"],
        "gid": payload["gid"],
        "cap_eff": payload["cap_eff"],
        "no_new_privs": payload["no_new_privs"],
        "root_write_errno": payload["root_write_errno"],
        "input_write_errno": payload["input_write_errno"],
        "input_entry_count": len(payload["input_entries"]),
        "forbidden_environment_name_count": len(leaked),
        "docker_socket_exists": False,
        "secret_entry_count": 0,
    }


_NETWORK_SCRIPT = r'''
import json,socket
from pathlib import Path
interfaces=sorted(item.name for item in Path("/sys/class/net").iterdir())
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.settimeout(1.0)
try:
    connect_errno=s.connect_ex(("1.1.1.1",53))
finally:
    s.close()
print(json.dumps({"interfaces":interfaces,"connect_errno":connect_errno},sort_keys=True,separators=(",",":")))
'''.strip()


def _network_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("network probe did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    if payload.get("interfaces") != ["lo"]:
        raise QualificationFailure("network-none container exposes non-loopback interface")
    connect_errno = payload.get("connect_errno")
    if type(connect_errno) is not int or connect_errno == 0:
        raise QualificationFailure("external IPv4 connect unexpectedly succeeded")
    return payload


_FRESH_SCRIPT = r'''
import json
from pathlib import Path
marker=Path("/pc-work/qualification-persistence-marker")
preexisting=marker.exists()
marker.write_bytes(b"marker")
print(json.dumps({"preexisting":preexisting},sort_keys=True,separators=(",",":")))
'''.strip()


def _fresh_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("fresh-workspace probe did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    if payload.get("preexisting") is not False:
        raise QualificationFailure("fresh workspace contained persistence marker")
    return payload


def _timeout_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if not result.timed_out or result.exit_code is not None or result.memory_limit_exceeded:
        raise QualificationFailure("wall-time ceiling did not produce timeout result")
    return {"wall_time_ms": result.resources.wall_time_ms}


def _stdout_limit_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code is not None or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure("stdout overflow termination classification mismatch")
    if len(stdout) != 4096 or stderr:
        raise QualificationFailure("stdout ceiling did not preserve exactly the declared bound")
    return {"captured_stdout_bytes": len(stdout)}


def _stderr_limit_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code is not None or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure("stderr overflow termination classification mismatch")
    if len(stderr) != 4096 or stdout:
        raise QualificationFailure("stderr ceiling did not preserve exactly the declared bound")
    return {"captured_stderr_bytes": len(stderr)}


_MEMORY_SCRIPT = "x=bytearray(1024*1024*1024);print(len(x))"


def _memory_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if not result.memory_limit_exceeded or result.timed_out:
        raise QualificationFailure("memory pressure did not produce explicit OOM evidence")
    if result.resources.peak_ram_bytes <= 0:
        raise QualificationFailure("memory probe lacks peak-memory accounting")
    return {
        "memory_limit_exceeded": True,
        "peak_ram_bytes": result.resources.peak_ram_bytes,
        "candidate_exit_code": result.exit_code,
    }


_PIDS_SCRIPT = r'''
import errno,json,subprocess,sys
from pathlib import Path

def event_max():
    values={}
    for line in Path("/sys/fs/cgroup/pids.events").read_text(encoding="ascii").splitlines():
        key,value=line.split(maxsplit=1)
        values[key]=int(value)
    return values.get("max",0)

before=event_max()
children=[]
failure_errno=0
try:
    for _ in range(64):
        try:
            children.append(subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        except OSError as exc:
            failure_errno=int(exc.errno or -1)
            break
finally:
    after=event_max()
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=1)
print(json.dumps({"started":len(children),"failure_errno":failure_errno,"max_event_delta":after-before},sort_keys=True,separators=(",",":")))
'''.strip()


def _pids_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("PID probe did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    if payload.get("failure_errno") != errno.EAGAIN:
        raise QualificationFailure("PID exhaustion did not fail with EAGAIN")
    if type(payload.get("max_event_delta")) is not int or payload["max_event_delta"] < 1:
        raise QualificationFailure("cgroup pids.events did not record limit enforcement")
    started = payload.get("started")
    if type(started) is not int or started >= 64:
        raise QualificationFailure("PID probe unexpectedly spawned all requested children")
    return payload


_WRITABLE_SCRIPT = r'''
import errno,json,os
path="/pc-work/qualification-fill.bin"
fd=os.open(path,os.O_CREAT|os.O_WRONLY,0o600)
written=0
failure_errno=0
chunk=b"x"*(1024*1024)
try:
    while written < 64*1024*1024:
        try:
            written += os.write(fd,chunk)
        except OSError as exc:
            failure_errno=int(exc.errno or -1)
            break
finally:
    os.close(fd)
print(json.dumps({"written":written,"failure_errno":failure_errno},sort_keys=True,separators=(",",":")))
'''.strip()


def _writable_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("writable-space probe did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    if payload.get("failure_errno") != errno.ENOSPC:
        raise QualificationFailure("tmpfs writable-space exhaustion did not fail with ENOSPC")
    written = payload.get("written")
    if type(written) is not int or written <= 0 or written > 8_388_608:
        raise QualificationFailure("tmpfs wrote beyond declared writable-space ceiling")
    return payload


_CPU_SCRIPT = r'''
import json,time
start=time.monotonic()
deadline=start+2.0
value=0
while time.monotonic()<deadline:
    value=(value*1664525+1013904223)&0xffffffff
elapsed_ms=int((time.monotonic()-start)*1000)
print(json.dumps({"elapsed_ms":elapsed_ms,"value":value},sort_keys=True,separators=(",",":")))
'''.strip()


def _cpu_verifier(result: SandboxResult, stdout: bytes, stderr: bytes, audit: dict[str, Any]) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("CPU-bandwidth probe did not complete cleanly")
    payload = _canonical_probe_json(stdout)
    elapsed = payload.get("elapsed_ms")
    if type(elapsed) is not int or elapsed < 1_800:
        raise QualificationFailure("CPU probe did not run for the intended wall interval")
    if result.resources.cpu_time_ms >= 1_400:
        raise QualificationFailure("observed CPU time is inconsistent with the 0.25 CPU bandwidth ceiling")
    if audit.get("nano_cpus") != 250_000_000:
        raise QualificationFailure("Docker did not apply exact 0.25 NanoCpus limit")
    return {
        "candidate_elapsed_ms": elapsed,
        "observed_cpu_time_ms": result.resources.cpu_time_ms,
        "observed_wall_time_ms": result.resources.wall_time_ms,
        "nano_cpus": audit.get("nano_cpus"),
    }


def run_docker_qualification(
    *,
    image_reference: str,
    software_revision: str,
    expected_engine_sha256: str,
    output: Path,
    evidence_root: Path,
    dockerfile: Path,
    bootstrap_guard: Path,
    bootstrap_core: Path,
    sandbox_contract: Path,
    docker_executable: str = "docker",
) -> DockerQualificationReport:
    """Run the exact Repository Surgery v0 target-machine qualification matrix."""

    _git_revision(software_revision)
    validate_sha256(expected_engine_sha256)
    if not image_reference.startswith("sha256:"):
        raise ValueError("qualification image must be an immutable local sha256 reference")
    validate_sha256(image_reference.split(":", 1)[1])

    evidence_root = Path(evidence_root)
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise ValueError("evidence_root must be absent or empty")
    evidence_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(evidence_root / "store")
    staging_root = evidence_root / "staging"
    staging_root.mkdir()
    work_root = evidence_root / "work"
    work_root.mkdir()

    base_identity = probe_docker_qualification_identity(
        image_reference=_BASE_IMAGE,
        software_revision=software_revision,
        docker_executable=docker_executable,
    )
    engine: DockerEngineIdentity = base_identity.engine
    if engine.sha256 != expected_engine_sha256:
        raise QualificationFailure(
            "Docker Engine fingerprint changed; rerun non-starting identity freeze before qualification"
        )

    local_image: DockerLocalImageIdentity = probe_local_qualification_image(
        image_reference=image_reference,
        software_revision=software_revision,
        dockerfile=Path(dockerfile),
        bootstrap=Path(bootstrap_guard),
        docker_executable=docker_executable,
    )
    if local_image.immutable_reference != image_reference:
        raise QualificationFailure("local image identity does not match requested immutable image")

    core_sha256 = _sha256_file(Path(bootstrap_core))
    if core_sha256 != _EXPECTED_CORE_SHA256:
        raise QualificationFailure("bootstrap core no longer matches guard's frozen SHA-256")

    configuration = DockerRunnerConfiguration(image_reference=image_reference)
    records: list[QualificationProbeRecord] = []

    records.append(
        _execute_probe(
            name="result-capture-and-policy",
            command_argv=(
                "/usr/local/bin/python3",
                "-c",
                "import sys;sys.stdout.write('qualification-stdout\\n');sys.stderr.write('qualification-stderr\\n');raise SystemExit(7)",
            ),
            limits=_limits(),
            verifier=_baseline_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="isolation-surface",
            command_argv=("/usr/local/bin/python3", "-c", _ISOLATION_SCRIPT),
            limits=_limits(),
            verifier=_isolation_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="network-denial",
            command_argv=("/usr/local/bin/python3", "-c", _NETWORK_SCRIPT),
            limits=_limits(),
            verifier=_network_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    for suffix in ("a", "b"):
        records.append(
            _execute_probe(
                name=f"fresh-workspace-{suffix}",
                command_argv=("/usr/local/bin/python3", "-c", _FRESH_SCRIPT),
                limits=_limits(),
                verifier=_fresh_verifier,
                configuration=configuration,
                store=store,
                work_root=work_root,
                staging_root=staging_root,
                docker_executable=docker_executable,
            )
        )
    records.append(
        _execute_probe(
            name="wall-time-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", "import time;time.sleep(10)"),
            limits=_limits(wall=500, cpu=500),
            verifier=_timeout_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="stdout-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", "import os;os.write(1,b'x'*8192)"),
            limits=_limits(stdout=4096),
            verifier=_stdout_limit_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="stderr-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", "import os;os.write(2,b'x'*8192)"),
            limits=_limits(stderr=4096),
            verifier=_stderr_limit_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="memory-oom-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", _MEMORY_SCRIPT),
            limits=_limits(memory=134_217_728, wall=8_000, cpu=8_000),
            verifier=_memory_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="process-count-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", _PIDS_SCRIPT),
            limits=_limits(processes=8, wall=8_000, cpu=8_000),
            verifier=_pids_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="writable-space-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", _WRITABLE_SCRIPT),
            limits=_limits(writable=8_388_608, wall=8_000, cpu=8_000),
            verifier=_writable_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )
    records.append(
        _execute_probe(
            name="cpu-bandwidth-ceiling",
            command_argv=("/usr/local/bin/python3", "-c", _CPU_SCRIPT),
            limits=_limits(wall=4_000, cpu=1_000),
            verifier=_cpu_verifier,
            configuration=configuration,
            store=store,
            work_root=work_root,
            staging_root=staging_root,
            docker_executable=docker_executable,
        )
    )

    shutil.rmtree(work_root)
    if any(staging_root.iterdir()):
        records.append(
            QualificationProbeRecord(
                name="final-staging-cleanup",
                passed=False,
                request_sha256=None,
                sandbox_result=None,
                evidence={"staging_entry_count": len(list(staging_root.iterdir()))},
                error="staging root was non-empty after qualification matrix",
            )
        )

    report = DockerQualificationReport(
        software_revision=software_revision,
        engine_sha256=engine.sha256,
        image_identity_sha256=local_image.sha256,
        immutable_image=local_image.immutable_reference,
        runner_configuration_sha256=configuration.sha256,
        sandbox_contract_sha256=_sha256_file(Path(sandbox_contract)),
        qualification_source_sha256=_sha256_file(Path(__file__)),
        bootstrap_core_sha256=core_sha256,
        bootstrap_guard_sha256=local_image.bootstrap_sha256,
        dockerfile_sha256=local_image.dockerfile_sha256,
        probes=tuple(records),
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(_canonical_json_bytes(report.canonical_payload()))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run project-authored adversarial qualification of the protected Docker runner."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--expected-engine-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--dockerfile", default=Path("docker/protected-runner/Dockerfile"), type=Path)
    parser.add_argument(
        "--bootstrap-guard",
        default=Path("src/plural_cognition/collective/docker_bootstrap_guard.py"),
        type=Path,
    )
    parser.add_argument(
        "--bootstrap-core",
        default=Path("src/plural_cognition/collective/docker_bootstrap.py"),
        type=Path,
    )
    parser.add_argument(
        "--sandbox-contract",
        default=Path("docs/26-protected-sandbox-interface.md"),
        type=Path,
    )
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = run_docker_qualification(
        image_reference=args.image,
        software_revision=args.software_revision,
        expected_engine_sha256=args.expected_engine_sha256,
        output=args.output,
        evidence_root=args.evidence_root,
        dockerfile=args.dockerfile,
        bootstrap_guard=args.bootstrap_guard,
        bootstrap_core=args.bootstrap_core,
        sandbox_contract=args.sandbox_contract,
        docker_executable=args.docker_executable,
    )
    print(f"status={report.status}")
    print(f"report_sha256={report.sha256}")
    print(f"engine_sha256={report.engine_sha256}")
    print(f"image_identity_sha256={report.image_identity_sha256}")
    print(f"immutable_image={report.immutable_image}")
    for probe in report.probes:
        print(f"probe={probe.name}:{'PASS' if probe.passed else 'FAIL'}")
        if probe.error is not None:
            print(f"probe_error={probe.name}:{probe.error}")
    print(f"output={args.output}")
    return 0 if report.status == QUALIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
