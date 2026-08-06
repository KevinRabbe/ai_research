"""Construct the first four-member run plan from the selected screening scale."""

from __future__ import annotations

from .experiment import ResolvedRunManifest, RunIntent, resolve_run_intent
from .screening_selection import MODEL_ORDER


def build_initial_population_plan(
    selected_model: str,
    screening_runs: tuple[ResolvedRunManifest, ...],
    *,
    population_seeds: tuple[int, ...] = (101, 102, 103, 104),
) -> tuple[ResolvedRunManifest, ...]:
    """Reuse selected-scale screening runs and add seeds to reach four minds."""

    if selected_model not in MODEL_ORDER:
        raise ValueError(f"unknown selected model: {selected_model!r}")
    if len(population_seeds) != 4 or len(population_seeds) != len(set(population_seeds)):
        raise ValueError("the initial population requires exactly four unique seeds")
    matching = tuple(
        sorted(
            (
                run
                for run in screening_runs
                if run.intent.model_name == selected_model
            ),
            key=lambda run: run.intent.initialization_seed,
        )
    )
    if len(matching) < 2:
        raise ValueError("screening plan does not contain two selected-scale runs")
    template = matching[0]
    geometry = {
        (
            run.git_commit,
            run.precision,
            run.microbatch_examples,
            run.gradient_accumulation_steps,
            run.effective_tokens_per_optimizer_step,
            run.device_name,
            run.preflight_sha256,
        )
        for run in matching
    }
    if len(geometry) != 1:
        raise ValueError("selected-scale screening runs use different resolved geometry")
    intent_contracts = {
        (
            run.intent.experiment_name,
            run.intent.data_seed,
            run.intent.token_budget,
            run.intent.sequence_length,
            run.intent.target_tokens_per_optimizer_step,
            run.intent.validation_examples,
            run.intent.checkpoint_tokens,
            run.intent.optimizer,
        )
        for run in matching
    }
    if len(intent_contracts) != 1:
        raise ValueError("selected-scale screening runs use different training contracts")

    by_seed = {run.intent.initialization_seed: run for run in matching}
    if not set(by_seed).issubset(population_seeds):
        raise ValueError("existing selected-scale screening seeds are absent from population_seeds")

    result: list[ResolvedRunManifest] = []
    for seed in population_seeds:
        existing = by_seed.get(seed)
        if existing is not None:
            result.append(existing)
            continue
        source = template.intent
        intent = RunIntent(
            source.experiment_name,
            selected_model,
            seed,
            source.data_seed,
            source.token_budget,
            source.sequence_length,
            source.target_tokens_per_optimizer_step,
            source.validation_examples,
            source.checkpoint_tokens,
            source.optimizer,
        )
        result.append(
            resolve_run_intent(
                intent,
                git_commit=template.git_commit,
                precision=template.precision,
                microbatch_examples=template.microbatch_examples,
                device_name=template.device_name,
                preflight_sha256=template.preflight_sha256,
            )
        )
    return tuple(result)
