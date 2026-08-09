import pytest

from plural_cognition.experiment import RunIntent, resolve_run_intent
from plural_cognition.population_plan import build_initial_population_plan


def _run(model: str, seed: int, microbatch: int = 64, experiment: str = "v1.1-screen"):
    return resolve_run_intent(
        RunIntent(experiment, model, seed, 20260806),
        git_commit="a" * 40,
        precision="bf16",
        microbatch_examples=microbatch,
        device_name="RTX 4060 Ti",
        preflight_sha256="b" * 64,
    )


def test_population_plan_reuses_two_runs_and_adds_two_seeds() -> None:
    screening = tuple(
        _run(model, seed)
        for model in ("PC-4M", "PC-10M", "PC-18M")
        for seed in (101, 102)
    )

    population = build_initial_population_plan("PC-10M", screening)

    assert len(population) == 4
    assert tuple(run.intent.initialization_seed for run in population) == (
        101,
        102,
        103,
        104,
    )
    assert all(run.intent.model_name == "PC-10M" for run in population)
    assert population[0] == next(
        run
        for run in screening
        if run.intent.model_name == "PC-10M"
        and run.intent.initialization_seed == 101
    )
    assert population[1] == next(
        run
        for run in screening
        if run.intent.model_name == "PC-10M"
        and run.intent.initialization_seed == 102
    )
    assert len({run.intent.sha256 for run in population}) == 4
    assert all(run.microbatch_examples == 64 for run in population)


def test_v12_population_plan_accepts_recovery_scale() -> None:
    screening = tuple(
        _run(model, seed, microbatch=32, experiment="v1.2-screen")
        for model in ("PC-29M", "PC-44M", "PC-64M")
        for seed in (101, 102)
    )

    population = build_initial_population_plan("PC-44M", screening)

    assert tuple(run.intent.initialization_seed for run in population) == (
        101,
        102,
        103,
        104,
    )
    assert all(run.intent.model_name == "PC-44M" for run in population)
    assert all(run.intent.experiment_name == "v1.2-screen" for run in population)
    assert all(run.microbatch_examples == 32 for run in population)


def test_population_plan_rejects_mixed_selected_scale_geometry() -> None:
    screening = (
        _run("PC-10M", 101, 64),
        _run("PC-10M", 102, 32),
    )

    with pytest.raises(ValueError, match="different resolved geometry"):
        build_initial_population_plan("PC-10M", screening)


def test_population_plan_requires_four_unique_seeds() -> None:
    screening = (_run("PC-10M", 101), _run("PC-10M", 102))

    with pytest.raises(ValueError, match="exactly four unique seeds"):
        build_initial_population_plan(
            "PC-10M",
            screening,
            population_seeds=(101, 102, 103),
        )
