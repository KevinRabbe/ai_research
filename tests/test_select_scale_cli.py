from plural_cognition.manifest_io import read_canonical_json, write_canonical_json
from plural_cognition.select_scale_cli import main


def _evaluation(exact: float) -> dict:
    return {
        "schema": "plural-cognition-validation-evaluation-v1",
        "execution_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "validation_shard_manifest_sha256s": ["c" * 64],
        "generation": {
            "mode": "greedy",
            "sampling_seed": None,
            "temperature": None,
            "top_k": None,
        },
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


def _run_selection(tmp_path, values, *, protocol="v1.1"):
    args = ["--protocol", protocol]
    for model, model_values in values.items():
        for seed, exact in zip((101, 102), model_values, strict=True):
            path = tmp_path / f"{model}-{seed}.json"
            write_canonical_json(path, _evaluation(exact))
            args.extend(("--result", model, str(seed), str(path)))
    output = tmp_path / f"selection-{protocol}.json"
    args.extend(("--output", str(output)))
    assert main(tuple(args)) == 0
    return read_canonical_json(output)


def test_scale_selection_command_writes_canonical_decision(tmp_path) -> None:
    payload = _run_selection(
        tmp_path,
        {
            "PC-4M": (0.10, 0.15),
            "PC-10M": (0.30, 0.40),
            "PC-18M": (0.55, 0.60),
        },
    )

    assert payload["schema"] == "plural-cognition-scale-selection-v1"
    assert payload["selected"] is True
    assert payload["selected_model"] == "PC-10M"
    assert payload["status"] == "selected"
    assert len(payload["summaries"]) == 3


def test_v12_scale_selection_command_uses_recovery_order(tmp_path) -> None:
    payload = _run_selection(
        tmp_path,
        {
            "PC-29M": (0.12, 0.16),
            "PC-44M": (0.25, 0.30),
            "PC-64M": (0.45, 0.50),
        },
        protocol="v1.2",
    )

    assert payload["selected"] is True
    assert payload["selected_model"] == "PC-44M"
    assert payload["status"] == "selected"
    assert [item["model_name"] for item in payload["summaries"]] == [
        "PC-29M",
        "PC-44M",
        "PC-64M",
    ]
