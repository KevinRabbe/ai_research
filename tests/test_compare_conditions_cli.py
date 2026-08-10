from plural_cognition.compare_conditions_cli import main
from plural_cognition.manifest_io import read_canonical_json, write_canonical_json


def _population_payload(population_type: str, accuracies, gains, qualified: bool):
    return {
        "schema": "plural-cognition-population-evaluation-v1",
        "population_type": population_type,
        "members": [],
        "validation_shard_manifest_sha256s": ["a" * 64],
        "case_count": len(accuracies),
        "summary": {
            "analysis_coverage": 1.0,
            "mean_synthesis_accuracy": sum(accuracies) / len(accuracies),
            "mean_synthesis_gain": sum(gains) / len(gains),
        },
        "qualification": {"passed": qualified, "reasons": []},
        "tasks": [
            {
                "case_index": index,
                "full_synthesis_semantic_accuracy": accuracy,
                "synthesis_gain": gain,
            }
            for index, (accuracy, gain) in enumerate(zip(accuracies, gains, strict=True))
        ],
    }


def test_condition_comparison_command_writes_passing_artifact(tmp_path) -> None:
    primary_path = tmp_path / "primary.json"
    control_path = tmp_path / "control.json"
    output_path = tmp_path / "comparison.json"
    write_canonical_json(
        primary_path,
        _population_payload(
            "different-checkpoint-greedy",
            (1.0, 0.9, 1.0, 0.8),
            (0.25, 0.20, 0.25, 0.15),
            True,
        ),
    )
    write_canonical_json(
        control_path,
        _population_payload(
            "same-checkpoint-sampled",
            (0.6, 0.5, 0.7, 0.4),
            (0.05, 0.00, 0.10, 0.00),
            False,
        ),
    )

    assert main(
        (
            "--primary",
            str(primary_path),
            "--same-weight-control",
            str(control_path),
            "--bootstrap-resamples",
            "500",
            "--bootstrap-seed",
            "7",
            "--output",
            str(output_path),
        )
    ) == 0
    payload = read_canonical_json(output_path)
    assert payload["schema"] == "plural-cognition-condition-comparison-v1"
    assert payload["passed"] is True
    assert payload["paired_accuracy_advantage_ci"]["lower"] > 0
    assert payload["paired_gain_advantage_ci"]["lower"] > 0
