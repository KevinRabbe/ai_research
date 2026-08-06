"""Create the first four-member run plan from screening and scale selection."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .manifest_io import (
    read_canonical_json,
    read_screening_plan,
    write_screening_plan,
)
from .population_plan import build_initial_population_plan


class PopulationPlanInputError(ValueError):
    pass


def _selected_model(path: str | Path) -> str:
    payload = read_canonical_json(path)
    expected = {
        "schema",
        "selected",
        "selected_model",
        "status",
        "reasons",
        "summaries",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PopulationPlanInputError("scale-selection artifact has wrong fields")
    if payload["schema"] != "plural-cognition-scale-selection-v1":
        raise PopulationPlanInputError("unsupported scale-selection schema")
    if payload["selected"] is not True or not isinstance(payload["selected_model"], str):
        raise PopulationPlanInputError("scale selection did not produce a model")
    return payload["selected_model"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reuse two selected-scale screening runs and add two seeds for a four-member population."
    )
    parser.add_argument("--screening-plan", type=Path, required=True)
    parser.add_argument("--scale-selection", type=Path, required=True)
    parser.add_argument("--population-seeds", type=int, nargs=4, default=(101, 102, 103, 104))
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        selected_model = _selected_model(args.scale_selection)
        screening_runs = read_screening_plan(args.screening_plan)
        population = build_initial_population_plan(
            selected_model,
            screening_runs,
            population_seeds=tuple(args.population_seeds),
        )
        write_screening_plan(args.output, population)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    reused = {
        run.intent.initialization_seed
        for run in screening_runs
        if run.intent.model_name == selected_model
    }
    print(
        f"wrote {args.output} selected_model={selected_model} "
        f"members={len(population)}"
    )
    for run in population:
        source = "reused" if run.intent.initialization_seed in reused else "new"
        print(
            f"seed={run.intent.initialization_seed} source={source} "
            f"run_id={run.intent.run_id}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
