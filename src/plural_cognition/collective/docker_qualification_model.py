"""Immutable evidence model for exact-scope Docker runner qualification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .content_store import validate_sha256

DOCKER_QUALIFICATION_REPORT_SCHEMA = "plural-cognition-docker-runner-qualification-v2"
DOCKER_QUALIFICATION_PROBE_SCHEMA = "plural-cognition-docker-runner-probe-v1"
QUALIFICATION_SCOPE = "repository-surgery-v0"
QUALIFIED = "QUALIFIED"
REJECTED = "REJECTED"


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def validate_git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


class QualificationFailure(RuntimeError):
    """One empirical qualification invariant failed."""


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
    engine_observation_sha256: str
    engine_qualification_sha256: str
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
        validate_git_revision(self.software_revision)
        for digest in (
            self.engine_observation_sha256,
            self.engine_qualification_sha256,
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
            "engine_observation_sha256": self.engine_observation_sha256,
            "engine_qualification_sha256": self.engine_qualification_sha256,
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
        return sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()
