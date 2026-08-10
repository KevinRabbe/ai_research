"""Protected, resource-bounded execution contracts for untrusted candidate patches.

This module deliberately defines no host executor. Concrete runners must live
behind ``SandboxRunner`` and satisfy these immutable request/result contracts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from .artifacts import ResourceUsage, TaskIdentity
from .content_store import validate_sha256

SANDBOX_SPEC_SCHEMA = "plural-cognition-protected-sandbox-spec-v1"
SANDBOX_REQUEST_SCHEMA = "plural-cognition-protected-sandbox-request-v1"
SANDBOX_RESULT_SCHEMA = "plural-cognition-protected-sandbox-result-v1"


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


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


class NetworkPolicy(str, Enum):
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    wall_time_ms: int
    cpu_time_ms: int
    memory_bytes: int
    writable_bytes: int
    process_count: int
    stdout_bytes: int
    stderr_bytes: int

    def __post_init__(self) -> None:
        for field in (
            "wall_time_ms",
            "cpu_time_ms",
            "memory_bytes",
            "writable_bytes",
            "process_count",
            "stdout_bytes",
            "stderr_bytes",
        ):
            _positive_int(getattr(self, field), field)

    def canonical_payload(self) -> dict[str, int]:
        return {
            "wall_time_ms": self.wall_time_ms,
            "cpu_time_ms": self.cpu_time_ms,
            "memory_bytes": self.memory_bytes,
            "writable_bytes": self.writable_bytes,
            "process_count": self.process_count,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
        }


@dataclass(frozen=True, slots=True)
class ProtectedSandboxSpec:
    """Exact privileged execution policy for one protected evaluator."""

    runner_id: str
    runner_configuration_sha256: str
    environment_image_sha256: str
    network_policy: NetworkPolicy
    command_argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    limits: SandboxLimits

    def __post_init__(self) -> None:
        _nonempty(self.runner_id, "runner_id")
        validate_sha256(self.runner_configuration_sha256)
        validate_sha256(self.environment_image_sha256)
        if self.network_policy is not NetworkPolicy.DISABLED:
            raise ValueError("protected evaluator network policy must be disabled")
        if not self.command_argv:
            raise ValueError("command_argv must not be empty")
        if any(type(item) is not str or not item for item in self.command_argv):
            raise ValueError("command_argv entries must be non-empty strings")
        if not isinstance(self.limits, SandboxLimits):
            raise TypeError("limits must be SandboxLimits")
        names: list[str] = []
        for item in self.environment:
            if type(item) is not tuple or len(item) != 2:
                raise TypeError("environment entries must be (name, value) tuples")
            name, value = item
            _nonempty(name, "environment name")
            if type(value) is not str:
                raise TypeError("environment values must be strings")
            if "=" in name or "\x00" in name or "\x00" in value:
                raise ValueError("environment entries contain invalid characters")
            names.append(name)
        if tuple(names) != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("environment variables must be sorted by unique name")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_SPEC_SCHEMA,
            "runner_id": self.runner_id,
            "runner_configuration_sha256": self.runner_configuration_sha256,
            "environment_image_sha256": self.environment_image_sha256,
            "network_policy": self.network_policy.value,
            "command_argv": list(self.command_argv),
            "environment": [[name, value] for name, value in self.environment],
            "limits": self.limits.canonical_payload(),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    """Privileged request to evaluate one immutable patch in a fresh workspace."""

    task: TaskIdentity
    submission_sha256: str
    buggy_repository_sha256: str
    patch_sha256: str
    hidden_tests_sha256: str
    sandbox_spec_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        for digest in (
            self.submission_sha256,
            self.buggy_repository_sha256,
            self.patch_sha256,
            self.hidden_tests_sha256,
            self.sandbox_spec_sha256,
        ):
            validate_sha256(digest)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_REQUEST_SCHEMA,
            "task": self.task.canonical_payload(),
            "submission_sha256": self.submission_sha256,
            "buggy_repository_sha256": self.buggy_repository_sha256,
            "patch_sha256": self.patch_sha256,
            "hidden_tests_sha256": self.hidden_tests_sha256,
            "sandbox_spec_sha256": self.sandbox_spec_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Immutable result returned by a concrete isolated runner."""

    request_sha256: str
    exit_code: int | None
    timed_out: bool
    memory_limit_exceeded: bool
    stdout_sha256: str
    stderr_sha256: str
    resources: ResourceUsage

    def __post_init__(self) -> None:
        validate_sha256(self.request_sha256)
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise TypeError("exit_code must be int or None")
        if type(self.timed_out) is not bool or type(self.memory_limit_exceeded) is not bool:
            raise TypeError("sandbox termination flags must be bool")
        if self.timed_out and self.exit_code is not None:
            raise ValueError("timed-out sandbox result must not report a normal exit code")
        validate_sha256(self.stdout_sha256)
        validate_sha256(self.stderr_sha256)
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")

    @property
    def completed_normally(self) -> bool:
        return (
            self.exit_code is not None
            and not self.timed_out
            and not self.memory_limit_exceeded
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_RESULT_SCHEMA,
            "request_sha256": self.request_sha256,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "memory_limit_exceeded": self.memory_limit_exceeded,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "resources": self.resources.canonical_payload(),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@runtime_checkable
class SandboxRunner(Protocol):
    """Execution boundary implemented later by an actual isolated runtime."""

    @property
    def spec(self) -> ProtectedSandboxSpec:
        ...

    def run(self, request: SandboxRequest) -> SandboxResult:
        ...
