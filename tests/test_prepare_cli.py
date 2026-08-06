import json

from plural_cognition.dataset_shard import (
    DatasetShardManifest,
    training_data_config_sha256,
)
from plural_cognition.manifest_io import (
    read_execution_manifest,
    read_screening_plan,
    write_dataset_shard_manifest,
)
from plural_cognition.prepare_cli import (
    prepare_execution_main,
    resolve_screening_plan_main,
)
from plural_cognition.training_data import TrainingDataConfig


def _preflight_payload():
    return {
        "schema_version": 1,
        "mode": "cuda_training_preflight",
        "git_commit": "a" * 40,
        "precision": "bf16",
        "hardware": {"gpu_name": "RTX 4060 Ti"},
        "results": [
            {
                "model_name": model,
                "sequence_length": 256,
                "microbatch": 64,
                "status": "ok",
                "within_vram_limit": True,
                "tokens_per_second": 1000.0,
            }
            for model in ("PC-4M", "PC-10M", "PC-18M")
        ],
    }


def test_resolve_and_prepare_execution_commands(tmp_path) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(_preflight_payload()), encoding="utf-8")
    plan_path = tmp_path / "screening-plan.json"

    assert resolve_screening_plan_main(
        ("--preflight", str(preflight), "--output", str(plan_path))
    ) == 0
    runs = read_screening_plan(plan_path)
    assert len(runs) == 6

    config_hash = training_data_config_sha256(
        TrainingDataConfig(base_seed=20260806)
    )
    train_manifest = DatasetShardManifest(
        "train", 0, 39_168, config_hash, "b" * 64, 8_000_000
    )
    validation_manifest = DatasetShardManifest(
        "validation", 0, 512, config_hash, "c" * 64, 100_000
    )
    train_path = tmp_path / "train.manifest.json"
    validation_path = tmp_path / "validation.manifest.json"
    write_dataset_shard_manifest(train_path, train_manifest)
    write_dataset_shard_manifest(validation_path, validation_manifest)
    execution_path = tmp_path / "execution.json"

    assert prepare_execution_main(
        (
            "--screening-plan",
            str(plan_path),
            "--model",
            "PC-10M",
            "--initialization-seed",
            "101",
            "--training-manifests",
            str(train_path),
            "--validation-manifests",
            str(validation_path),
            "--output",
            str(execution_path),
        )
    ) == 0
    execution = read_execution_manifest(execution_path)
    assert execution.run.intent.model_name == "PC-10M"
    assert execution.run.microbatch_examples == 64
    assert execution.required_training_examples == 39_168
