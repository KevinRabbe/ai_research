"""Freeze a locally built Docker qualification image by immutable image ID.

Unlike registry images, a local build normally has no RepoDigests entry.  Docker
still assigns it an immutable content-addressed ``sha256:<image-id>``.  This
module binds that ID to the exact Dockerfile, bootstrap bytes, and software
revision without creating or starting a container.
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

DOCKER_LOCAL_IMAGE_IDENTITY_SCHEMA = "plural-cognition-docker-local-image-identity-v1"
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
            f"Docker diagnostic command failed ({completed.returncode}): {argv!r}: {stderr}"
        )
    return completed.stdout


def _json_command(runner: CommandRunner, argv: tuple[str, ...]) -> dict[str, Any]:
    try:
        payload = json.loads(runner(argv).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("docker image inspect returned invalid JSON") from exc
    if type(payload) is not dict:
        raise RuntimeError("docker image inspect did not return a JSON object")
    return payload


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"identity source file does not exist: {path}")
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class DockerLocalImageIdentity:
    software_revision: str
    requested_reference: str
    image_id_sha256: str
    os_type: str
    architecture: str
    size_bytes: int
    dockerfile_sha256: str
    bootstrap_sha256: str

    def __post_init__(self) -> None:
        _git_revision(self.software_revision)
        _nonempty(self.requested_reference, "requested_reference")
        validate_sha256(self.image_id_sha256)
        _nonempty(self.os_type, "os_type")
        _nonempty(self.architecture, "architecture")
        _positive_int(self.size_bytes, "size_bytes")
        validate_sha256(self.dockerfile_sha256)
        validate_sha256(self.bootstrap_sha256)

    @property
    def immutable_reference(self) -> str:
        return "sha256:" + self.image_id_sha256

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": DOCKER_LOCAL_IMAGE_IDENTITY_SCHEMA,
            "software_revision": self.software_revision,
            "requested_reference": self.requested_reference,
            "immutable_reference": self.immutable_reference,
            "image_id_sha256": self.image_id_sha256,
            "os_type": self.os_type,
            "architecture": self.architecture,
            "size_bytes": self.size_bytes,
            "dockerfile_sha256": self.dockerfile_sha256,
            "bootstrap_sha256": self.bootstrap_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


def probe_local_qualification_image(
    *,
    image_reference: str,
    software_revision: str,
    dockerfile: Path,
    bootstrap: Path,
    docker_executable: str = "docker",
    command_runner: CommandRunner | None = None,
) -> DockerLocalImageIdentity:
    """Inspect one already-built local image without starting a container."""

    _git_revision(software_revision)
    _nonempty(image_reference, "image_reference")
    _nonempty(docker_executable, "docker_executable")
    runner = command_runner or _default_command_runner
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
    image_id = image.get("Id")
    if type(image_id) is not str or not image_id.startswith("sha256:"):
        raise RuntimeError("local Docker image Id is not sha256-addressed")
    digest = image_id.split(":", 1)[1]
    validate_sha256(digest)
    os_type = image.get("Os")
    architecture = image.get("Architecture")
    size_bytes = image.get("Size")
    if os_type != "linux":
        raise RuntimeError("protected qualification image must be Linux")
    if architecture not in ("amd64", "x86_64"):
        raise RuntimeError("protected qualification image must be amd64")
    _positive_int(size_bytes, "image Size")

    return DockerLocalImageIdentity(
        software_revision=software_revision,
        requested_reference=image_reference,
        image_id_sha256=digest,
        os_type=os_type,
        architecture=architecture,
        size_bytes=size_bytes,
        dockerfile_sha256=_file_sha256(Path(dockerfile)),
        bootstrap_sha256=_file_sha256(Path(bootstrap)),
    )


def _write_report(report: DockerLocalImageIdentity, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_json_bytes(report.canonical_payload()))
    print(f"image_id_sha256={report.image_id_sha256}")
    print(f"dockerfile_sha256={report.dockerfile_sha256}")
    print(f"bootstrap_sha256={report.bootstrap_sha256}")
    print(f"report_sha256={report.sha256}")
    print(f"immutable_image={report.immutable_reference}")
    print(f"output={output}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze a locally built protected-runner image without starting it."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--dockerfile", required=True, type=Path)
    parser.add_argument("--bootstrap", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    report = probe_local_qualification_image(
        image_reference=args.image,
        software_revision=args.software_revision,
        dockerfile=args.dockerfile,
        bootstrap=args.bootstrap,
        docker_executable=args.docker_executable,
    )
    _write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
