"""Trusted entry wrapper for the protected Docker bootstrap.

The large Repository Surgery bootstrap core remains content-frozen.  This small
entry layer verifies that exact core SHA-256 before loading it, measures the
cgroup-v2 ``memory.events`` ``oom_kill`` counter immediately around candidate
execution, and upgrades the candidate-result envelope to v2 with explicit OOM
evidence.

This module is copied into the qualification image as ``bootstrap.py``.  The
verified core is copied beside it as ``bootstrap_core.py``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

BOOTSTRAP_RESULT_SCHEMA = "plural-cognition-docker-bootstrap-result-v2"
CORE_BOOTSTRAP_SHA256 = "7e24fd1cbe8294e0a1be90f33b18e2b6aa3f5d79fbb907aed7949d8253c10b86"

_CORE_PATH = Path("/opt/plural-cognition/bootstrap_core.py")
_MEMORY_EVENTS_PATH = Path("/sys/fs/cgroup/memory.events")
_EXPECTED_REQUEST = Path("/pc-input/request.json")
_EXPECTED_SANDBOX_SPEC = Path("/pc-input/sandbox-spec.json")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _error_envelope(message: str) -> dict[str, Any]:
    return {
        "schema": BOOTSTRAP_RESULT_SCHEMA,
        "status": "bootstrap-error",
        "error": message[:2048],
    }


def _parse_memory_events(raw: str) -> dict[str, int]:
    events: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            raise RuntimeError("cgroup v2 memory.events contains malformed data")
        key, value_text = parts
        if not key or key in events:
            raise RuntimeError("cgroup v2 memory.events contains duplicate/empty keys")
        try:
            value = int(value_text)
        except ValueError as exc:
            raise RuntimeError("cgroup v2 memory.events contains a non-integer value") from exc
        if value < 0:
            raise RuntimeError("cgroup v2 memory.events contains a negative counter")
        events[key] = value
    if "oom_kill" not in events:
        raise RuntimeError("cgroup v2 memory.events lacks oom_kill")
    return events


def _read_oom_kill(path: Path = _MEMORY_EVENTS_PATH) -> int:
    try:
        raw = path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("cannot read cgroup v2 memory.events") from exc
    return _parse_memory_events(raw)["oom_kill"]


def _load_verified_core(path: Path = _CORE_PATH) -> ModuleType:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeError("protected bootstrap core is unavailable") from exc
    actual = sha256(raw).hexdigest()
    if actual != CORE_BOOTSTRAP_SHA256:
        raise RuntimeError("protected bootstrap core SHA-256 mismatch")

    module_name = "_plural_cognition_protected_bootstrap_core"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load protected bootstrap core")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _run_guarded(core: ModuleType) -> dict[str, Any]:
    original_run_candidate = getattr(core, "_run_candidate", None)
    run_bootstrap = getattr(core, "run_bootstrap", None)
    if not callable(original_run_candidate) or not callable(run_bootstrap):
        raise RuntimeError("protected bootstrap core lacks required entry points")

    evidence: dict[str, int | None] = {"oom_kill_events": None}

    def guarded_run_candidate(*args: Any, **kwargs: Any) -> Any:
        before = _read_oom_kill()
        result = original_run_candidate(*args, **kwargs)
        after = _read_oom_kill()
        if after < before:
            raise RuntimeError("cgroup v2 oom_kill counter moved backwards")
        evidence["oom_kill_events"] = after - before
        return result

    core._run_candidate = guarded_run_candidate
    payload = run_bootstrap()
    if type(payload) is not dict or payload.get("status") != "candidate-result":
        raise RuntimeError("protected bootstrap core returned an invalid result envelope")
    delta = evidence["oom_kill_events"]
    if type(delta) is not int or delta < 0:
        raise RuntimeError("protected bootstrap did not produce OOM evidence")
    payload = dict(payload)
    payload["schema"] = BOOTSTRAP_RESULT_SCHEMA
    payload["oom_kill_events"] = delta
    payload["memory_limit_exceeded"] = delta > 0
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OOM-aware protected Docker bootstrap")
    parser.add_argument("--request", default=str(_EXPECTED_REQUEST))
    parser.add_argument("--sandbox-spec", default=str(_EXPECTED_SANDBOX_SPEC))
    args = parser.parse_args(argv)

    try:
        if Path(args.request) != _EXPECTED_REQUEST:
            raise ValueError("unexpected request path")
        if Path(args.sandbox_spec) != _EXPECTED_SANDBOX_SPEC:
            raise ValueError("unexpected sandbox-spec path")
        core = _load_verified_core()
        envelope = _run_guarded(core)
        return_code = 0
    except BaseException as exc:  # fail closed without traceback or host details
        envelope = _error_envelope(f"{type(exc).__name__}: {exc}")
        return_code = 125

    sys.stdout.buffer.write(_canonical_json_bytes(envelope) + b"\n")
    sys.stdout.buffer.flush()
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
