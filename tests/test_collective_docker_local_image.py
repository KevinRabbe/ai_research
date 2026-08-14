from __future__ import annotations

import json
from pathlib import Path

import pytest

from plural_cognition.collective.docker_local_image import (
    DockerLocalImageIdentity,
    probe_local_qualification_image,
)


IMAGE_ID = "a" * 64
REVISION = "b" * 40


def _runner(*, os_type: str = "linux", architecture: str = "amd64"):
    def run(argv: tuple[str, ...]) -> bytes:
        assert argv[:5] == (
            "docker",
            "image",
            "inspect",
            "--format",
            "{{json .}}",
        )
        return json.dumps(
            {
                "Id": "sha256:" + IMAGE_ID,
                "RepoDigests": [],
                "Os": os_type,
                "Architecture": architecture,
                "Size": 50000000,
            }
        ).encode("utf-8")

    return run


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    dockerfile = tmp_path / "Dockerfile"
    bootstrap = tmp_path / "bootstrap.py"
    dockerfile.write_text("FROM python@sha256:" + "c" * 64 + "\n", encoding="utf-8")
    bootstrap.write_text("print('bootstrap')\n", encoding="utf-8")
    return dockerfile, bootstrap


def test_local_image_identity_uses_immutable_image_id_without_repo_digest(
    tmp_path: Path,
) -> None:
    dockerfile, bootstrap = _sources(tmp_path)
    report = probe_local_qualification_image(
        image_reference="plural-cognition/protected-runner:qualification",
        software_revision=REVISION,
        dockerfile=dockerfile,
        bootstrap=bootstrap,
        command_runner=_runner(),
    )

    assert isinstance(report, DockerLocalImageIdentity)
    assert report.image_id_sha256 == IMAGE_ID
    assert report.immutable_reference == "sha256:" + IMAGE_ID
    assert report.os_type == "linux"
    assert report.architecture == "amd64"
    assert len(report.dockerfile_sha256) == 64
    assert len(report.bootstrap_sha256) == 64
    assert len(report.sha256) == 64


def test_local_image_identity_rejects_non_linux_image(tmp_path: Path) -> None:
    dockerfile, bootstrap = _sources(tmp_path)
    with pytest.raises(RuntimeError, match="must be Linux"):
        probe_local_qualification_image(
            image_reference="local:test",
            software_revision=REVISION,
            dockerfile=dockerfile,
            bootstrap=bootstrap,
            command_runner=_runner(os_type="windows"),
        )


def test_local_image_identity_rejects_wrong_architecture(tmp_path: Path) -> None:
    dockerfile, bootstrap = _sources(tmp_path)
    with pytest.raises(RuntimeError, match="must be amd64"):
        probe_local_qualification_image(
            image_reference="local:test",
            software_revision=REVISION,
            dockerfile=dockerfile,
            bootstrap=bootstrap,
            command_runner=_runner(architecture="arm64"),
        )
