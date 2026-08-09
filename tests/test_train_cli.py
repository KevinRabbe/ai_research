from plural_cognition.dataset_shard import build_dataset_shard
from plural_cognition.execution import ExecutionManifest
from plural_cognition.experiment import RunIntent, resolve_run_intent
from plural_cognition.manifest_io import (
    write_dataset_shard_manifest,
    write_execution_manifest,
)
from plural_cognition.train_cli import _progress_bar, main
from plural_cognition.training_data import TrainingDataConfig


def test_progress_bar_reports_percentage_and_step_count() -> None:
    assert _progress_bar(0, 306, width=10) == "[----------]   0.00% (  0/306 steps)"
    assert _progress_bar(153, 306, width=10) == "[#####-----]  50.00% (153/306 steps)"
    assert _progress_bar(306, 306, width=10) == "[##########] 100.00% (306/306 steps)"


def test_training_command_dry_run_verifies_exact_shards_without_cuda(tmp_path) -> None:
    config = TrainingDataConfig(base_seed=5)
    train_data = tmp_path / "train.jsonl"
    validation_data = tmp_path / "validation.jsonl"
    train_manifest = build_dataset_shard(
        train_data,
        split="train",
        start_index=0,
        example_count=1,
        config=config,
    )
    validation_manifest = build_dataset_shard(
        validation_data,
        split="validation",
        start_index=0,
        example_count=1,
        config=config,
    )
    train_manifest_path = tmp_path / "train.manifest.json"
    validation_manifest_path = tmp_path / "validation.manifest.json"
    write_dataset_shard_manifest(train_manifest_path, train_manifest)
    write_dataset_shard_manifest(validation_manifest_path, validation_manifest)

    intent = RunIntent(
        "dry-run",
        "PC-4M",
        1,
        5,
        token_budget=256,
        target_tokens_per_optimizer_step=256,
        validation_examples=1,
        checkpoint_tokens=(256,),
    )
    run = resolve_run_intent(
        intent,
        git_commit="a" * 40,
        precision="bf16",
        microbatch_examples=1,
        device_name="unused in dry run",
        preflight_sha256="b" * 64,
    )
    execution = ExecutionManifest(run, (train_manifest,), (validation_manifest,))
    execution_path = tmp_path / "execution.json"
    write_execution_manifest(execution_path, execution)

    assert main(
        (
            "--execution",
            str(execution_path),
            "--preflight",
            str(tmp_path / "unused-preflight.json"),
            "--training-shard",
            str(train_data),
            str(train_manifest_path),
            "--validation-shard",
            str(validation_data),
            str(validation_manifest_path),
            "--output-dir",
            str(tmp_path / "output"),
            "--dry-run",
        )
    ) == 0
