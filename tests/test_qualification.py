import pytest

from plural_cognition.boolean_world import (
    AmbiguousTaskError,
    EvidenceConfig,
    GenerationConfig,
    Var,
    build_catalog,
    build_qualification_task,
    evaluate_visible,
)


def _recover_target_for_test(seed: int, catalog_size: int, config: GenerationConfig, task):
    catalog = build_catalog(seed ^ 0xA17E5EED, catalog_size, config)
    matches = [
        entry.mechanism
        for entry in catalog.entries
        if evaluate_visible(entry.mechanism, task.public).consistent
    ]
    assert len(matches) == 1
    return matches[0], catalog


def test_qualification_task_is_deterministic_and_public_payload_has_no_ground_truth() -> None:
    config = GenerationConfig(variable_count=6, min_atoms=2, max_atoms=5, max_depth=5)
    first = build_qualification_task(123, 96, config)
    second = build_qualification_task(123, 96, config)

    assert first.public.to_payload() == second.public.to_payload()
    payload_text = repr(first.public.to_payload()).lower()
    assert "target" not in payload_text
    assert "catalog" not in payload_text
    assert "hidden" not in payload_text
    assert first.catalog_consistent_count() == 1
    assert first.target_is_catalog_entry() is True


def test_visible_evidence_uniquely_identifies_target_with_hidden_cases_remaining() -> None:
    seed = 456
    catalog_size = 128
    config = GenerationConfig(variable_count=6, min_atoms=2, max_atoms=5, max_depth=5)
    task = build_qualification_task(seed, catalog_size, config)
    target, catalog = _recover_target_for_test(seed, catalog_size, config, task)

    visible = evaluate_visible(target, task.public)
    hidden = task.hidden_evaluate(target)

    assert visible.consistent is True
    assert hidden.exact is True
    assert hidden.visible_consistent is True
    assert hidden.semantic_distance == 0
    assert hidden.hidden_total > 0
    assert hidden.hidden_accuracy == 1.0
    assert {case.output for case in task.public.evidence} == {False, True}

    wrong = next(
        entry.mechanism
        for entry in catalog.entries
        if not evaluate_visible(entry.mechanism, task.public).consistent
    )
    wrong_result = task.hidden_evaluate(wrong)
    assert wrong_result.exact is False
    assert wrong_result.semantic_distance > 0


def test_interventions_reference_one_bit_changes_and_correct_outputs() -> None:
    task = build_qualification_task(789, 96)
    cases = {case.case_id: case for case in task.public.evidence}
    variable_index = {name: index for index, name in enumerate(task.public.variable_order)}

    assert task.public.interventions
    for intervention in task.public.interventions:
        before = cases[intervention.before_case_id]
        after = cases[intervention.after_case_id]
        differences = [
            index
            for index, (left, right) in enumerate(zip(before.assignment, after.assignment, strict=True))
            if left != right
        ]
        assert differences == [variable_index[intervention.variable]]
        assert intervention.changed_output is (before.output != after.output)


def test_hidden_evaluator_rejects_unknown_candidate_variables() -> None:
    task = build_qualification_task(321, 64)
    result = task.hidden_evaluate(Var("UNKNOWN"))
    assert result.valid is False
    assert result.exact is False
    assert result.semantic_accuracy == 0.0


def test_ambiguous_tasks_are_rejected_when_visible_budget_is_too_small() -> None:
    with pytest.raises(AmbiguousTaskError):
        build_qualification_task(
            999,
            catalog_size=64,
            evidence_config=EvidenceConfig(
                max_visible_cases=2,
                boundary_interventions=0,
                stable_interventions=0,
            ),
        )
