"""Fail-closed Docker candidate adapter for protected Repository Surgery execution.

This module does not qualify Docker as a security boundary. It prepares a
solver-visible input bundle and converts a frozen ``ProtectedSandboxSpec`` into
a deterministic Docker create/start/inspect/remove command plan whose controls
can later be exercised by target-machine containment tests.

No Docker command is executed here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
from hashlib import sha256
from pathlib import Path
from typing import Any

from .content_store import ContentStore, content_sha256, validate_sha256
from .repository import load_repository_snapshot, materialize_repository_snapshot
from .sandbox import NetworkPolicy, ProtectedSandboxSpec, SandboxRequest

DOCKER_INPUT_BUNDLE_SCHEMA = "plural-cognition-docker-input-bundle-v1"
DOCKER_RUNNER_CONFIGURATION_SCHEMA = "plural-cognition-docker-runner-configuration-v1"
DOCKER_RUNNER_ID = "docker-linux-v1"

_BUNDLE_FILENAMES = (
    "bundle-manifest.json",
    "candidate.patch",
    "request.json",
    "runtime-input.bin",
    "sandbox-spec.json",
    "submission.json",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")


def _absolute_container_path(value: str, field: str) -> None:
    _nonempty(value, field)
    if not value.startswith("/") or "//" in value or "\x00" in value:
        raise ValueError(f"{field} must be a normalized absolute container path")
    if any(part in ("", ".", "..") for part in value.split("/")[1:]):
        raise ValueError(f"{field} must not contain empty, dot, or parent components")


def _pinned_image_digest(image_reference: str) -> str:
    """Return the digest from an immutable Docker image reference.

    Qualification may bind either a registry repository digest
    (``name@sha256:<digest>``) or a local immutable image ID
    (``sha256:<digest>``). Mutable tags are rejected.
    """

    _nonempty(image_reference, "image_reference")
    local_marker = "sha256:"
    repository_marker = "@sha256:"

    if image_reference.startswith(local_marker):
        digest = image_reference[len(local_marker) :]
        if repository_marker in digest or ":" in digest or "@" in digest:
            raise ValueError("local image_reference must contain exactly one sha256 digest")
        validate_sha256(digest)
        return digest

    if repository_marker in image_reference:
        name, digest = image_reference.rsplit(repository_marker, 1)
        if not name or repository_marker in name or image_reference.count(repository_marker) != 1:
            raise ValueError("image_reference must contain exactly one digest pin")
        validate_sha256(digest)
        return digest

    raise ValueError(
        "image_reference must be immutable: sha256:<digest> or name@sha256:<digest>"
    )


def _cpu_quota_text(cpu_time_ms: int, wall_time_ms: int) -> str:
    # Docker's --cpus is a CFS bandwidth limit. Rounding upward avoids a zero
    # value (which Docker interprets as unlimited); aggregate CPU-time compliance
    # remains an empirical qualification requirement.
    ratio = Decimal(cpu_time_ms) / Decimal(wall_time_ms)
    quantum = Decimal("0.000001")
    rounded = ratio.quantize(quantum, rounding=ROUND_UP)
    if rounded <= 0:
        rounded = quantum
    return format(rounded, "f")


def _prepare_empty_directory(path: str | Path) -> Path:
    destination = Path(path)
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("bundle destination must be a real directory")
        if any(destination.iterdir()):
            raise ValueError("bundle destination must be empty")
    else:
        destination.mkdir(parents=True)
    return destination.resolve()


def _mount_source(path: str | Path) -> str:
    source = Path(path).resolve()
    if not source.is_dir():
        raise ValueError("input_bundle_directory must be an existing directory")
    required = {*_BUNDLE_FILENAMES, "repository"}
    if not required.issubset({item.name for item in source.iterdir()}):
        raise ValueError("input bundle is incomplete")
    text = str(source)
    if "\x00" in text or "," in text:
        raise ValueError("input bundle path contains characters unsafe for Docker --mount")
    return text


@dataclass(frozen=True, slots=True)
class DockerInputBundle:
    root: Path
    manifest_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise ValueError("root must be an absolute Path")
        validate_sha256(self.manifest_sha256)


def prepare_docker_input_bundle(
    *,
    request: SandboxRequest,
    spec: ProtectedSandboxSpec,
    store: ContentStore,
    destination: str | Path,
) -> DockerInputBundle:
    """Materialize only candidate-visible execution material into a new bundle."""

    if not isinstance(request, SandboxRequest):
        raise TypeError("request must be SandboxRequest")
    if not isinstance(spec, ProtectedSandboxSpec):
        raise TypeError("spec must be ProtectedSandboxSpec")
    if request.sandbox_spec_sha256 != spec.sha256:
        raise ValueError("request does not bind the supplied sandbox specification")
    if not store.contains(request.submission_sha256):
        raise ValueError("submission artifact is missing from the content store")

    root = _prepare_empty_directory(destination)
    repository = load_repository_snapshot(request.buggy_repository_sha256, store)
    repository_path = root / "repository"
    materialize_repository_snapshot(repository, repository_path, store)

    submission = store.get_bytes(request.submission_sha256)
    patch = store.get_bytes(request.patch_sha256)
    runtime_input = store.get_bytes(request.runtime_input_sha256)
    request_bytes = _canonical_json_bytes(request.canonical_payload())
    spec_bytes = _canonical_json_bytes(spec.canonical_payload())

    (root / "submission.json").write_bytes(submission)
    (root / "candidate.patch").write_bytes(patch)
    (root / "runtime-input.bin").write_bytes(runtime_input)
    (root / "request.json").write_bytes(request_bytes)
    (root / "sandbox-spec.json").write_bytes(spec_bytes)

    manifest = {
        "schema": DOCKER_INPUT_BUNDLE_SCHEMA,
        "request_sha256": request.sha256,
        "sandbox_spec_sha256": spec.sha256,
        "submission_sha256": request.submission_sha256,
        "buggy_repository_sha256": request.buggy_repository_sha256,
        "patch_sha256": request.patch_sha256,
        "runtime_input_sha256": request.runtime_input_sha256,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    manifest_sha256 = store.put_bytes(manifest_bytes)
    if manifest_sha256 != content_sha256(manifest_bytes):
        raise AssertionError("content store returned inconsistent bundle-manifest identity")
    (root / "bundle-manifest.json").write_bytes(manifest_bytes)
    return DockerInputBundle(root=root, manifest_sha256=manifest_sha256)


@dataclass(frozen=True, slots=True)
class DockerRunnerConfiguration:
    """Hash-bound Docker policy that is independent of one task request."""

    image_reference: str
    platform: str = "linux/amd64"
    candidate_uid: int = 65534
    candidate_gid: int = 65534
    input_mount_target: str = "/pc-input"
    workspace_target: str = "/pc-work"
    bootstrap_argv: tuple[str, ...] = (
        "/usr/local/bin/python3",
        "/opt/plural-cognition/bootstrap.py",
        "--request",
        "/pc-input/request.json",
        "--sandbox-spec",
        "/pc-input/sandbox-spec.json",
    )

    def __post_init__(self) -> None:
        _pinned_image_digest(self.image_reference)
        _nonempty(self.platform, "platform")
        for field in ("candidate_uid", "candidate_gid"):
            value = getattr(self, field)
            if type(value) is not int or value < 1:
                raise ValueError(f"{field} must be a positive integer")
        _absolute_container_path(self.input_mount_target, "input_mount_target")
        _absolute_container_path(self.workspace_target, "workspace_target")
        if self.input_mount_target == self.workspace_target:
            raise ValueError("input and workspace targets must be distinct")
        if not self.bootstrap_argv:
            raise ValueError("bootstrap_argv must not be empty")
        if any(
            type(item) is not str or not item or "\x00" in item
            for item in self.bootstrap_argv
        ):
            raise ValueError("bootstrap_argv entries must be non-empty NUL-free strings")

    @property
    def runner_id(self) -> str:
        return DOCKER_RUNNER_ID

    @property
    def environment_image_sha256(self) -> str:
        return _pinned_image_digest(self.image_reference)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_RUNNER_CONFIGURATION_SCHEMA,
            "runner_id": self.runner_id,
            "image_reference": self.image_reference,
            "platform": self.platform,
            "candidate_uid": self.candidate_uid,
            "candidate_gid": self.candidate_gid,
            "input_mount_target": self.input_mount_target,
            "workspace_target": self.workspace_target,
            "bootstrap_argv": list(self.bootstrap_argv),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class DockerCommandPlan:
    """Non-executing command plan used by later target-machine qualification."""

    create_argv: tuple[str, ...]
    start_argv: tuple[str, ...]
    inspect_argv: tuple[str, ...]
    remove_argv: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ("create_argv", "start_argv", "inspect_argv", "remove_argv"):
            value = getattr(self, field)
            if type(value) is not tuple or not value:
                raise ValueError(f"{field} must be a non-empty tuple")
            if any(
                type(item) is not str or not item or "\x00" in item for item in value
            ):
                raise ValueError(
                    f"{field} entries must be non-empty NUL-free strings"
                )


def build_docker_command_plan(
    *,
    spec: ProtectedSandboxSpec,
    configuration: DockerRunnerConfiguration,
    input_bundle_directory: str | Path,
    container_name: str,
    docker_executable: str = "docker",
) -> DockerCommandPlan:
    """Build a locked-down Docker command plan without starting a container."""

    if not isinstance(spec, ProtectedSandboxSpec):
        raise TypeError("spec must be ProtectedSandboxSpec")
    if not isinstance(configuration, DockerRunnerConfiguration):
        raise TypeError("configuration must be DockerRunnerConfiguration")
    _nonempty(docker_executable, "docker_executable")
    _nonempty(container_name, "container_name")
    allowed_name_characters = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
    )
    if any(character not in allowed_name_characters for character in container_name):
        raise ValueError("container_name contains unsupported characters")
    if spec.runner_id != configuration.runner_id:
        raise ValueError("sandbox spec runner_id does not match Docker configuration")
    if spec.runner_configuration_sha256 != configuration.sha256:
        raise ValueError(
            "sandbox spec does not bind this Docker runner configuration"
        )
    if spec.environment_image_sha256 != configuration.environment_image_sha256:
        raise ValueError(
            "sandbox spec image digest does not match pinned Docker image"
        )
    if spec.network_policy is not NetworkPolicy.DISABLED:
        raise ValueError("Docker protected execution requires disabled networking")

    source = _mount_source(input_bundle_directory)
    limits = spec.limits
    cpu_quota = _cpu_quota_text(limits.cpu_time_ms, limits.wall_time_ms)

    create: list[str] = [
        docker_executable,
        "create",
        "--name",
        container_name,
        "--platform",
        configuration.platform,
        "--pull",
        "never",
        "--network",
        "none",
        "--ipc",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        str(limits.process_count),
        "--memory",
        f"{limits.memory_bytes}b",
        "--memory-swap",
        f"{limits.memory_bytes}b",
        "--memory-swappiness",
        "0",
        "--cpus",
        cpu_quota,
        "--restart",
        "no",
        "--user",
        f"{configuration.candidate_uid}:{configuration.candidate_gid}",
        "--workdir",
        configuration.workspace_target,
        "--mount",
        (
            f"type=bind,src={source},dst={configuration.input_mount_target},"
            "readonly,bind-propagation=rprivate,bind-recursive=readonly"
        ),
        "--tmpfs",
        (
            f"{configuration.workspace_target}:"
            f"rw,noexec,nosuid,size={limits.writable_bytes}"
        ),
    ]

    for name, value in spec.environment:
        create.extend(("--env", f"{name}={value}"))

    create.append(configuration.image_reference)
    create.extend(configuration.bootstrap_argv)

    return DockerCommandPlan(
        create_argv=tuple(create),
        start_argv=(docker_executable, "start", "--attach", container_name),
        inspect_argv=(
            docker_executable,
            "inspect",
            "--format",
            "{{json .State}}",
            container_name,
        ),
        remove_argv=(docker_executable, "rm", "--force", container_name),
    )
