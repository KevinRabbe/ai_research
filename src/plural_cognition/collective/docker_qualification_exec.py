"""Host-side execution and applied-policy audit helpers for Docker qualification."""

from __future__ import annotations

import json
import shutil
import subprocess
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any, Callable

from .artifacts import TaskIdentity
from .content_store import FileContentStore, content_sha256
from .docker_candidate import DOCKER_RUNNER_ID, DockerRunnerConfiguration
from .docker_qualification_model import (
    QualificationFailure,
    QualificationProbeRecord,
    canonical_json_bytes,
)
from .docker_runner import DockerCommandResult, DockerSandboxRunner
from .repository import snapshot_directory
from .sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
    SandboxRequest,
    SandboxResult,
)


def cpu_quota_text(cpu_time_ms: int, wall_time_ms: int) -> str:
    ratio = Decimal(cpu_time_ms) / Decimal(wall_time_ms)
    rounded = ratio.quantize(Decimal("0.000001"), rounding=ROUND_UP)
    if rounded <= 0:
        rounded = Decimal("0.000001")
    return format(rounded, "f")


def expected_nano_cpus(limits: SandboxLimits) -> int:
    return int(
        Decimal(cpu_quota_text(limits.cpu_time_ms, limits.wall_time_ms))
        * Decimal(1_000_000_000)
    )


def host_execute(argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
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


def json_host_command(argv: tuple[str, ...], timeout_seconds: float = 15.0) -> Any:
    result = host_execute(argv, timeout_seconds)
    if result.timed_out or result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:1024]
        raise QualificationFailure(f"host Docker diagnostic failed: {argv!r}: {detail}")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationFailure(
            f"host Docker diagnostic returned invalid JSON: {argv!r}"
        ) from exc


class AuditedDockerExecutor:
    """Execute runner argv and record a sanitized post-create policy snapshot."""

    def __init__(self, docker_executable: str) -> None:
        self.docker_executable = docker_executable
        self.container_name: str | None = None
        self.create_audit: dict[str, Any] | None = None
        self.audit_error: str | None = None

    def __call__(
        self, argv: tuple[str, ...], timeout_seconds: float
    ) -> DockerCommandResult:
        result = host_execute(argv, timeout_seconds)
        if (
            len(argv) > 1
            and argv[1] == "create"
            and not result.timed_out
            and result.returncode == 0
        ):
            try:
                index = argv.index("--name")
                self.container_name = argv[index + 1]
                raw = json_host_command(
                    (
                        self.docker_executable,
                        "inspect",
                        "--format",
                        "{{json .}}",
                        self.container_name,
                    )
                )
                if type(raw) is not dict:
                    raise QualificationFailure(
                        "docker inspect create audit is not an object"
                    )
                self.create_audit = sanitize_create_audit(raw)
            except BaseException as exc:
                # Do not throw here: DockerSandboxRunner must first mark the
                # successfully created container as created so its finally block
                # can remove it. The qualification verifier fails afterward.
                self.audit_error = f"{type(exc).__name__}: {exc}"[:2048]
        return result


def _list_field(host: dict[str, Any], name: str) -> list[Any]:
    value = host.get(name)
    return [] if value is None else list(value)


def sanitize_create_audit(raw: dict[str, Any]) -> dict[str, Any]:
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
        "cap_drop": sorted(str(item) for item in _list_field(host, "CapDrop")),
        "security_opt": sorted(str(item) for item in _list_field(host, "SecurityOpt")),
        "devices": _list_field(host, "Devices"),
        "device_requests": _list_field(host, "DeviceRequests"),
        "port_bindings": host.get("PortBindings") or {},
        "mounts": sanitized_mounts,
        "tmpfs": {str(key): str(value) for key, value in sorted(tmpfs.items())},
    }


def verify_create_audit(
    audit: dict[str, Any],
    *,
    configuration: DockerRunnerConfiguration,
    limits: SandboxLimits,
) -> dict[str, bool]:
    checks: dict[str, bool] = {
        "user": audit.get("user")
        == f"{configuration.candidate_uid}:{configuration.candidate_gid}",
        "network_none": audit.get("network_mode") == "none",
        "ipc_none": audit.get("ipc_mode") == "none",
        "pid_namespace_not_host": audit.get("pid_mode") != "host",
        "cgroup_namespace_not_host": audit.get("cgroupns_mode") != "host",
        "not_privileged": audit.get("privileged") is False,
        "readonly_rootfs": audit.get("readonly_rootfs") is True,
        "pids_limit": audit.get("pids_limit") == limits.process_count,
        "memory_limit": audit.get("memory") == limits.memory_bytes,
        "memory_swap_limit": audit.get("memory_swap") == limits.memory_bytes,
        "cpu_quota": audit.get("nano_cpus") == expected_nano_cpus(limits),
        "restart_disabled": audit.get("restart_policy") == "no",
        "capabilities_dropped": any(
            str(item).upper() == "ALL" for item in audit.get("cap_drop", [])
        ),
        "no_new_privileges": any(
            str(item).replace(":", "=").lower() == "no-new-privileges=true"
            for item in audit.get("security_opt", [])
        ),
        "no_devices": audit.get("devices") == []
        and audit.get("device_requests") == [],
        "no_ports": audit.get("port_bindings") == {},
    }

    mounts = audit.get("mounts")
    if type(mounts) is not list:
        mounts = []
    bind_mounts = [item for item in mounts if item.get("type") == "bind"]
    other_mounts = [item for item in mounts if item.get("type") != "bind"]
    checks["only_readonly_input_bind"] = bind_mounts == [
        {
            "type": "bind",
            "destination": configuration.input_mount_target,
            "rw": False,
        }
    ]
    checks["no_unexpected_mounts"] = all(
        item.get("type") == "tmpfs"
        and item.get("destination") == configuration.workspace_target
        for item in other_mounts
    )

    tmpfs = audit.get("tmpfs")
    tmpfs_value = (
        tmpfs.get(configuration.workspace_target, "") if type(tmpfs) is dict else ""
    )
    tmpfs_options = {
        option.strip() for option in tmpfs_value.split(",") if option.strip()
    }
    checks["bounded_workspace_tmpfs"] = {
        "noexec",
        "nosuid",
        f"size={limits.writable_bytes}",
    }.issubset(tmpfs_options)
    checks["workspace_tmpfs_writable"] = "rw" in tmpfs_options and "ro" not in tmpfs_options
    checks["workspace_tmpfs_mode"] = "mode=0700" in tmpfs_options
    checks["workspace_tmpfs_owner"] = {
        f"uid={configuration.candidate_uid}",
        f"gid={configuration.candidate_gid}",
    }.issubset(tmpfs_options)

    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise QualificationFailure(
            "Docker create policy mismatch: " + ", ".join(failed)
        )
    return checks


