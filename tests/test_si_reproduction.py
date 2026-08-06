import pytest

from plural_cognition.self_improvement.reproduction import (
    ReproductionError,
    ReproductionRun,
    qualify_reproductions,
)


def _run(identity: str, gain: float = 0.10) -> ReproductionRun:
    return ReproductionRun(
        identity * 64,
        tuple(character * 64 for character in (identity, "a", "b", "c")),
        True,
        gain,
        gain / 2.0,
        gain / 2.0,
        (gain, gain, gain, gain),
    )


def test_three_independent_positive_runs_pass_strong_gate() -> None:
    result = qualify_reproductions(
        (_run("1"), _run("2"), _run("3")),
        bootstrap_resamples=200,
    )

    assert result.passed is True
    assert result.mean_hidden_gain == 0.10
    assert result.run_mean_gain_ci.lower == 0.10
    assert result.pooled_task_gain_ci.lower == 0.10
    assert result.minimum_shift_gain == 0.05
    assert result.reasons == ()
    assert len(result.sha256) == 64


def test_reproduction_gate_rejects_insufficient_or_failed_runs() -> None:
    failed = ReproductionRun(
        "4" * 64,
        ("4" * 64, "d" * 64, "e" * 64, "f" * 64),
        False,
        0.10,
        0.05,
        0.05,
        (0.10, 0.10),
    )
    result = qualify_reproductions(
        (_run("1"), failed),
        bootstrap_resamples=200,
    )

    assert result.passed is False
    assert any("independent runs" in reason for reason in result.reasons)
    assert any("failed" in reason for reason in result.reasons)


def test_reproduction_gate_rejects_reused_candidate_pools() -> None:
    first = _run("1")
    duplicate_pool = ReproductionRun(
        "2" * 64,
        first.split_pool_sha256s,
        True,
        0.10,
        0.05,
        0.05,
        (0.10, 0.10),
    )

    with pytest.raises(ReproductionError, match="independent split"):
        qualify_reproductions(
            (first, duplicate_pool, _run("3")),
            bootstrap_resamples=200,
        )
