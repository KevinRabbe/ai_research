from __future__ import annotations

import json

import pytest

from plural_cognition.collective.docker_identity import (
    DockerQualificationIdentity,
    probe_docker_qualification_identity,
)


IMAGE_DIGEST = "a" * 64
IMAGE_ID = "b" * 64
REVISION = "c" * 40


def _fixture_runner(*, repo_digests=None, architecture="amd64"):
    responses = {
        ("docker", "version", "--format", "{{json .Client}}"): {
            "Version": "29.7.2",
            "ApiVersion": "1.55",
            "GitCommit": "a7dcaa6",
        },
        ("docker", "version", "--format", "{{json .Server}}"): {
            "Version": "29.7.2",
            "ApiVersion": "1.55",
            "GitCommit": "6a43e3d",
            "Platform": {"Name": "Docker Desktop 4.86.0 (236216)"},
        },
        ("docker", "info", "--format", "{{json .}}"): {
            "OSType": "linux",
            "Architecture": "x86_64",
            "KernelVersion": "6.18.33.2-microsoft-standard-WSL2",
            "OperatingSystem": "Docker Desktop",
            "CgroupVersion": "2",
            "CgroupDriver": "cgroupfs",
            "DockerRootDir": "/var/lib/docker",
            "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
            "NCPU": 24,
            "MemTotal": 16632201216,
        },
        (
            "docker",
            "image",
            "inspect",
            "--format",
            "{{json .}}",
            "python:3.11-slim-bookworm",
        ): {
            "Id": "sha256:" + IMAGE_ID,
            "RepoDigests": repo_digests
            if repo_digests is not None
            else ["python@sha256:" + IMAGE_DIGEST],
            "Os": "linux",
            "Architecture": architecture,
            "Size": 127000000,
        },
    }

    def run(argv: tuple[str, ...]) -> bytes:
        return json.dumps(responses[argv]).encode("utf-8")

    return run


def test_probe_freezes_engine_and_image_identity() -> None:
    report = probe_docker_qualification_identity(
        image_reference="python:3.11-slim-bookworm",
        software_revision=REVISION,
        command_runner=_fixture_runner(),
    )

    assert isinstance(report, DockerQualificationIdentity)
    assert report.engine.client_version == "29.7.2"
    assert report.engine.server_version == "29.7.2"
    assert report.engine.platform_name == "Docker Desktop 4.86.0 (236216)"
    assert report.engine.cgroup_version == "2"
    assert report.engine.security_options == (
        "name=cgroupns",
        "name=seccomp,profile=builtin",
    )
    assert report.image.repo_digest_reference == "python@sha256:" + IMAGE_DIGEST
    assert report.image.image_id_sha256 == IMAGE_ID
    assert report.image.environment_image_sha256 == IMAGE_DIGEST
    assert len(report.engine.sha256) == 64
    assert len(report.image.sha256) == 64
    assert len(report.sha256) == 64


def test_probe_fails_closed_when_image_has_no_registry_digest() -> None:
    with pytest.raises(RuntimeError, match="no immutable RepoDigests"):
        probe_docker_qualification_identity(
            image_reference="python:3.11-slim-bookworm",
            software_revision=REVISION,
            command_runner=_fixture_runner(repo_digests=[]),
        )


def test_probe_rejects_wrong_image_architecture() -> None:
    with pytest.raises(RuntimeError, match="must be amd64"):
        probe_docker_qualification_identity(
            image_reference="python:3.11-slim-bookworm",
            software_revision=REVISION,
            command_runner=_fixture_runner(architecture="arm64"),
        )


def test_probe_rejects_pinned_digest_not_present_locally() -> None:
    runner = _fixture_runner()

    def pinned_runner(argv: tuple[str, ...]) -> bytes:
        if argv[-1].startswith("python@sha256:"):
            argv = argv[:-1] + ("python:3.11-slim-bookworm",)
        return runner(argv)

    with pytest.raises(RuntimeError, match="not present locally"):
        probe_docker_qualification_identity(
            image_reference="python@sha256:" + "d" * 64,
            software_revision=REVISION,
            command_runner=pinned_runner,
        )
