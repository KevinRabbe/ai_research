"""Concrete DockerSandboxRunner for qualification and later protected execution.

The runner is intentionally conservative. It materializes only the existing
candidate-visible bundle, executes the locked Docker command plan as argv vectors,
requires a canonical trusted-bootstrap result envelope, records bounded candidate
stdout/stderr in the content store, and force-removes the container in ``finally``.

The presence of this implementation is not a containment qualification claim.
Target-machine adversarial qualification remains mandatory before protected
Repository Surgery execution is enabled.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .artifacts import ResourceUsage
from .content_store import ContentStore, validate_sha256
from .docker_bootstrap_guard import BOOTSTRAP_RESULT_SCHEMA
from .docker_candidate import (
    DockerRunnerConfiguration,
    build_docker_command_plan,
    prepare_docker_input_bundle,
)
from .sandbox import ProtectedSandboxSpec, SandboxRequest, SandboxResult


class DockerRunnerError(RuntimeError):
    """Raised for Docker/bootstrap infrastructure failures, not candidate failures."""


@dataclass(frozen=True, slots=True)
class DockerCommandResult:
    argv: tuple[str, ...]
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False

    def __post_init__(self) -> None:
        if type(self.argv) is not tuple or not self.argv:
            raise ValueError("argv must be a non-empty tuple")
        if self.returncode is not None and type(self.returncode) is not int:
            raise TypeError("returncode must be int or None")
        if type(self.stdout) is not bytes or type(self.stderr) is not bytes:
            raise TypeError("stdout/stderr must be bytes")
        if type(self.timed_out) is not bool:
            raise TypeError("timed_out must be bool")
        if self.timed_out and self.returncode is not None:
            raise ValueError("timed-out command must not report returncode")


DockerCommandExecutor = Callable[[tuple[str, ...], float], DockerCommandResult]


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _default_executor(argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
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


def _require_success(result: DockerCommandResult, operation: str) -> None:
    if result.timed_out:
        raise DockerRunnerError(f"docker {operation} timed out")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:2048]
        raise DockerRunnerError(
            f"docker {operation} failed with exit {result.returncode}: {detail}"
        )


def _parse_state(result: DockerCommandResult) -> dict[str, Any]:
    _require_success(result, "inspect")
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DockerRunnerError("docker inspect returned invalid JSON") from exc
    if type(payload) is not dict:
        raise DockerRunnerError("docker inspect state must be a JSON object")
    running = payload.get("Running")
    oom_killed = payload.get("OOMKilled")
    exit_code = payload.get("ExitCode")
    if type(running) is not bool or running:
        raise DockerRunnerError("docker inspect must report a stopped container")
    if type(oom_killed) is not bool:
        raise DockerRunnerError("docker inspect OOMKilled must be bool")
    if type(exit_code) is not int:
        raise DockerRunnerError("docker inspect ExitCode must be int")
    return payload


def _parse_bootstrap_envelope(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise DockerRunnerError("bootstrap output must be exactly one JSON line")
    body = raw[:-1]
    try:
        payload = json.loads(body.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DockerRunnerError("bootstrap output is not canonical ASCII JSON") from exc
    if type(payload) is not dict:
        raise DockerRunnerError("bootstrap envelope must be a JSON object")
    if _canonical_json_bytes(payload) != body:
        raise DockerRunnerError("bootstrap envelope is not canonical")
    if payload.get("schema") != BOOTSTRAP_RESULT_SCHEMA:
        raise DockerRunnerError("bootstrap envelope has wrong schema")
    return payload


def _bool(payload: dict[str, Any], name: str) -> bool:
    value = payload.get(name)
    if type(value) is not bool:
        raise DockerRunnerError(f"bootstrap field {name} must be bool")
    return value


def _nonnegative_int(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if type(value) is not int or value < 0:
        raise DockerRunnerError(f"bootstrap field {name} must be a non-negative integer")
    return value


def _optional_exit_code(payload: dict[str, Any]) -> int | None:
    value = payload.get("exit_code")
    if value is not None and type(value) is not int:
        raise DockerRunnerError("bootstrap exit_code must be int or null")
    return value


def _normalize_candidate_exit_code(
    *,
    exit_code: int | None,
    timed_out: bool,
    stdout_limit_exceeded: bool,
    stderr_limit_exceeded: bool,
) -> int | None:
    output_limit_exceeded = stdout_limit_exceeded or stderr_limit_exceeded
    if timed_out:
        if exit_code is not None:
            raise DockerRunnerError("timed-out candidate reported an exit code")
        return None
    if exit_code is None and not output_limit_exceeded:
        raise DockerRunnerError("non-timeout candidate omitted exit code")
    if output_limit_exceeded:
        return None
    return exit_code


def _bounded_base64(payload: dict[str, Any], name: str, limit: int) -> bytes:
    value = payload.get(name)
    if type(value) is not str:
        raise DockerRunnerError(f"bootstrap field {name} must be base64 text")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise DockerRunnerError(f"bootstrap field {name} is invalid base64") from exc
    if len(decoded) > limit:
        raise DockerRunnerError(f"bootstrap field {name} exceeds declared output limit")
    return decoded


@dataclass(slots=True)
class DockerSandboxRunner:
    """Concrete, not-yet-qualified implementation of ``SandboxRunner``."""

    spec: ProtectedSandboxSpec
    configuration: DockerRunnerConfiguration
    store: ContentStore
    staging_root: Path
    docker_executable: str = "docker"
    outer_timeout_grace_ms: int = 5_000
    command_executor: DockerCommandExecutor = _default_executor

    def __post_init__(self) -> None:
        if not isinstance(self.spec, ProtectedSandboxSpec):
            raise TypeError("spec must be ProtectedSandboxSpec")
        if not isinstance(self.configuration, DockerRunnerConfiguration):
            raise TypeError("configuration must be DockerRunnerConfiguration")
        if self.spec.runner_id != self.configuration.runner_id:
            raise ValueError("sandbox spec runner_id does not match Docker configuration")
        if self.spec.runner_configuration_sha256 != self.configuration.sha256:
            raise ValueError("sandbox spec does not bind Docker runner configuration")
        if self.spec.environment_image_sha256 != self.configuration.environment_image_sha256:
            raise ValueError("sandbox spec does not bind Docker image identity")
        self.staging_root = Path(self.staging_root)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        if self.staging_root.is_symlink() or not self.staging_root.is_dir():
            raise ValueError("staging_root must be a real directory")
        if type(self.docker_executable) is not str or not self.docker_executable:
            raise ValueError("docker_executable must be non-empty")
        if type(self.outer_timeout_grace_ms) is not int or self.outer_timeout_grace_ms < 1:
            raise ValueError("outer_timeout_grace_ms must be positive")
        if not callable(self.command_executor):
            raise TypeError("command_executor must be callable")

    def _exec(self, argv: tuple[str, ...], timeout_seconds: float) -> DockerCommandResult:
        result = self.command_executor(argv, timeout_seconds)
        if not isinstance(result, DockerCommandResult):
            raise TypeError("command_executor must return DockerCommandResult")
        if result.argv != argv:
            raise DockerRunnerError("command executor returned result for different argv")
        return result

    def run(self, request: SandboxRequest) -> SandboxResult:
        if not isinstance(request, SandboxRequest):
            raise TypeError("request must be SandboxRequest")
        if request.sandbox_spec_sha256 != self.spec.sha256:
            raise ValueError("request does not bind this runner sandbox specification")

        staging = Path(tempfile.mkdtemp(prefix="pc-docker-", dir=self.staging_root)).resolve()
        bundle_root = staging / "bundle"
        container_name = f"pc-{request.sha256[:20]}-{uuid4().hex[:12]}"
        plan = None
        created = False

        try:
            prepare_docker_input_bundle(
                request=request,
                spec=self.spec,
                store=self.store,
                destination=bundle_root,
            )
            plan = build_docker_command_plan(
                spec=self.spec,
                configuration=self.configuration,
                input_bundle_directory=bundle_root,
                container_name=container_name,
                docker_executable=self.docker_executable,
            )

            create = self._exec(plan.create_argv, 30.0)
            _require_success(create, "create")
            created = True

            outer_timeout = (
                self.spec.limits.wall_time_ms + self.outer_timeout_grace_ms
            ) / 1000.0
            start = self._exec(plan.start_argv, outer_timeout)
            if start.timed_out:
                raise DockerRunnerError(
                    "docker start exceeded outer wall-time boundary; container will be removed"
                )

            inspect = self._exec(plan.inspect_argv, 15.0)
            state = _parse_state(inspect)
            envelope = _parse_bootstrap_envelope(start.stdout)

            status = envelope.get("status")
            if status == "bootstrap-error":
                message = envelope.get("error")
                if type(message) is not str:
                    message = "malformed bootstrap-error envelope"
                raise DockerRunnerError(f"protected bootstrap failed: {message[:2048]}")
            if status != "candidate-result":
                raise DockerRunnerError("bootstrap envelope has unknown status")

            if start.returncode != 0:
                raise DockerRunnerError(
                    f"bootstrap candidate-result exited with Docker status {start.returncode}"
                )
            if start.stderr:
                raise DockerRunnerError("docker start produced unexpected stderr")
            if state["ExitCode"] != 0:
                raise DockerRunnerError("container state disagrees with successful bootstrap exit")

            if envelope.get("request_sha256") != request.sha256:
                raise DockerRunnerError("bootstrap result binds a different request")
            patched_repository_sha256 = envelope.get("patched_repository_sha256")
            try:
                validate_sha256(patched_repository_sha256)
            except (TypeError, ValueError) as exc:
                raise DockerRunnerError("bootstrap result has invalid patched repository digest") from exc

            timed_out = _bool(envelope, "timed_out")
            stdout_limit_exceeded = _bool(envelope, "stdout_limit_exceeded")
            stderr_limit_exceeded = _bool(envelope, "stderr_limit_exceeded")
            memory_limit_exceeded = _bool(envelope, "memory_limit_exceeded")
            oom_kill_events = _nonnegative_int(envelope, "oom_kill_events")
            if memory_limit_exceeded != (oom_kill_events > 0):
                raise DockerRunnerError("bootstrap OOM fields are inconsistent")
            exit_code = _normalize_candidate_exit_code(
                exit_code=_optional_exit_code(envelope),
                timed_out=timed_out,
                stdout_limit_exceeded=stdout_limit_exceeded,
                stderr_limit_exceeded=stderr_limit_exceeded,
            )

            stdout = _bounded_base64(
                envelope,
                "stdout_base64",
                self.spec.limits.stdout_bytes,
            )
            stderr = _bounded_base64(
                envelope,
                "stderr_base64",
                self.spec.limits.stderr_bytes,
            )
            wall_time_ms = _nonnegative_int(envelope, "wall_time_ms")
            cpu_time_ms = _nonnegative_int(envelope, "cpu_time_ms")
            peak_memory_bytes = _nonnegative_int(envelope, "peak_memory_bytes")

            stdout_sha256 = self.store.put_bytes(stdout)
            stderr_sha256 = self.store.put_bytes(stderr)
            resources = ResourceUsage(
                wall_time_ms=wall_time_ms,
                cpu_time_ms=cpu_time_ms,
                peak_ram_bytes=peak_memory_bytes,
            )
            return SandboxResult(
                request_sha256=request.sha256,
                exit_code=exit_code,
                timed_out=timed_out,
                memory_limit_exceeded=(memory_limit_exceeded or state["OOMKilled"]),
                stdout_sha256=stdout_sha256,
                stderr_sha256=stderr_sha256,
                resources=resources,
            )
        finally:
            cleanup_failures: list[str] = []
            if created and plan is not None:
                try:
                    remove = self._exec(plan.remove_argv, 15.0)
                    _require_success(remove, "rm --force")
                except BaseException as exc:
                    cleanup_failures.append(f"container cleanup failed: {type(exc).__name__}: {exc}")
            try:
                shutil.rmtree(staging)
            except BaseException as exc:
                cleanup_failures.append(f"staging cleanup failed: {type(exc).__name__}: {exc}")
            if cleanup_failures:
                raise DockerRunnerError("; ".join(cleanup_failures))
