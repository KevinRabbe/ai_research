import pytest

from plural_cognition.screening_selection import (
    MODEL_ORDER,
    V1_2_MODEL_ORDER,
    ScreeningRunResult,
    select_screening_scale,
)


def _result(model: str, seed: int, exact: float, parse: float = 1.0):
    return ScreeningRunResult(
        model,
        seed,
        ("a" if seed == 101 else "b") * 64,
        ("c" if seed == 101 else "d") * 64,
        ("e" * 64,),
        parse,
        exact,
        exact,
        exact,
    )


def _matrix(values, model_order=MODEL_ORDER):
    return tuple(
        _result(model, seed, values[model][index])
        for model in model_order
        for index, seed in enumerate((101, 102))
    )


def test_selects_smallest_model_inside_capability_band() -> None:
    decision = select_screening_scale(
        _matrix(
            {
                "PC-4M": (0.25, 0.35),
                "PC-10M": (0.50, 0.55),
                "PC-18M": (0.65, 0.68),
            }
        )
    )

    assert decision.selected_model == "PC-4M"
    assert decision.status == "selected"
    assert decision.summaries[0].qualifies is True


def test_selects_next_scale_when_smaller_model_is_too_weak() -> None:
    decision = select_screening_scale(
        _matrix(
            {
                "PC-4M": (0.10, 0.15),
                "PC-10M": (0.30, 0.40),
                "PC-18M": (0.55, 0.60),
            }
        )
    )

    assert decision.selected_model == "PC-10M"
    assert decision.summaries[0].qualifies is False
    assert decision.summaries[1].qualifies is True


def test_v12_selects_smallest_recovery_scale_in_band() -> None:
    values = {
        "PC-29M": (0.15, 0.18),
        "PC-44M": (0.26, 0.31),
        "PC-64M": (0.42, 0.48),
    }
    decision = select_screening_scale(
        _matrix(values, V1_2_MODEL_ORDER),
        model_order=V1_2_MODEL_ORDER,
    )

    assert decision.selected_model == "PC-44M"
    assert decision.status == "selected"
    assert decision.summaries[0].qualifies is False
    assert decision.summaries[1].qualifies is True


def test_rejects_low_parse_rate_even_when_accuracy_is_in_band() -> None:
    values = list(
        _matrix(
            {
                "PC-4M": (0.30, 0.35),
                "PC-10M": (0.40, 0.45),
                "PC-18M": (0.50, 0.55),
            }
        )
    )
    values[0] = _result("PC-4M", 101, 0.30, parse=0.90)

    decision = select_screening_scale(tuple(values))

    assert decision.selected_model == "PC-10M"
    assert any("parse rate" in reason for reason in decision.summaries[0].reasons)


def test_reports_all_too_weak_without_post_hoc_selection() -> None:
    decision = select_screening_scale(
        _matrix(
            {
                "PC-4M": (0.05, 0.10),
                "PC-10M": (0.10, 0.15),
                "PC-18M": (0.15, 0.19),
            }
        )
    )

    assert decision.selected is False
    assert decision.status == "all-too-weak"


def test_requires_exact_six_run_matrix_and_shared_validation_set() -> None:
    results = list(
        _matrix(
            {
                "PC-4M": (0.25, 0.30),
                "PC-10M": (0.40, 0.45),
                "PC-18M": (0.55, 0.60),
            }
        )
    )
    with pytest.raises(ValueError, match="requires 6 runs"):
        select_screening_scale(tuple(results[:-1]))

    changed = results[-1]
    results[-1] = ScreeningRunResult(
        changed.model_name,
        changed.initialization_seed,
        changed.execution_sha256,
        changed.checkpoint_sha256,
        ("9" * 64,),
        changed.parse_rate,
        changed.exact_accuracy,
        changed.visible_consistency_rate,
        changed.mean_semantic_accuracy,
    )
    with pytest.raises(ValueError, match="different validation shards"):
        select_screening_scale(tuple(results))
