import pytest

from plural_cognition.boolean_world import Var
from plural_cognition.evaluate_cli import (
    generation_protocol_payload,
    validation_evaluation_payload,
)
from plural_cognition.inference import GenerationResult
from plural_cognition.validation import (
    ValidationCaseResult,
    ValidationEvaluation,
)


def test_validation_payload_preserves_fixed_outputs_and_scores() -> None:
    generation_result = GenerationResult(True, Var("V0"), (12, 2), None)
    case = ValidationCaseResult(
        0,
        "MODEL-TASK",
        generation_result,
        True,
        True,
        1.0,
    )
    evaluation = ValidationEvaluation((case,), 1.0, 1.0, 1.0, 1.0)
    generation = generation_protocol_payload(
        sampling_seed=None,
        temperature=1.0,
        top_k=None,
    )

    payload = validation_evaluation_payload(
        evaluation,
        execution_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
        validation_shard_manifest_sha256s=("c" * 64,),
        generation=generation,
    )

    assert payload["schema"] == "plural-cognition-validation-evaluation-v1"
    assert payload["execution_sha256"] == "a" * 64
    assert payload["checkpoint_sha256"] == "b" * 64
    assert payload["validation_shard_manifest_sha256s"] == ["c" * 64]
    assert payload["generation"] == {
        "mode": "greedy",
        "sampling_seed": None,
        "temperature": None,
        "top_k": None,
    }
    assert payload["exact_accuracy"] == 1.0
    assert payload["cases"] == [
        {
            "case_index": 0,
            "task_id": "MODEL-TASK",
            "valid": True,
            "expression": "V0",
            "generated_token_ids": [12, 2],
            "generation_error": None,
            "exact": True,
            "visible_consistent": True,
            "semantic_accuracy": 1.0,
        }
    ]


def test_generation_protocol_requires_sampling_seed_for_sampling_controls() -> None:
    assert generation_protocol_payload(
        sampling_seed=301,
        temperature=0.8,
        top_k=8,
    ) == {
        "mode": "sampled",
        "sampling_seed": 301,
        "temperature": 0.8,
        "top_k": 8,
    }
    with pytest.raises(ValueError, match="require --sampling-seed"):
        generation_protocol_payload(
            sampling_seed=None,
            temperature=0.8,
            top_k=None,
        )
