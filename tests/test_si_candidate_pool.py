from copy import deepcopy

import pytest

from plural_cognition.boolean_world import EvidenceCase, PublicTask
from plural_cognition.self_improvement import (
    CandidatePoolError,
    FrozenCandidatePool,
    build_frozen_candidate_pool,
)


def _tasks():
    return (
        PublicTask(
            "TASK-0",
            ("V0",),
            (
                EvidenceCase("E0", (False,), False),
                EvidenceCase("E1", (True,), True),
            ),
            (),
        ),
    )


def _evaluation(
    seed: int,
    expression: str | None = "V0",
    *,
    generated_token_ids: list[int] | None = None,
) -> dict:
    valid = expression is not None
    tokens = [10 + seed, 2] if generated_token_ids is None else generated_token_ids
    return {
        "schema": "plural-cognition-validation-evaluation-v1",
        "execution_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "validation_shard_manifest_sha256s": ["c" * 64],
        "generation": {
            "mode": "sampled",
            "sampling_seed": seed,
            "temperature": 1.0,
            "top_k": 8,
        },
        "case_count": 1,
        "parse_rate": 1.0 if valid else 0.0,
        "exact_accuracy": 1.0 if valid else 0.0,
        "visible_consistency_rate": 1.0 if valid else 0.0,
        "mean_semantic_accuracy": 1.0 if valid else 0.0,
        "cases": [
            {
                "case_index": 0,
                "task_id": "MODEL-TASK",
                "valid": valid,
                "expression": expression,
                "generated_token_ids": tokens,
                "generation_error": None if valid else "parse failed",
                "exact": valid,
                "visible_consistent": valid,
                "semantic_accuracy": 1.0 if valid else 0.0,
            }
        ],
    }


def test_pool_is_deterministic_across_artifact_order() -> None:
    first = build_frozen_candidate_pool(
        _tasks(),
        (_evaluation(401), _evaluation(402, None)),
    )
    second = build_frozen_candidate_pool(
        _tasks(),
        (_evaluation(402, None), _evaluation(401)),
    )

    assert first == second
    assert first.sha256 == second.sha256
    assert [source.source_id for source in first.sources] == [
        "sample-401",
        "sample-402",
    ]
    assert first.tasks[0].public_task.variable_order == ("V0",)
    assert first.tasks[0].candidates[1].valid is False
    assert first.tasks[0].candidates[1].error == "parse failed"


def test_pool_preserves_failure_before_any_token_was_emitted() -> None:
    pool = build_frozen_candidate_pool(
        _tasks(),
        (_evaluation(401, None, generated_token_ids=[]),),
    )

    assert pool.tasks[0].candidates[0].valid is False
    assert pool.tasks[0].candidates[0].generated_token_ids == ()
    assert FrozenCandidatePool.from_payload(pool.canonical_payload()) == pool


def test_pool_round_trip_preserves_canonical_identity() -> None:
    pool = build_frozen_candidate_pool(_tasks(), (_evaluation(401),))

    restored = FrozenCandidatePool.from_payload(pool.canonical_payload())

    assert restored == pool
    assert restored.sha256 == pool.sha256
    assert "exact_accuracy" not in restored.canonical_payload()
    assert "semantic_accuracy" not in restored.canonical_payload()


def test_pool_rejects_mixed_checkpoints() -> None:
    changed = _evaluation(402)
    changed["checkpoint_sha256"] = "9" * 64

    with pytest.raises(CandidatePoolError, match="different checkpoints"):
        build_frozen_candidate_pool(_tasks(), (_evaluation(401), changed))


def test_pool_rejects_duplicate_generation_sources() -> None:
    with pytest.raises(CandidatePoolError, match="sources must be unique"):
        build_frozen_candidate_pool(_tasks(), (_evaluation(401), _evaluation(401)))


def test_pool_rejects_out_of_task_expression() -> None:
    changed = deepcopy(_evaluation(401))
    changed["cases"][0]["expression"] = "V1"

    with pytest.raises(ValueError):
        build_frozen_candidate_pool(_tasks(), (changed,))
