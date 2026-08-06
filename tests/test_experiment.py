import pytest

from plural_cognition.experiment import (
    RunIntent,
    default_screening_plan,
    resolve_run_intent,
)


def test_default_screening_plan_is_three_scales_by_two_seeds() -> None:
    plan = default_screening_plan()

    assert len(plan) == 6
    assert {intent.model_name for intent in plan} == {"PC-4M", "PC-10M", "PC-18M"}
    assert {intent.initialization_seed for intent in plan} == {101, 102}
    assert len({intent.sha256 for intent in plan}) == 6
    assert all(intent.token_budget == 10_000_000 for intent in plan)


def test_run_intent_hash_is_deterministic_and_sensitive() -> None:
    first = RunIntent("screen", "PC-10M", 1, 2)
    same = RunIntent("screen", "PC-10M", 1, 2)
    changed = RunIntent("screen", "PC-10M", 2, 2)

    assert first.canonical_bytes() == same.canonical_bytes()
    assert first.sha256 == same.sha256
    assert first.run_id == same.run_id
    assert first.sha256 != changed.sha256


def test_resolved_manifest_exactly_matches_target_token_batch() -> None:
    intent = RunIntent("screen", "PC-10M", 1, 2)
    manifest = resolve_run_intent(
        intent,
        git_commit="a" * 40,
        precision="bf16",
        microbatch_examples=32,
        device_name="RTX 4060 Ti",
        preflight_sha256="b" * 64,
    )

    assert manifest.gradient_accumulation_steps == 4
    assert manifest.effective_tokens_per_optimizer_step == 32_768
    assert manifest.canonical_payload()["intent_sha256"] == intent.sha256
    assert len(manifest.sha256) == 64


def test_manifest_rejects_microbatch_that_breaks_matched_compute() -> None:
    intent = RunIntent("screen", "PC-10M", 1, 2)

    with pytest.raises(ValueError, match="exceeds"):
        resolve_run_intent(
            intent,
            git_commit="a" * 40,
            precision="bf16",
            microbatch_examples=256,
            device_name="RTX 4060 Ti",
            preflight_sha256="b" * 64,
        )


def test_intent_requires_final_checkpoint_at_budget() -> None:
    with pytest.raises(ValueError, match="final checkpoint"):
        RunIntent(
            "screen",
            "PC-4M",
            1,
            2,
            checkpoint_tokens=(1_000_000, 5_000_000),
        )
