from dataclasses import replace

import pytest

from plural_cognition.collective import (
    CollectiveStage,
    MindBackend,
    MindIdentity,
    MindInvocationResult,
    MindRequest,
    ResourceUsage,
    TaskIdentity,
    sha256_content,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
GIT_SHA = "e" * 40


def task() -> TaskIdentity:
    return TaskIdentity("task-1", "coding", SHA_A)


def identity() -> MindIdentity:
    return MindIdentity(
        mind_id="mind-a",
        backend_family="local-dense",
        model_id="example/model",
        model_revision="revision-1",
        configuration_sha256=SHA_B,
    )


def request() -> MindRequest:
    return MindRequest(
        task=task(),
        run_id="run-1",
        protocol_sha256=SHA_C,
        visible_input_sha256=SHA_D,
    )


def result() -> MindInvocationResult:
    req = request()
    return MindInvocationResult(
        mind=identity(),
        request_sha256=req.sha256,
        output_content_sha256=sha256_content(b"answer"),
        software_revision=GIT_SHA,
        resources=ResourceUsage(
            input_tokens=50,
            output_tokens=10,
            inference_calls=1,
            accelerator_time_ms=250,
        ),
        finish_reason="stop",
    )


def test_mind_identity_binds_model_backend_revision_and_configuration() -> None:
    base = identity()
    assert base.sha256 == identity().sha256
    assert replace(base, backend_family="local-moe").sha256 != base.sha256
    assert replace(base, model_revision="revision-2").sha256 != base.sha256
    assert replace(base, configuration_sha256=SHA_C).sha256 != base.sha256


def test_request_binds_visible_inputs_without_hidden_evaluator_state() -> None:
    req = request()
    payload = req.canonical_payload()
    assert payload["task"]["task_id"] == "task-1"
    assert payload["visible_input_sha256"] == SHA_D
    assert "evaluator" not in payload
    assert "ground_truth" not in payload


def test_request_context_hashes_must_be_sorted_and_unique() -> None:
    req = request()
    sorted_req = replace(req, context_artifact_sha256s=(SHA_A, SHA_B))
    assert sorted_req.context_artifact_sha256s == (SHA_A, SHA_B)

    with pytest.raises(ValueError, match="sorted and unique"):
        replace(req, context_artifact_sha256s=(SHA_B, SHA_A))

    with pytest.raises(ValueError, match="sorted and unique"):
        replace(req, context_artifact_sha256s=(SHA_A, SHA_A))


def test_invocation_result_freezes_as_raw_mind_artifact() -> None:
    req = request()
    invocation = result()
    artifact = invocation.to_raw_artifact(req)

    assert artifact.stage is CollectiveStage.RAW_MIND_OUTPUT
    assert artifact.task == req.task
    assert artifact.producer_id == "mind-a"
    assert artifact.producer_configuration_sha256 == identity().sha256
    assert artifact.protocol_sha256 == req.protocol_sha256
    assert artifact.parent_sha256s == ()
    assert artifact.resources.total_tokens == 60


def test_invocation_result_rejects_different_request_identity() -> None:
    invocation = result()
    changed_request = replace(request(), visible_input_sha256=SHA_A)
    with pytest.raises(ValueError, match="request identity does not match"):
        invocation.to_raw_artifact(changed_request)


def test_backend_protocol_is_structural() -> None:
    class FakeBackend:
        def __init__(self) -> None:
            self._identity = identity()

        @property
        def identity(self) -> MindIdentity:
            return self._identity

        def invoke(self, req: MindRequest) -> MindInvocationResult:
            return MindInvocationResult(
                mind=self.identity,
                request_sha256=req.sha256,
                output_content_sha256=sha256_content(b"answer"),
                software_revision=GIT_SHA,
                resources=ResourceUsage(inference_calls=1),
                finish_reason="stop",
            )

    backend = FakeBackend()
    assert isinstance(backend, MindBackend)
    invocation = backend.invoke(request())
    assert invocation.mind == backend.identity
