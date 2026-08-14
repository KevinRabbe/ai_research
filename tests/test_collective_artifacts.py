from dataclasses import replace

import pytest

from plural_cognition.collective import (
    CollectiveStage,
    EvaluationRecord,
    EvaluationVisibility,
    MetricValue,
    ResourceUsage,
    StageArtifact,
    TaskIdentity,
    sha256_content,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
GIT_SHA = "d" * 40


def task() -> TaskIdentity:
    return TaskIdentity("task-1", "coding", SHA_A)


def raw_artifact() -> StageArtifact:
    return StageArtifact(
        CollectiveStage.RAW_MIND_OUTPUT,
        task(),
        "run-1",
        "mind-a",
        SHA_B,
        SHA_C,
        GIT_SHA,
        sha256_content(b"candidate-a"),
        resources=ResourceUsage(
            input_tokens=100,
            output_tokens=25,
            inference_calls=1,
            wall_time_ms=500,
            accelerator_time_ms=450,
            peak_accelerator_bytes=1_000_000,
        ),
    )


def test_resource_usage_is_nonnegative_and_rejects_bool() -> None:
    usage = ResourceUsage(input_tokens=10, output_tokens=5)
    assert usage.total_tokens == 15

    with pytest.raises(ValueError, match="must not be negative"):
        ResourceUsage(tool_calls=-1)

    with pytest.raises(TypeError, match="must be int"):
        ResourceUsage(inference_calls=True)


def test_task_identity_requires_exact_lowercase_sha256() -> None:
    assert task().canonical_payload()["payload_sha256"] == SHA_A

    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        TaskIdentity("task-1", "coding", "abc")

    with pytest.raises(ValueError, match="lowercase"):
        TaskIdentity("task-1", "coding", "A" * 64)


def test_raw_artifact_is_deterministic_and_has_no_parent() -> None:
    first = raw_artifact()
    second = raw_artifact()
    assert first.sha256 == second.sha256
    assert first.resources.total_tokens == 125
    assert first.parent_sha256s == ()

    with pytest.raises(ValueError, match="must not have parent"):
        replace(first, parent_sha256s=(SHA_A,))


def test_non_raw_stage_requires_sorted_unique_parent_hashes() -> None:
    raw = raw_artifact()
    synthesis = StageArtifact(
        CollectiveStage.SYNTHESIS,
        raw.task,
        "run-1",
        "synthesizer-v1",
        SHA_B,
        SHA_C,
        GIT_SHA,
        sha256_content(b"combined"),
        parent_sha256s=(raw.sha256,),
    )
    assert synthesis.parent_sha256s == (raw.sha256,)

    with pytest.raises(ValueError, match="require at least one parent"):
        replace(synthesis, parent_sha256s=())

    with pytest.raises(ValueError, match="sorted and unique"):
        replace(synthesis, parent_sha256s=(SHA_B, SHA_A))

    with pytest.raises(ValueError, match="sorted and unique"):
        replace(synthesis, parent_sha256s=(SHA_A, SHA_A))


def test_content_change_changes_artifact_identity_without_mutating_parent() -> None:
    original = raw_artifact()
    revised = replace(original, content_sha256=sha256_content(b"candidate-b"))
    assert revised.sha256 != original.sha256
    assert original.content_sha256 == sha256_content(b"candidate-a")


def test_sha256_content_accepts_bytes_only() -> None:
    assert sha256_content(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
    with pytest.raises(TypeError, match="content must be bytes"):
        sha256_content("abc")  # type: ignore[arg-type]


def test_evaluation_record_binds_artifact_evaluator_and_visibility() -> None:
    raw = raw_artifact()
    record = EvaluationRecord(
        artifact_sha256=raw.sha256,
        task=raw.task,
        evaluator_id="coding-tests-v1",
        evaluator_configuration_sha256=SHA_A,
        evaluator_software_revision=GIT_SHA,
        visibility=EvaluationVisibility.PROTECTED,
        metrics=(
            MetricValue("exact", 1.0),
            MetricValue("tests_passed", 17),
        ),
        qualified=True,
        resources=ResourceUsage(verifier_calls=1, wall_time_ms=250),
    )
    same = replace(record)
    assert record.sha256 == same.sha256
    assert record.canonical_payload()["visibility"] == "protected"

    changed = replace(record, visibility=EvaluationVisibility.DEVELOPMENT)
    assert changed.sha256 != record.sha256


def test_evaluation_metrics_must_be_sorted_unique_and_finite() -> None:
    raw = raw_artifact()
    base = dict(
        artifact_sha256=raw.sha256,
        task=raw.task,
        evaluator_id="eval",
        evaluator_configuration_sha256=SHA_A,
        evaluator_software_revision=GIT_SHA,
        visibility=EvaluationVisibility.DEVELOPMENT,
    )

    with pytest.raises(ValueError, match="sorted by unique name"):
        EvaluationRecord(
            **base,
            metrics=(MetricValue("z", 1), MetricValue("a", 1)),
        )

    with pytest.raises(ValueError, match="sorted by unique name"):
        EvaluationRecord(
            **base,
            metrics=(MetricValue("a", 1), MetricValue("a", 2)),
        )

    with pytest.raises(ValueError, match="finite"):
        MetricValue("bad", float("nan"))