def canonical_probe_json(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise QualificationFailure("probe stdout must be exactly one JSON line")
    body = raw[:-1]
    try:
        payload = json.loads(body.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationFailure("probe stdout is not ASCII JSON") from exc
    if type(payload) is not dict or canonical_json_bytes(payload) != body:
        raise QualificationFailure("probe stdout is not canonical JSON")
    return payload


def limits(
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


def prepare_case(
    *,
    name: str,
    command_argv: tuple[str, ...],
    case_limits: SandboxLimits,
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
        limits=case_limits,
    )
    visible_payload = canonical_json_bytes({"probe": name})
    request = SandboxRequest(
        task=TaskIdentity(
            task_id=f"docker-qualification-{name}",
            task_family="docker-qualification-v1",
            payload_sha256=content_sha256(visible_payload),
        ),
        submission_sha256=store.put_bytes(visible_payload),
        buggy_repository_sha256=repository.manifest_sha256,
        patch_sha256=store.put_bytes(b""),
        runtime_input_sha256=store.put_bytes(b"qualification-input\n"),
        sandbox_spec_sha256=spec.sha256,
    )
    return spec, request


def cleanup_evidence(
    *,
    docker_executable: str,
    request: SandboxRequest,
    staging_root: Path,
) -> dict[str, int]:
    prefix = f"pc-{request.sha256[:20]}-"
    result = host_execute(
        (
            docker_executable,
            "ps",
            "-aq",
            "--filter",
            f"name={prefix}",
        ),
        15.0,
    )
    if result.timed_out or result.returncode != 0:
        raise QualificationFailure("could not verify container cleanup")
    try:
        stale = [
            line
            for line in result.stdout.decode("ascii").splitlines()
            if line
        ]
    except UnicodeDecodeError as exc:
        raise QualificationFailure("container cleanup query was not ASCII") from exc
    staging_entries = (
        sorted(path.name for path in staging_root.iterdir())
        if staging_root.exists()
        else []
    )
    evidence = {
        "stale_container_count": len(stale),
        "staging_entry_count": len(staging_entries),
    }
    if stale or staging_entries:
        raise QualificationFailure(
            "runner cleanup left container or staging residue"
        )
    return evidence


Verifier = Callable[[SandboxResult, bytes, bytes, dict[str, Any]], dict[str, Any]]


def execute_probe(
    *,
    name: str,
    command_argv: tuple[str, ...],
    case_limits: SandboxLimits,
    verifier: Verifier,
    configuration: DockerRunnerConfiguration,
    store: FileContentStore,
    work_root: Path,
    staging_root: Path,
    docker_executable: str,
) -> QualificationProbeRecord:
    spec, request = prepare_case(
        name=name,
        command_argv=command_argv,
        case_limits=case_limits,
        configuration=configuration,
        store=store,
        work_root=work_root,
    )
    executor = AuditedDockerExecutor(docker_executable)
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
        if executor.audit_error is not None:
            raise QualificationFailure(
                "create-time policy audit failed: " + executor.audit_error
            )
        if executor.create_audit is None:
            raise QualificationFailure(
                "runner did not produce a create-time policy audit"
            )
        evidence["create_policy"] = verify_create_audit(
            executor.create_audit,
            configuration=configuration,
            limits=case_limits,
        )
        stdout = store.get_bytes(result.stdout_sha256)
        stderr = store.get_bytes(result.stderr_sha256)
        evidence["probe"] = verifier(
            result, stdout, stderr, executor.create_audit
        )
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"[:4096]

    try:
        evidence["cleanup"] = cleanup_evidence(
            docker_executable=docker_executable,
            request=request,
            staging_root=staging_root,
        )
    except BaseException as exc:
        cleanup_error = f"{type(exc).__name__}: {exc}"[:2048]
        error = (
            cleanup_error if error is None else error + "; " + cleanup_error
        )

    return QualificationProbeRecord(
        name=name,
        passed=error is None,
        request_sha256=request.sha256,
        sandbox_result=None if result is None else result.canonical_payload(),
        evidence=evidence,
        error=error,
    )
