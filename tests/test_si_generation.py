from dataclasses import replace
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from plural_cognition.boolean_world import (
    EvidenceCase,
    PublicTask,
    Var,
    encode_mechanism,
)
from plural_cognition.boolean_world.codec import VOCAB_SIZE
from plural_cognition.inference import encode_inference_prompt
from plural_cognition.self_improvement import (
    GenerationSource,
    TargetFreeGenerationArtifact,
    build_pool_from_generation_artifacts,
    generate_target_free_artifact,
)


class _ScriptedModel(nn.Module):
    def __init__(self, start_length: int, planned: tuple[int, ...]):
        super().__init__()
        self.start_length = start_length
        self.planned = planned
        self.config = SimpleNamespace(max_seq_len=256)

    def forward(self, input_ids, attention_mask=None):
        batch, sequence = input_ids.shape
        step = sequence - self.start_length
        token = self.planned[min(step, len(self.planned) - 1)]
        logits = torch.full((batch, sequence, VOCAB_SIZE), -1000.0)
        logits[:, -1, token] = 1000.0
        return logits


def _task() -> PublicTask:
    return PublicTask(
        "TASK-SI-GENERATION",
        ("V0",),
        (
            EvidenceCase("E0", (False,), False),
            EvidenceCase("E1", (True,), True),
        ),
        (),
    )


def _artifact(source: GenerationSource) -> TargetFreeGenerationArtifact:
    task = _task()
    planned = encode_mechanism(Var("V0"))[2:]
    model = _ScriptedModel(len(encode_inference_prompt(task)), planned)
    return generate_target_free_artifact(
        model,
        (task,),
        device=torch.device("cpu"),
        generation_git_commit="d" * 40,
        execution_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
        task_shard_manifest_sha256s=("c" * 64,),
        source=source,
    )


def test_target_free_artifact_contains_no_target_or_score_fields() -> None:
    artifact = _artifact(GenerationSource("greedy", "greedy", None, None, None))
    payload = artifact.canonical_payload()

    assert payload["schema"] == "plural-cognition-si-target-free-generation-v1"
    assert payload["generation_git_commit"] == "d" * 40
    assert payload["cases"][0]["expression"] == "V0"
    assert "target" not in str(payload)
    assert "accuracy" not in str(payload)
    assert TargetFreeGenerationArtifact.from_payload(payload) == artifact


def test_generation_artifacts_build_order_invariant_pool() -> None:
    greedy = _artifact(GenerationSource("greedy", "greedy", None, None, None))
    sampled = _artifact(
        GenerationSource("sample-401", "sampled", 401, 1.0, 8)
    )

    first = build_pool_from_generation_artifacts((greedy, sampled))
    second = build_pool_from_generation_artifacts((sampled, greedy))

    assert first == second
    assert first.sha256 == second.sha256
    assert [source.source_id for source in first.sources] == [
        "greedy",
        "sample-401",
    ]


def test_pool_rejects_generation_paths_from_different_si_commits() -> None:
    greedy = _artifact(GenerationSource("greedy", "greedy", None, None, None))
    sampled = replace(
        _artifact(GenerationSource("sample-401", "sampled", 401, 1.0, 8)),
        generation_git_commit="e" * 40,
    )

    with pytest.raises(ValueError, match="different SI code commits"):
        build_pool_from_generation_artifacts((greedy, sampled))
