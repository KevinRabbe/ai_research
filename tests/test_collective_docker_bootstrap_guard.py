from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import plural_cognition.collective.docker_bootstrap_guard as guard


def test_memory_events_parser_requires_nonnegative_oom_kill() -> None:
    assert guard._parse_memory_events("low 0\nhigh 2\nmax 3\noom 1\noom_kill 1\n") == {
        "low": 0,
        "high": 2,
        "max": 3,
        "oom": 1,
        "oom_kill": 1,
    }

    with pytest.raises(RuntimeError, match="lacks oom_kill"):
        guard._parse_memory_events("low 0\noom 1\n")
    with pytest.raises(RuntimeError, match="negative"):
        guard._parse_memory_events("oom_kill -1\n")
    with pytest.raises(RuntimeError, match="duplicate"):
        guard._parse_memory_events("oom_kill 0\noom_kill 1\n")


def test_guard_verifies_frozen_bootstrap_core_hash() -> None:
    source = Path(guard.__file__).with_name("docker_bootstrap.py")
    module = guard._load_verified_core(source)
    assert callable(module.run_bootstrap)
    assert callable(module._run_candidate)


def test_guard_rejects_core_hash_mismatch(tmp_path: Path) -> None:
    core = tmp_path / "bootstrap_core.py"
    core.write_bytes(b"print('wrong')\n")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        guard._load_verified_core(core)


def test_guard_records_oom_kill_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace()

    def original_run_candidate(*args, **kwargs):
        return object()

    module._run_candidate = original_run_candidate

    def run_bootstrap():
        module._run_candidate()
        return {"schema": "old", "status": "candidate-result"}

    module.run_bootstrap = run_bootstrap
    values = iter((4, 6))
    monkeypatch.setattr(guard, "_read_oom_kill", lambda: next(values))

    payload = guard._run_guarded(module)

    assert payload["schema"] == guard.BOOTSTRAP_RESULT_SCHEMA
    assert payload["oom_kill_events"] == 2
    assert payload["memory_limit_exceeded"] is True


def test_guard_fails_closed_on_nonmonotonic_oom_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace()
    module._run_candidate = lambda *args, **kwargs: object()

    def run_bootstrap():
        module._run_candidate()
        return {"schema": "old", "status": "candidate-result"}

    module.run_bootstrap = run_bootstrap
    values = iter((5, 4))
    monkeypatch.setattr(guard, "_read_oom_kill", lambda: next(values))

    with pytest.raises(RuntimeError, match="moved backwards"):
        guard._run_guarded(module)
