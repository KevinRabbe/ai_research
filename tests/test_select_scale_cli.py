from plural_cognition.manifest_io import read_canonical_json, write_canonical_json
from plural_cognition.select_scale_cli import main


def _evaluation(exact: float) -> dict:
    return {
        "schema": "plural-cognition-validation-evaluation-v1",
        "execution_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "validation_shard_manifest_sha256s": ["c" * 64],
        "case_count": 1,
        "parse_rate": 1.0,
        "exact_accuracy": exact,
        "visible_consistency_rate": exact,
        "mean_semantic_accuracy": exact,
        "cases": [
            {
                "case_index": 0,
                "task_id": "MODEL-TASK",
                "valid": True,
                "expression": "V0",
                "generated_token_ids": [12, 2],
                "generation_error": None,
                "exact": exact == 1.0,
                "visible_consistent": exact == 1.0,
                "semantic_accuracy": exact,
            }
        ],
    }


def test_scale_selection_command_writes_canonical_decision(tmp_path) -> None:
    values = {
        "PC-4M": (0.10, 0.15),
        "PC-10M": (0.30, 0.40),
        "PC-18M": (0.55, 0.60),
    }
    args = []
    for model, model_values in values.items():
        for seed, exact in zip((101, 102), model_values, strict=True):
            path = tmp_path / f"{model}-{seed}.json"
            write_canonical_json(path, _evaluation(exact))
            args.extend(("--result", model, str(seed), str(path)))
    output = tmp_path / "selection.json"
    args.extend(("--output", str(output)))

    assert main(tuple(args)) == 0
    payload = read_canonical_json(output)
    assert payload["schema"] == "plural-cognition-scale-selection-v1"
    assert payload["selected"] is True
    assert payload["selected_model"] == "PC-10M"
    assert payload["status"] == "selected"
    assert len(payload["summaries"]) == 3
