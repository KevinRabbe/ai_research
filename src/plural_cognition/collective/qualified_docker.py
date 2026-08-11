"""Fail-closed binding for the target-qualified protected Docker runner.

The underlying ``docker_runner.py`` remains the exact implementation exercised by
the v10 target-machine qualification.  This module does not alter that security
boundary.  It records the immutable promotion decision and refuses protected use
when the bound runner source/configuration or live stable Engine fingerprint has
drifted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .docker_candidate import DockerRunnerConfiguration
from .docker_engine_fingerprint import qualification_engine_sha256
from .docker_identity import DockerEngineIdentity, probe_docker_qualification_identity
from .docker_qualification import _qualification_source_sha256

QUALIFIED_DOCKER_REPORT_SHA256 = (
    "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"
)
QUALIFIED_DOCKER_SOURCE_REVISION = "8d201c685ecf73917a073093bb057a2178f59d6f"
QUALIFIED_DOCKER_QUALIFICATION_SOURCE_SHA256 = (
    "1a361fee3ba74ba1b85d7d249ced89b624d9d58a907f95bde34d7f24730782e3"
)
QUALIFIED_DOCKER_ENGINE_SHA256 = (
    "8155c7193395faaa6096032249b179926381f069343589f5c40e2ac3f4c14000"
)
QUALIFIED_DOCKER_IMAGE = (
    "sha256:b6b32c4c224d190ff281853aafe6e6d57d0361a32dc7ba11076af6e18892b139"
)
QUALIFIED_DOCKER_IMAGE_IDENTITY_SHA256 = (
    "eb83cb008705c1b4d744f8c3cd44839e0660bc8565d4b7895f6ba12146d7fc75"
)
QUALIFIED_DOCKER_RUNNER_CONFIGURATION_SHA256 = (
    "92c30ff08bff86cac4a584d69d2845a5d7f2b6baf1446d2fe2299aa15d1f39a0"
)
QUALIFICATION_BASE_IMAGE = (
    "python@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3"
)


class QualifiedDockerError(RuntimeError):
    """Raised when protected execution no longer matches the qualified tuple."""


@dataclass(frozen=True, slots=True)
class QualifiedDockerBinding:
    report_sha256: str = QUALIFIED_DOCKER_REPORT_SHA256
    source_revision: str = QUALIFIED_DOCKER_SOURCE_REVISION
    qualification_source_sha256: str = QUALIFIED_DOCKER_QUALIFICATION_SOURCE_SHA256
    engine_qualification_sha256: str = QUALIFIED_DOCKER_ENGINE_SHA256
    immutable_image: str = QUALIFIED_DOCKER_IMAGE
    image_identity_sha256: str = QUALIFIED_DOCKER_IMAGE_IDENTITY_SHA256
    runner_configuration_sha256: str = QUALIFIED_DOCKER_RUNNER_CONFIGURATION_SHA256

    def configuration(self) -> DockerRunnerConfiguration:
        live_source = _qualification_source_sha256()
        if live_source != self.qualification_source_sha256:
            raise QualifiedDockerError(
                "qualified Docker runner source drifted; rerun adversarial qualification"
            )
        configuration = DockerRunnerConfiguration(image_reference=self.immutable_image)
        if configuration.sha256 != self.runner_configuration_sha256:
            raise QualifiedDockerError(
                "qualified Docker runner configuration drifted; rerun adversarial qualification"
            )
        return configuration

    def assert_engine(self, engine: DockerEngineIdentity) -> None:
        if not isinstance(engine, DockerEngineIdentity):
            raise TypeError("engine must be DockerEngineIdentity")
        observed = qualification_engine_sha256(engine)
        if observed != self.engine_qualification_sha256:
            raise QualifiedDockerError(
                "Docker Engine qualification fingerprint drifted; protected execution is blocked"
            )


QUALIFIED_DOCKER = QualifiedDockerBinding()


def probe_qualified_docker_configuration(
    *,
    software_revision: str,
    docker_executable: str = "docker",
) -> DockerRunnerConfiguration:
    """Check the live non-starting Engine surface and return the qualified config.

    This performs Docker version/info/image-inspect diagnostics only.  It does not
    create or start a container.  The returned configuration may then be supplied
    to the exact v10-qualified ``DockerSandboxRunner``.
    """

    configuration = QUALIFIED_DOCKER.configuration()
    identity = probe_docker_qualification_identity(
        image_reference=QUALIFICATION_BASE_IMAGE,
        software_revision=software_revision,
        docker_executable=docker_executable,
    )
    QUALIFIED_DOCKER.assert_engine(identity.engine)
    return configuration
