from plural_cognition.boolean_world import Var
from plural_cognition.evaluate_cli import validation_evaluation_payload
from plural_cognition.inference import GenerationResult
from plural_cognition.validation import (
    ValidationCaseResult,
    ValidationEvaluation,
)


def test_validation_payload_preserves_fixed_outputs_and_scores() -> None:
    generation = GenerationResult(True, Var("V0"), (12, 2), None)
    case = ValidationCaseResult(
        0,
        "MODEL-TASK",
        generation,
        True,
        True,
        1.0,
    )
    evaluation = ValidationEvaluation((case,), 1.0, 1.0, 1.0, 1.0)

    payload = validation_evaluation_payload(
        evaluation,
        execution_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
        validation_shard_manifest_sha256s=("c" * 64,),
    )

    assert payload["schema"] == "plural-cognition-validation-evaluation-v1"
    assert payload["execution_sha256"] == "a" * 64
    assert payload["checkpoint_sha256"] == "b" * 64
    assert payload["validation_shard_manifest_sha256s"] == ["c" * 64]
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
