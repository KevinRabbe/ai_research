from dataclasses import replace

import pytest

from plural_cognition.dataset_shard import DatasetShardManifest
from plural_cognition.execution import ExecutionManifest
from plural_cognition.experiment import RunIntent, resolve_run_intent


def _run():
    return resolve_run_intent(
        RunIntent("screen", "PC-10M", 1, 2),
        git_commit="a" * 40,
        precision="bf16",
        microbatch_examples=32,
        device_name="RTX 4060 Ti",
        preflight_sha256="b" * 64,
    )


def _shard(split, start, count, records="d" * 64):
    return DatasetShardManifest(
        split,
        start,
        count,
        "c" * 64,
        records,
        count * 200,
    )


def test_execution_manifest_binds_complete_training_and_validation_data() -> None:
    manifest = ExecutionManifest(
        _run(),
        (_shard("train", 0, 39_168),),
        (_shard("validation", 0, 512, "e" * 64),),
    )

    assert manifest.optimizer_steps == 306
    assert manifest.examples_per_optimizer_step == 128
    assert manifest.required_training_examples == 39_168
    assert manifest.effective_training_tokens == 10_027_008
    assert manifest.training_example_count == 39_168
    assert len(manifest.sha256) == 64


def test_execution_accepts_contiguous_multi_shard_training_set() -> None:
    manifest = ExecutionManifest(
        _run(),
        (
            _shard("train", 0, 20_000),
            _shard("train", 20_000, 19_168, "f" * 64),
        ),
        (_shard("validation", 0, 512, "e" * 64),),
    )
    assert manifest.required_training_examples == 39_168


def test_execution_rejects_dataset_gap_and_insufficient_coverage() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        ExecutionManifest(
            _run(),
            (
                _shard("train", 0, 20_000),
                _shard("train", 20_001, 20_000, "f" * 64),
            ),
            (_shard("validation", 0, 512, "e" * 64),),
        )

    with pytest.raises(ValueError, match="complete matched-compute"):
        ExecutionManifest(
            _run(),
            (_shard("train", 0, 39_167),),
            (_shard("validation", 0, 512, "e" * 64),),
        )


def test_execution_rejects_mixed_data_configs() -> None:
    validation = replace(
        _shard("validation", 0, 512, "e" * 64),
        config_sha256="9" * 64,
    )
    with pytest.raises(ValueError, match="one data configuration"):
        ExecutionManifest(
            _run(),
            (_shard("train", 0, 39_168),),
            (validation,),
        )
