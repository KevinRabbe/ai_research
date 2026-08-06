from dataclasses import replace

import pytest

from plural_cognition.checkpoint_bundle import (
    load_execution_checkpoint,
    save_execution_checkpoint,
)
from plural_cognition.dataset_shard import DatasetShardManifest
from plural_cognition.execution import ExecutionManifest
from plural_cognition.experiment import RunIntent, resolve_run_intent
from plural_cognition.model import PluralDecoder
from plural_cognition.training import TrainingState, build_optimizer


def _shard(split: str, count: int, records_sha256: str) -> DatasetShardManifest:
    return DatasetShardManifest(
        split,
        0,
        count,
        "c" * 64,
        records_sha256,
        count * 200,
    )


def _execution() -> ExecutionManifest:
    intent = RunIntent("screen", "PC-4M", 1, 2)
    run = resolve_run_intent(
        intent,
        git_commit="a" * 40,
        precision="fp32",
        microbatch_examples=128,
        device_name="CPU qualification",
        preflight_sha256="b" * 64,
    )
    return ExecutionManifest(
        run,
        (_shard("train", 39_168, "d" * 64),),
        (_shard("validation", 512, "e" * 64),),
    )


def test_execution_checkpoint_round_trip_binds_binary_and_sidecar(tmp_path) -> None:
    execution = _execution()
    model = PluralDecoder(execution.run.intent.model_config)
    optimizer = build_optimizer(model, execution.run.intent.optimizer)
    state = TrainingState(3, 98_304, 384)
    path = tmp_path / "checkpoint.pt"

    record = save_execution_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        execution=execution,
        state=state,
    )
    restored = load_execution_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        execution=execution,
    )

    assert restored == state
    assert record.execution_sha256 == execution.sha256
    assert record.checkpoint.file_sha256
    assert (tmp_path / "checkpoint.pt.manifest.json").exists()


def test_execution_checkpoint_rejects_different_dataset_shards(tmp_path) -> None:
    execution = _execution()
    model = PluralDecoder(execution.run.intent.model_config)
    optimizer = build_optimizer(model, execution.run.intent.optimizer)
    path = tmp_path / "checkpoint.pt"
    save_execution_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        execution=execution,
        state=TrainingState(),
    )
    changed_training = replace(
        execution.training_shards[0],
        records_sha256="9" * 64,
    )
    changed_execution = ExecutionManifest(
        execution.run,
        (changed_training,),
        execution.validation_shards,
    )

    with pytest.raises(ValueError, match="different dataset shards"):
        load_execution_checkpoint(
            path,
            model=model,
            optimizer=optimizer,
            execution=changed_execution,
        )


def test_execution_checkpoint_rejects_binary_tampering(tmp_path) -> None:
    execution = _execution()
    model = PluralDecoder(execution.run.intent.model_config)
    optimizer = build_optimizer(model, execution.run.intent.optimizer)
    path = tmp_path / "checkpoint.pt"
    save_execution_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        execution=execution,
        state=TrainingState(),
    )
    with path.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(ValueError, match="binary hash"):
        load_execution_checkpoint(
            path,
            model=model,
            optimizer=optimizer,
            execution=execution,
        )
