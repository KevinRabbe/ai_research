"""Standalone Linux bootstrap for the protected Docker runner.

This module is copied verbatim into the qualification image.  It intentionally
uses only the Python standard library so the runtime image can remain small and
content-addressable.  Candidate code receives the protected *input* through
stdin and a fixed workspace file, but never receives protected expectations or
privileged grader state.

The bootstrap is not itself a security boundary.  Docker containment and every
resource control remain subject to target-machine adversarial qualification.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

BOOTSTRAP_RESULT_SCHEMA = "plural-cognition-docker-bootstrap-result-v1"
REPOSITORY_SNAPSHOT_SCHEMA = "plural-cognition-repository-snapshot-v1"
SANDBOX_REQUEST_SCHEMA = "plural-cognition-protected-sandbox-request-v1"
SANDBOX_SPEC_SCHEMA = "plural-cognition-protected-sandbox-spec-v1"
BUNDLE_SCHEMA = "plural-cognition-docker-input-bundle-v1"

_INPUT_ROOT = Path("/pc-input")
_WORK_ROOT = Path("/pc-work")
_REPOSITORY_NAME = "repository"
_RUNTIME_INPUT_NAME = "runtime-input.bin"

_HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _validate_digest(value: Any, field: str) -> str:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError(f"{field} must use lowercase hexadecimal")
    return value


def _positive_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _load_canonical_json(path: Path, expected_schema: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name} is not canonical ASCII JSON") from exc
    if type(payload) is not dict or payload.get("schema") != expected_schema:
        raise ValueError(f"{path.name} has the wrong schema")
    if _canonical_json_bytes(payload) != raw:
        raise ValueError(f"{path.name} is not canonical JSON")
    return payload, raw


def _safe_relative_path(value: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise ValueError("patch path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError("patch path must be normalized and relative")
    if any(part in ("", ".", "..") or ":" in part for part in path.parts):
        raise ValueError("patch path contains unsafe components")
    return path


def _path_from_header(value: str, prefix: str) -> str | None:
    if not value.startswith(prefix):
        raise ValueError("invalid unified-diff file header")
    raw = value[len(prefix) :]
    if "\t" in raw:
        raw = raw.split("\t", 1)[0]
    if raw == "/dev/null":
        return None
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    return _safe_relative_path(raw).as_posix()


@dataclass(frozen=True, slots=True)
class _Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FilePatch:
    old_path: str | None
    new_path: str | None
    hunks: tuple[_Hunk, ...]


def _parse_unified_diff(raw: bytes) -> tuple[_FilePatch, ...]:
    if b"\x00" in raw or b"\r" in raw:
        raise ValueError("Repository Surgery v0 patches must be UTF-8 LF text")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("patch must be UTF-8") from exc
    if not text:
        return ()
    if not text.endswith("\n"):
        raise ValueError("patch must end with LF")
    lines = text[:-1].split("\n")
    patches: list[_FilePatch] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git ") or line.startswith("index "):
            i += 1
            continue
        if line.startswith(("new file mode ", "deleted file mode ", "old mode ", "new mode ")):
            i += 1
            continue
        if not line.startswith("--- "):
            raise ValueError(f"unsupported unified-diff metadata: {line!r}")
        old_path = _path_from_header(line, "--- ")
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise ValueError("unified diff is missing +++ header")
        new_path = _path_from_header(lines[i], "+++ ")
        i += 1
        if old_path is None and new_path is None:
            raise ValueError("patch cannot map /dev/null to /dev/null")
        if old_path is not None and new_path is not None and old_path != new_path:
            raise ValueError("Repository Surgery v0 does not permit rename patches")

        hunks: list[_Hunk] = []
        while i < len(lines) and lines[i].startswith("@@ "):
            match = _HUNK_RE.match(lines[i])
            if match is None:
                raise ValueError(f"invalid unified-diff hunk header: {lines[i]!r}")
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            i += 1
            body: list[str] = []
            seen_old = 0
            seen_new = 0
            while i < len(lines):
                candidate = lines[i]
                if candidate.startswith("@@ ") or candidate.startswith("--- ") or candidate.startswith("diff --git "):
                    break
                if candidate == "\\ No newline at end of file":
                    raise ValueError("Repository Surgery v0 requires trailing LF text files")
                if not candidate or candidate[0] not in (" ", "+", "-"):
                    raise ValueError(f"invalid unified-diff hunk line: {candidate!r}")
                marker = candidate[0]
                if marker in (" ", "-"):
                    seen_old += 1
                if marker in (" ", "+"):
                    seen_new += 1
                body.append(candidate)
                i += 1
            if seen_old != old_count or seen_new != new_count:
                raise ValueError("unified-diff hunk counts do not match its body")
            hunks.append(_Hunk(old_start, old_count, new_start, new_count, tuple(body)))
        if not hunks:
            raise ValueError("file patch must contain at least one hunk")
        patches.append(_FilePatch(old_path, new_path, tuple(hunks)))

    touched = [patch.new_path or patch.old_path for patch in patches]
    if len(touched) != len(set(touched)):
        raise ValueError("a patch may modify each repository path at most once")
    return tuple(patches)


def _text_lines(path: Path) -> list[str]:
    if not path.exists():
        raise ValueError(f"patch source does not exist: {path.name}")
    if path.is_symlink() or not path.is_file():
        raise ValueError("patch source must be a regular file")
    raw = path.read_bytes()
    if b"\x00" in raw or b"\r" in raw:
        raise ValueError("patchable repository files must be UTF-8 LF text")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("patchable repository files must be UTF-8") from exc
    if text and not text.endswith("\n"):
        raise ValueError("patchable repository files must end with LF")
    return [] if not text else text[:-1].split("\n")


def _apply_hunks(original: list[str], hunks: tuple[_Hunk, ...]) -> list[str]:
    result: list[str] = []
    cursor = 0
    expected_new_cursor = 0
    for hunk in hunks:
        target = hunk.old_start if hunk.old_count == 0 else hunk.old_start - 1
        new_target = hunk.new_start if hunk.new_count == 0 else hunk.new_start - 1
        if target < cursor or target > len(original):
            raise ValueError("unified-diff hunk starts outside source file")
        if new_target != expected_new_cursor + (target - cursor):
            raise ValueError("unified-diff old/new hunk coordinates are inconsistent")
        result.extend(original[cursor:target])
        cursor = target
        consumed = 0
        produced = 0
        for line in hunk.lines:
            marker, content = line[0], line[1:]
            if marker in (" ", "-"):
                if cursor >= len(original) or original[cursor] != content:
                    raise ValueError("unified-diff context does not match repository content")
                cursor += 1
                consumed += 1
            if marker in (" ", "+"):
                result.append(content)
                produced += 1
        if consumed != hunk.old_count or produced != hunk.new_count:
            raise AssertionError("validated hunk counts changed during application")
        expected_new_cursor = len(result)
    result.extend(original[cursor:])
    return result


def _resolved_child(root: Path, relative: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative).parts)
    root_resolved = root.resolve()
    parent = path.parent.resolve()
    if parent != root_resolved and root_resolved not in parent.parents:
        raise ValueError("patch path escapes repository workspace")
    return path


def apply_unified_diff(repository_root: Path, patch_bytes: bytes) -> None:
    """Apply the strict Repository Surgery v0 unified-diff subset in place."""

    root = repository_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("repository_root must be a real directory")
    for patch in _parse_unified_diff(patch_bytes):
        old_path = patch.old_path
        new_path = patch.new_path
        source_lines: list[str]
        if old_path is None:
            assert new_path is not None
            destination = _resolved_child(root, new_path)
            if destination.exists():
                raise ValueError("new-file patch destination already exists")
            source_lines = []
        else:
            source = _resolved_child(root, old_path)
            source_lines = _text_lines(source)
            destination = source if new_path is not None else source

        updated = _apply_hunks(source_lines, patch.hunks)
        if new_path is None:
            if updated:
                raise ValueError("deleted-file patch must remove all source lines")
            destination.unlink()
            continue

        destination = _resolved_child(root, new_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        for ancestor in (destination.parent, *destination.parent.parents):
            if ancestor == root.parent:
                break
            if ancestor.exists() and ancestor.is_symlink():
                raise ValueError("patch destination traverses a symlink")
            if ancestor == root:
                break
        encoded = b"" if not updated else ("\n".join(updated) + "\n").encode("utf-8")
        destination.write_bytes(encoded)


def _snapshot_repository(root: Path) -> tuple[str, dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError("repository snapshot rejects symlinks")
        if path.is_dir():
            continue
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError("repository snapshot requires regular files")
        relative = path.relative_to(root).as_posix()
        _safe_relative_path(relative)
        raw = path.read_bytes()
        files.append(
            {
                "path": relative,
                "content_sha256": _sha256(raw),
                "size_bytes": len(raw),
            }
        )
    payload = {"schema": REPOSITORY_SNAPSHOT_SCHEMA, "files": files}
    return _sha256(_canonical_json_bytes(payload)), payload


def _copy_repository(source: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("workspace repository destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError("input repository contains a symlink")
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            raise ValueError("input repository contains a non-regular file")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _verify_bundle(input_root: Path) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    manifest, _ = _load_canonical_json(input_root / "bundle-manifest.json", BUNDLE_SCHEMA)
    request, request_raw = _load_canonical_json(input_root / "request.json", SANDBOX_REQUEST_SCHEMA)
    spec, spec_raw = _load_canonical_json(input_root / "sandbox-spec.json", SANDBOX_SPEC_SCHEMA)

    if _sha256(request_raw) != _validate_digest(manifest.get("request_sha256"), "request_sha256"):
        raise ValueError("bundle request identity mismatch")
    if _sha256(spec_raw) != _validate_digest(manifest.get("sandbox_spec_sha256"), "sandbox_spec_sha256"):
        raise ValueError("bundle sandbox-spec identity mismatch")
    if request.get("sandbox_spec_sha256") != _sha256(spec_raw):
        raise ValueError("request does not bind the supplied sandbox spec")

    patch = (input_root / "candidate.patch").read_bytes()
    runtime_input = (input_root / "runtime-input.bin").read_bytes()
    submission = (input_root / "submission.json").read_bytes()
    checks = (
        ("patch_sha256", patch),
        ("runtime_input_sha256", runtime_input),
        ("submission_sha256", submission),
    )
    for field, raw in checks:
        digest = _validate_digest(request.get(field), field)
        if digest != _sha256(raw) or manifest.get(field) != digest:
            raise ValueError(f"bundle {field} mismatch")

    repository_sha, _ = _snapshot_repository(input_root / _REPOSITORY_NAME)
    expected_repository = _validate_digest(
        request.get("buggy_repository_sha256"), "buggy_repository_sha256"
    )
    if repository_sha != expected_repository or manifest.get("buggy_repository_sha256") != expected_repository:
        raise ValueError("bundle repository identity mismatch")
    return request, spec, patch, runtime_input


def _read_cpu_usage_usec() -> int:
    path = Path("/sys/fs/cgroup/cpu.stat")
    data = path.read_text(encoding="ascii")
    for line in data.splitlines():
        key, value = line.split(maxsplit=1)
        if key == "usage_usec":
            return int(value)
    raise RuntimeError("cgroup v2 cpu.stat lacks usage_usec")


def _read_memory_peak() -> int:
    raw = Path("/sys/fs/cgroup/memory.peak").read_text(encoding="ascii").strip()
    if raw == "max":
        raise RuntimeError("cgroup v2 memory.peak is unbounded")
    return int(raw)


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@dataclass(frozen=True, slots=True)
class _Execution:
    exit_code: int | None
    timed_out: bool
    stdout_limit_exceeded: bool
    stderr_limit_exceeded: bool
    stdout: bytes
    stderr: bytes
    wall_time_ms: int
    cpu_time_ms: int
    peak_memory_bytes: int


def _run_candidate(
    *,
    argv: Sequence[str],
    cwd: Path,
    runtime_input_path: Path,
    wall_time_ms: int,
    stdout_limit: int,
    stderr_limit: int,
) -> _Execution:
    if not argv or any(type(item) is not str or not item or "\x00" in item for item in argv):
        raise ValueError("sandbox command_argv is invalid")
    cpu_before = _read_cpu_usage_usec()
    started = time.monotonic_ns()
    with runtime_input_path.open("rb") as stdin_handle:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            stdin=stdin_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
        assert process.stdout is not None and process.stderr is not None
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        captured = {"stdout": bytearray(), "stderr": bytearray()}
        exceeded = {"stdout": False, "stderr": False}
        deadline = time.monotonic() + wall_time_ms / 1000.0
        timed_out = False

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                timed_out = True
                _terminate_group(process)
                remaining = 0
            events = selector.select(timeout=max(0.0, min(0.05, remaining)))
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    continue
                name = key.data
                limit = stdout_limit if name == "stdout" else stderr_limit
                buffer = captured[name]
                space = max(0, limit - len(buffer))
                buffer.extend(chunk[:space])
                if len(chunk) > space:
                    exceeded[name] = True
                    _terminate_group(process)
            if process.poll() is not None and not events:
                for key in list(selector.get_map().values()):
                    stream = key.fileobj
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        continue
                    name = key.data
                    limit = stdout_limit if name == "stdout" else stderr_limit
                    buffer = captured[name]
                    space = max(0, limit - len(buffer))
                    buffer.extend(chunk[:space])
                    if len(chunk) > space:
                        exceeded[name] = True
        selector.close()
        try:
            return_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _terminate_group(process)
            return_code = process.wait(timeout=2)

    ended = time.monotonic_ns()
    cpu_after = _read_cpu_usage_usec()
    return _Execution(
        exit_code=None if timed_out else return_code,
        timed_out=timed_out,
        stdout_limit_exceeded=exceeded["stdout"],
        stderr_limit_exceeded=exceeded["stderr"],
        stdout=bytes(captured["stdout"]),
        stderr=bytes(captured["stderr"]),
        wall_time_ms=max(0, (ended - started + 999_999) // 1_000_000),
        cpu_time_ms=max(0, (cpu_after - cpu_before + 999) // 1000),
        peak_memory_bytes=_read_memory_peak(),
    )


def _success_envelope(
    *,
    request_sha256: str,
    patched_repository_sha256: str,
    execution: _Execution,
) -> dict[str, Any]:
    return {
        "schema": BOOTSTRAP_RESULT_SCHEMA,
        "status": "candidate-result",
        "request_sha256": request_sha256,
        "patched_repository_sha256": patched_repository_sha256,
        "exit_code": execution.exit_code,
        "timed_out": execution.timed_out,
        "stdout_limit_exceeded": execution.stdout_limit_exceeded,
        "stderr_limit_exceeded": execution.stderr_limit_exceeded,
        "stdout_base64": base64.b64encode(execution.stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(execution.stderr).decode("ascii"),
        "wall_time_ms": execution.wall_time_ms,
        "cpu_time_ms": execution.cpu_time_ms,
        "peak_memory_bytes": execution.peak_memory_bytes,
    }


def _error_envelope(message: str) -> dict[str, Any]:
    return {
        "schema": BOOTSTRAP_RESULT_SCHEMA,
        "status": "bootstrap-error",
        "error": message[:2048],
    }


def run_bootstrap(*, input_root: Path = _INPUT_ROOT, work_root: Path = _WORK_ROOT) -> dict[str, Any]:
    request, spec, patch, runtime_input = _verify_bundle(input_root)
    limits = spec.get("limits")
    if type(limits) is not dict:
        raise ValueError("sandbox spec lacks limits")
    wall_time_ms = _positive_int(limits.get("wall_time_ms"), "wall_time_ms")
    stdout_limit = _positive_int(limits.get("stdout_bytes"), "stdout_bytes")
    stderr_limit = _positive_int(limits.get("stderr_bytes"), "stderr_bytes")
    command = spec.get("command_argv")
    if type(command) is not list:
        raise ValueError("sandbox spec command_argv must be a list")

    repository = work_root / _REPOSITORY_NAME
    runtime_path = work_root / _RUNTIME_INPUT_NAME
    if repository.exists():
        raise ValueError("workspace repository already exists")
    _copy_repository(input_root / _REPOSITORY_NAME, repository)
    runtime_path.write_bytes(runtime_input)
    apply_unified_diff(repository, patch)
    patched_sha, _ = _snapshot_repository(repository)
    execution = _run_candidate(
        argv=command,
        cwd=repository,
        runtime_input_path=runtime_path,
        wall_time_ms=wall_time_ms,
        stdout_limit=stdout_limit,
        stderr_limit=stderr_limit,
    )
    request_raw = (input_root / "request.json").read_bytes()
    return _success_envelope(
        request_sha256=_sha256(request_raw),
        patched_repository_sha256=patched_sha,
        execution=execution,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Protected Docker candidate bootstrap")
    parser.add_argument("--request", default=str(_INPUT_ROOT / "request.json"))
    parser.add_argument("--sandbox-spec", default=str(_INPUT_ROOT / "sandbox-spec.json"))
    args = parser.parse_args(argv)
    if Path(args.request) != _INPUT_ROOT / "request.json":
        print(_canonical_json_bytes(_error_envelope("unexpected request path")).decode("ascii"))
        return 125
    if Path(args.sandbox_spec) != _INPUT_ROOT / "sandbox-spec.json":
        print(_canonical_json_bytes(_error_envelope("unexpected sandbox-spec path")).decode("ascii"))
        return 125
    try:
        envelope = run_bootstrap()
    except BaseException as exc:  # fail closed without a traceback or host details
        envelope = _error_envelope(f"{type(exc).__name__}: {exc}")
        sys.stdout.buffer.write(_canonical_json_bytes(envelope) + b"\n")
        sys.stdout.buffer.flush()
        return 125
    sys.stdout.buffer.write(_canonical_json_bytes(envelope) + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
