from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    PublicTask,
    Var,
    canonical_text,
    encode_causal_example,
    encode_public_task,
)
from plural_cognition.self_improvement import (
    CandidatePoolTask,
    FrozenCandidate,
    FrozenCandidatePool,
    GenerationSource,
    IMMUTABLE_PARENT_GENOME,
    PolicyMode,
    ReasoningBudget,
    ReasoningPolicyGenome,
    evaluate_policy_on_split,
    execute_reasoning_policy,
)


def _public() -> PublicTask:
    order = ("V0", "V1", "V2")
    evidence = tuple(
        EvidenceCase(
            f"E{value:03b}",
            tuple(bool((value >> shift) & 1) for shift in (2, 1, 0)),
            bool((value & 0b100) and (value & 0b010)),
        )
        for value in range(8)
    )
    return PublicTask("TASK-SI-POLICY", order, evidence, ())


def _pool() -> FrozenCandidatePool:
    public = _public()
    expressions = (
        ("sample-401", And((Var("V0"), Var("V2")))),
        ("sample-402", Var("V1")),
        ("sample-403", Var("V2")),
        ("sample-404", Var("V0")),
    )
    sources = tuple(
        GenerationSource(source_id, "sampled", 401 + index, 1.0, 8)
        for index, (source_id, _) in enumerate(expressions)
    )
    candidates = tuple(
        FrozenCandidate(
            source_id,
            True,
            canonical_text(expression),
            (20 + index, 2),
            None,
        )
        for index, (source_id, expression) in enumerate(expressions)
    )
    task = CandidatePoolTask(0, tuple(encode_public_task(public)), candidates)
    return FrozenCandidatePool(
        "a" * 64,
        "b" * 64,
        ("c" * 64,),
        sources,
        (task,),
    )


def test_verified_synthesis_improves_constructed_fixed_pool() -> None:
    pool = _pool()
    parent = execute_reasoning_policy(IMMUTABLE_PARENT_GENOME, pool.tasks[0])
    descendant = execute_reasoning_policy(
        ReasoningPolicyGenome(
            PolicyMode.VERIFIED_SYNTHESIS,
            max_unique_candidates=64,
            max_candidate_evaluations=128,
            max_generated_composites=128,
        ),
        pool.tasks[0],
    )

    assert parent.valid is True
    assert parent.visible_accuracy == 0.75
    assert descendant.valid is True
    assert descendant.canonical_expression == "AND(V0,V1)"
    assert descendant.visible_accuracy == 1.0
    assert {"sample-401", "sample-402"} <= set(descendant.source_ids)
    assert descendant.resources.generated_composites > 0


def test_policy_fails_closed_when_candidate_input_budget_is_exceeded() -> None:
    result = execute_reasoning_policy(
        IMMUTABLE_PARENT_GENOME,
        _pool().tasks[0],
        budget=ReasoningBudget(max_candidate_inputs=2),
    )

    assert result.valid is False
    assert result.expression is None
    assert "candidate input" in result.error
    assert result.resources.within_budget is False


def test_split_scorer_scores_only_after_policy_output_is_fixed() -> None:
    pool = _pool()
    example = encode_causal_example(
        _public(),
        And((Var("V0"), Var("V1"))),
    )
    descendant = ReasoningPolicyGenome(PolicyMode.VERIFIED_SYNTHESIS)

    parent_score = evaluate_policy_on_split(
        IMMUTABLE_PARENT_GENOME,
        pool,
        (example,),
    )
    descendant_score = evaluate_policy_on_split(
        descendant,
        pool,
        (example,),
    )

    assert parent_score.mean_semantic_accuracy == 0.75
    assert parent_score.exact_accuracy == 0.0
    assert descendant_score.mean_semantic_accuracy == 1.0
    assert descendant_score.exact_accuracy == 1.0
    assert descendant_score.invalid_rate == 0.0
    assert descendant_score.fitness_key < parent_score.fitness_key
