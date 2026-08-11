"""Freeze exact Docker Engine and local OCI image identities without execution.

This diagnostic module never creates or starts a container. It records the
Engine surface exposed by ``docker version`` / ``docker info`` and resolves an
already-present image tag to an immutable repository digest using
``docker image inspect``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Sequence

from .content_store import validate_sha256

DOCKER_ENGINE_IDENTITY_SCHEMA = "plural-cognition-docker-engine-identity-v1"
DOCKER_IMAGE_IDENTITY_SCHEMA = "plural-cognition-docker-image-identity-v1"
DOCKER_QUALIFICATION_IDENTITY_SCHEMA = (
    "plural-cognition-docker-qualification-identity-v1"
)

CommandRunner = Callable[[tuple[str, ...]], bytes]


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


def _git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _default_command_runner(argv: tuple[str, ...]) -> bytes:
    completed = subprocess.run(
        argv,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        shell=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Docker diagnostic command failed ({completed.returncode}): "
            f"{argv!r}: {stderr}"
        )
    return completed.stdout


def _json_command(runner: CommandRunner, argv: tuple[str, ...]) -> dict[str, Any]:
    raw = runner(argv)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Docker command returned invalid JSON: {argv!r}") from exc
    if type(value) is not dict:
        raise RuntimeError(f"Docker command did not return a JSON object: {argv!r}")
    return value


def _string_field(payload: dict[str, Any], key: str, *, field: str) -> str:
    value = payload.get(key)
    _nonempty(value, field)
    return value


def _repo_name(reference: str) -> str:
    without_digest = reference.split("@", 1)[0]
    last_slash = without_digest.rfind("/")
    last_colon = without_digest.rfind(":")
    if last_colon > last_slash:
        without_digest = without_digest[:last_colon]
    return without_digest


def _resolve_repo_digest(reference: str, repo_digests: Sequence[str]) -> str:
    _nonempty(reference, "image_reference")
    normalized: list[str] = []
    for item in repo_digests:
        if type(item) is not str or "@sha256:" not in item:
            raise RuntimeError("docker image inspect returned an invalid RepoDigests entry")
        digest = item.rsplit("@sha256:", 1)[1]
        validate_sha256(digest)
        normalized.append(item)

    if "@sha256:" in reference:
        requested_digest = reference.rsplit("@sha256:", 1)[1]
        validate_sha256(requested_digest)
        matches = [
            item for item in normalized if item.endswith("@sha256:" + requested_digest)
        ]
        if len(matches) != 1:
            raise RuntimeError("requested pinned image digest is not present locally")
        return matches[0]

    wanted_repo = _repo_name(reference)
    matches = [item for item in normalized if item.split("@", 1)[0] == wanted_repo]
    if len(matches) != 1:
        raise RuntimeError(
            "image tag must resolve to exactly one local repository digest for its repository"
        )
    return matches[0]


@dataclass(frozen=True, slots=True)
class DockerEngineIdentity:
    client_version: str
    client_api_version: str
    client_git_commit: str
    server_version: str
    server_api_version: str
    server_git_commit: str
    platform_name: str
    os_type: str
    architecture: str
    kernel_version: str
    operating_system: str
    cgroup_version: str
    cgroup_driver: str
    docker_root_dir: str
    security_options: tuple[str, ...]
    ncpu: int
    memory_bytes: int

    def __post_init__(self) -> None:
        for field in (
            "client_version",
            "client_api_version",
            "client_git_commit",
            "server_version",
            "server_api_version",
            "server_git_commit",
            "platform_name",
            "os_type",
            "architecture",
            "kernel_version",
            "operating_system",
            "cgroup_version",
            "cgroup_driver",
            "docker_root_dir",
        ):
            _nonempty(getattr(self, field), field)
        _positive_int(self.ncpu, "ncpu")
        _positive_int(self.memory_bytes, "memory_bytes")
        if any(type(item) is not str or not item for item in self.security_options):
            raise ValueError("security_options entries must be non-empty strings")
        if self.security_options != tuple(sorted(set(self.security_options))):
            raise ValueError("security_options must be sorted and unique")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_ENGINE_IDENTITY_SCHEMA,
            "client_version": self.client_version,
            "client_api_version": self.client_api_version,
            "client_git_commit": self.client_git_commit,
            "server_version": self.server_version,
            "server_api_version": self.server_api_version,
            "server_git_commit": self.server_git_commit,
            "platform_name": self.platform_name,
            "os_type": self.os_type,
            "architecture": self.architecture,
            "kernel_version": self.kernel_version,
            "operating_system": self.operating_system,
            "cgroup_version": self.cgroup_version,
            "cgroup_driver": self.cgroup_driver,
            "docker_root_dir": self.docker_root_dir,
            "security_options": list(self.security_options),
            "ncpu": self.ncpu,
            "memory_bytes": self.memory_bytes,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class DockerImageIdentity:
    requested_reference: str
    repo_digest_reference: str
    image_id_sha256: str
    os_type: str
    architecture: str
    size_bytes: int

    def __post_init__(self) -> None:
        _nonempty(self.requested_reference, "requested_reference")
        if "@sha256:" not in self.repo_digest_reference:
            raise ValueError("repo_digest_reference must be digest pinned")
        repo_digest = self.repo_digest_reference.rsplit("@sha256:", 1)[1]
        validate_sha256(repo_digest)
        validate_sha256(self.image_id_sha256)
        _nonempty(self.os_type, "os_type")
        _nonempty(self.architecture, "architecture")
        _positive_int(self.size_bytes, "size_bytes")

    @property
    def environment_image_sha256(self) -> str:
        return self.repo_digest_reference.rsplit("@sha256:", 1)[1]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_IMAGE_IDENTITY_SCHEMA,
            "requested_reference": self.requested_reference,
            "repo_digest_reference": self.repo_digest_reference,
            "image_id_sha256": self.image_id_sha256,
            "os_type": self.os_type,
            "architecture": self.architecture,
            "size_bytes": self.size_bytes,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class DockerQualificationIdentity:
    software_revision: str
    engine: DockerEngineIdentity
    image: DockerImageIdentity

    def __post_init__(self) -> None:
        _git_revision(self.software_revision)
        if not isinstance(self.engine, DockerEngineIdentity):
            raise TypeError("engine must be DockerEngineIdentity")
        if not isinstance(self.image, DockerImageIdentity):
            raise TypeError("image must be DockerImageIdentity")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_QUALIFICATION_IDENTITY_SCHEMA,
            "software_revision": self.software_revision,
            "engine": self.engine.canonical_payload(),
            "image": self.image.canonical_payload(),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


def probe_docker_qualification_identity(
    *,
    image_reference: str,
    software_revision: str,
    docker_executable: str = "docker",
    command_runner: CommandRunner | None = None,
) -> DockerQualificationIdentity:
    """Inspect an available Engine and already-present image without starting it."""

    _git_revision(software_revision)
    _nonempty(docker_executable, "docker_executable")
    runner = command_runner or _default_command_runner

    client = _json_command(
        runner,
        (docker_executable, "version", "--format", "{{json .Client}}"),
    )
    server = _json_command(
        runner,
        (docker_executable, "version", "--format", "{{json .Server}}"),
    )
    info = _json_command(
        runner,
        (docker_executable, "info", "--format", "{{json .}}"),
    )
    image = _json_command(
        runner,
        (
            docker_executable,
            "image",
            "inspect",
            "--format",
            "{{json .}}",
            image_reference,
        ),
    )

    platform = server.get("Platform")
    if type(platform) is not dict:
        raise RuntimeError("docker version server payload lacks Platform")
    security_options = info.get("SecurityOptions")
    if type(security_options) is not list:
        raise RuntimeError("docker info payload lacks SecurityOptions")
    repo_digests = image.get("RepoDigests")
    if type(repo_digests) is not list or not repo_digests:
        raise RuntimeError("image has no immutable RepoDigests; pull a registry image first")

    image_id = _string_field(image, "Id", field="image Id")
    if not image_id.startswith("sha256:"):
        raise RuntimeError("docker image Id is not sha256-addressed")
    image_id_digest = image_id.split(":", 1)[1]
    validate_sha256(image_id_digest)

    engine_identity = DockerEngineIdentity(
        client_version=_string_field(client, "Version", field="client Version"),
        client_api_version=_string_field(
            client, "ApiVersion", field="client ApiVersion"
        ),
        client_git_commit=_string_field(
            client, "GitCommit", field="client GitCommit"
        ),
        server_version=_string_field(server, "Version", field="server Version"),
        server_api_version=_string_field(
            server, "ApiVersion", field="server ApiVersion"
        ),
        server_git_commit=_string_field(
            server, "GitCommit", field="server GitCommit"
        ),
        platform_name=_string_field(platform, "Name", field="server Platform.Name"),
        os_type=_string_field(info, "OSType", field="info OSType"),
        architecture=_string_field(info, "Architecture", field="info Architecture"),
        kernel_version=_string_field(
            info, "KernelVersion", field="info KernelVersion"
        ),
        operating_system=_string_field(
            info, "OperatingSystem", field="info OperatingSystem"
        ),
        cgroup_version=str(info.get("CgroupVersion")),
        cgroup_driver=_string_field(
            info, "CgroupDriver", field="info CgroupDriver"
        ),
        docker_root_dir=_string_field(
            info, "DockerRootDir", field="info DockerRootDir"
        ),
        security_options=tuple(sorted(set(security_options))),
        ncpu=info.get("NCPU"),
        memory_bytes=info.get("MemTotal"),
    )
    image_identity = DockerImageIdentity(
        requested_reference=image_reference,
        repo_digest_reference=_resolve_repo_digest(image_reference, repo_digests),
        image_id_sha256=image_id_digest,
        os_type=_string_field(image, "Os", field="image Os"),
        architecture=_string_field(
            image, "Architecture", field="image Architecture"
        ),
        size_bytes=image.get("Size"),
    )
    if engine_identity.os_type != "linux":
        raise RuntimeError("protected Docker qualification requires a Linux Engine")
    if image_identity.os_type != "linux":
        raise RuntimeError("protected Docker image must be Linux")
    if image_identity.architecture not in ("amd64", "x86_64"):
        raise RuntimeError("protected Docker image must be amd64 on this target")

    return DockerQualificationIdentity(
        software_revision=software_revision,
        engine=engine_identity,
        image=image_identity,
    )


def _write_report(report: DockerQualificationIdentity, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_json_bytes(report.canonical_payload())
    output.write_bytes(raw)
    print(f"engine_sha256={report.engine.sha256}")
    print(f"image_sha256={report.image.sha256}")
    print(f"environment_image_sha256={report.image.environment_image_sha256}")
    print(f"report_sha256={report.sha256}")
    print(f"pinned_image={report.image.repo_digest_reference}")
    print(f"output={output}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze Docker Engine and local image identity without starting a container."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = probe_docker_qualification_identity(
        image_reference=args.image,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    _write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
