"""Prepare predeclared training-horizon recovery screening protocols."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .experiment import RunIntent, ResolvedRunManifest, resolve_run_intent
from .manifest_io import write_screening_plan
from .model import V1_2_MODEL_CONFIGS
from .preflight_resolution import _file_sha256, _load_report, _selected_case

T20M_EXPERIMENT_NAME = "v1.2-t20m-screen"
T20M_TOKEN_BUDGET = 20_000_000
T20M_CHECKPOINT_TOKENS = (
    1_000_000,
    2_000_000,
    5_000_000,
    10_000_000,
    15_000_000,
    20_000_000,
)

T30M_EXPERIMENT_NAME = "v1.2-t30m-screen"
T30M_TOKEN_BUDGET = 30_000_000
T30M_CHECKPOINT_TOKENS = (
    1_000_000,
    2_000_000,
    5_000_000,
    10_000_000,
    15_000_000,
    20_000_000,
    25_000_000,
    30_000_000,
)


def _screening_intents(
    *,
    experiment_name: str,
    token_budget: int,
    checkpoint_tokens: tuple[int, ...],
    initialization_seeds: tuple[int, ...],
    data_seed: int,
) -> tuple[RunIntent, ...]:
    if not initialization_seeds or len(initialization_seeds) != len(
        set(initialization_seeds)
    ):
        raise ValueError("initialization_seeds must be non-empty and unique")
    return tuple(
        RunIntent(
            experiment_name,
            model.name,
            seed,
            data_seed,
            token_budget=token_budget,
            checkpoint_tokens=checkpoint_tokens,
        )
        for model in V1_2_MODEL_CONFIGS
        for seed in initialization_seeds
    )


def t20m_screening_intents(
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
) -> tuple[RunIntent, ...]:
    """Return the frozen V1.2 capacity matrix under the 20M training horizon."""

    return _screening_intents(
        experiment_name=T20M_EXPERIMENT_NAME,
        token_budget=T20M_TOKEN_BUDGET,
        checkpoint_tokens=T20M_CHECKPOINT_TOKENS,
        initialization_seeds=initialization_seeds,
        data_seed=data_seed,
    )


def t30m_screening_intents(
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
) -> tuple[RunIntent, ...]:
    """Return the frozen V1.2 capacity matrix under the 30M training horizon."""

    return _screening_intents(
        experiment_name=T30M_EXPERIMENT_NAME,
        token_budget=T30M_TOKEN_BUDGET,
        checkpoint_tokens=T30M_CHECKPOINT_TOKENS,
        initialization_seeds=initialization_seeds,
        data_seed=data_seed,
    )


def _resolve_screening_plan_from_preflight(
    path: str | Path,
    *,
    intents: tuple[RunIntent, ...],
) -> tuple[ResolvedRunManifest, ...]:
    source = Path(path)
    report = _load_report(source)
    digest = _file_sha256(source)
    selected_by_model: dict[str, dict] = {}
    for intent in intents:
        selected_by_model.setdefault(
            intent.model_name,
            _selected_case(
                report,
                model_name=intent.model_name,
                sequence_length=intent.sequence_length,
                target_tokens_per_step=intent.target_tokens_per_optimizer_step,
            ),
        )
    return tuple(
        resolve_run_intent(
            intent,
            git_commit=report["git_commit"],
            precision=report["precision"],
            microbatch_examples=int(
                selected_by_model[intent.model_name]["microbatch"]
            ),
            device_name=report["hardware"]["gpu_name"],
            preflight_sha256=digest,
        )
        for intent in intents
    )


def resolve_t20m_screening_plan_from_preflight(
    path: str | Path,
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
) -> tuple[ResolvedRunManifest, ...]:
    """Resolve the 20M recovery matrix from one exact CUDA preflight report."""

    return _resolve_screening_plan_from_preflight(
        path,
        intents=t20m_screening_intents(
            initialization_seeds=initialization_seeds,
            data_seed=data_seed,
        ),
    )


def resolve_t30m_screening_plan_from_preflight(
    path: str | Path,
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
) -> tuple[ResolvedRunManifest, ...]:
    """Resolve the 30M recovery matrix from one exact CUDA preflight report."""

    return _resolve_screening_plan_from_preflight(
        path,
        intents=t30m_screening_intents(
            initialization_seeds=initialization_seeds,
            data_seed=data_seed,
        ),
    )


def _parser(*, token_budget_label: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the frozen PC-29M/44M/64M recovery screen at "
            f"{token_budget_label} training tokens."
        )
    )
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--initialization-seeds", type=int, nargs="+", default=(101, 102)
    )
    parser.add_argument("--data-seed", type=int, default=20260806)
    return parser


def _resolve_main(
    argv: Sequence[str] | None,
    *,
    token_budget_label: str,
    protocol_label: str,
    resolver,
) -> int:
    parser = _parser(token_budget_label=token_budget_label)
    args = parser.parse_args(argv)
    try:
        runs = resolver(
            args.preflight,
            initialization_seeds=tuple(args.initialization_seeds),
            data_seed=args.data_seed,
        )
        write_screening_plan(args.output, runs)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} with {len(runs)} resolved runs "
        f"protocol={protocol_label}"
    )
    for run in runs:
        print(
            f"{run.intent.run_id} model={run.intent.model_name} "
            f"microbatch={run.microbatch_examples} "
            f"accumulation={run.gradient_accumulation_steps} "
            f"token_budget={run.intent.token_budget}"
        )
    return 0


def resolve_t20m_screening_main(argv: Sequence[str] | None = None) -> int:
    return _resolve_main(
        argv,
        token_budget_label="20M",
        protocol_label="v1.2-t20m",
        resolver=resolve_t20m_screening_plan_from_preflight,
    )


def resolve_t30m_screening_main(argv: Sequence[str] | None = None) -> int:
    return _resolve_main(
        argv,
        token_budget_label="30M",
        protocol_label="v1.2-t30m",
        resolver=resolve_t30m_screening_plan_from_preflight,
    )


if __name__ == "__main__":
    raise SystemExit(resolve_t20m_screening_main())
