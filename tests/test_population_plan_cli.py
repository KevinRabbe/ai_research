from plural_cognition.experiment import RunIntent, resolve_run_intent
from plural_cognition.manifest_io import (
    read_screening_plan,
    write_canonical_json,
    write_screening_plan,
)
from plural_cognition.population_plan_cli import main


def _run(model: str, seed: int):
    return resolve_run_intent(
        RunIntent("v1.1-screen", model, seed, 20260806),
        git_commit="a" * 40,
        precision="bf16",
        microbatch_examples=64,
        device_name="RTX 4060 Ti",
        preflight_sha256="b" * 64,
    )


def test_population_plan_command_reuses_screened_members(tmp_path) -> None:
    screening_path = tmp_path / "screening.json"
    screening = tuple(
        _run(model, seed)
        for model in ("PC-4M", "PC-10M", "PC-18M")
        for seed in (101, 102)
    )
    write_screening_plan(screening_path, screening)
    selection_path = tmp_path / "selection.json"
    write_canonical_json(
        selection_path,
        {
            "schema": "plural-cognition-scale-selection-v1",
            "selected": True,
            "selected_model": "PC-10M",
            "status": "selected",
            "reasons": ["qualified"],
            "summaries": [],
        },
    )
    output = tmp_path / "population.json"

    assert main(
        (
            "--screening-plan",
            str(screening_path),
            "--scale-selection",
            str(selection_path),
            "--output",
            str(output),
        )
    ) == 0
    population = read_screening_plan(output)
    assert len(population) == 4
    assert all(run.intent.model_name == "PC-10M" for run in population)
    assert tuple(run.intent.initialization_seed for run in population) == (
        101,
        102,
        103,
        104,
    )
