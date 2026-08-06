from types import SimpleNamespace

import pytest
import torch
from torch import nn

from plural_cognition.boolean_world import (
    CatalogEntry,
    EvidenceCase,
    MechanismCatalog,
    Not,
    PublicTask,
    Var,
    canonical_text,
    encode_mechanism,
    encode_tokens,
    semantic_key,
)
from plural_cognition.boolean_world.qualification import QualificationTask
from plural_cognition.inference import (
    encode_inference_prompt,
    evaluate_checkpoint,
    greedy_generate_mechanism,
    sample_generate_mechanism,
)
from plural_cognition.boolean_world.codec import EOS_ID, PAD_ID, VOCAB_SIZE


class _ScriptedModel(nn.Module):
    def __init__(self, start_length: int, planned: tuple[int, ...], max_seq_len: int = 256):
        super().__init__()
        self.start_length = start_length
        self.planned = planned
        self.config = SimpleNamespace(max_seq_len=max_seq_len)

    def forward(self, input_ids, attention_mask=None):
        batch, sequence = input_ids.shape
        step = sequence - self.start_length
        token = self.planned[min(step, len(self.planned) - 1)]
        logits = torch.full((batch, sequence, VOCAB_SIZE), -1000.0)
        logits[:, -1, token] = 1000.0
        return logits


class _TwoPathModel(nn.Module):
    def __init__(self, start_length: int):
        super().__init__()
        self.start_length = start_length
        self.config = SimpleNamespace(max_seq_len=256)
        self.first_tokens = (
            encode_tokens(("V0",))[0],
            encode_tokens(("<TRUE>",))[0],
        )

    def forward(self, input_ids, attention_mask=None):
        batch, sequence = input_ids.shape
        step = sequence - self.start_length
        logits = torch.full((batch, sequence, VOCAB_SIZE), -1000.0)
        if step == 0:
            for token in self.first_tokens:
                logits[:, -1, token] = 0.0
        else:
            logits[:, -1, EOS_ID] = 1000.0
        return logits


def _public() -> PublicTask:
    return PublicTask(
        "TASK-INFERENCE",
        ("V0",),
        (EvidenceCase("E0", (False,), False),),
        (),
    )


def _qualification() -> QualificationTask:
    target = Var("V0")
    alternative = Not(Var("V0"))
    _, target_bits = semantic_key(target, ("V0",))
    _, alternative_bits = semantic_key(alternative, ("V0",))
    catalog = MechanismCatalog(
        ("V0",),
        (
            CatalogEntry(target, target_bits, canonical_text(target)),
            CatalogEntry(alternative, alternative_bits, canonical_text(alternative)),
        ),
    )
    return QualificationTask(
        _public(),
        target,
        target_bits,
        catalog,
        ((True,),),
    )


def test_greedy_generation_parses_canonical_mechanism() -> None:
    task = _public()
    prompt = encode_inference_prompt(task)
    planned = encode_mechanism(Var("V0"))[2:]
    model = _ScriptedModel(len(prompt), planned)

    result = greedy_generate_mechanism(
        model,
        task,
        device=torch.device("cpu"),
    )

    assert result.valid is True
    assert result.expression == Var("V0")
    assert result.generated_token_ids[-1] == EOS_ID


def test_seeded_sampling_is_reproducible() -> None:
    task = _public()
    prompt = encode_inference_prompt(task)
    model = _TwoPathModel(len(prompt))

    first = sample_generate_mechanism(
        model,
        task,
        device=torch.device("cpu"),
        seed=77,
    )
    second = sample_generate_mechanism(
        model,
        task,
        device=torch.device("cpu"),
        seed=77,
    )

    assert first == second
    assert first.valid is True


def test_sampling_rejects_invalid_temperature_and_top_k() -> None:
    model = _TwoPathModel(len(encode_inference_prompt(_public())))
    with pytest.raises(ValueError, match="temperature"):
        sample_generate_mechanism(
            model,
            _public(),
            device=torch.device("cpu"),
            seed=1,
            temperature=0.0,
        )
    with pytest.raises(ValueError, match="top_k"):
        sample_generate_mechanism(
            model,
            _public(),
            device=torch.device("cpu"),
            seed=1,
            top_k=0,
        )


def test_generation_fails_closed_on_malformed_answer() -> None:
    task = _public()
    prompt = encode_inference_prompt(task)
    model = _ScriptedModel(len(prompt), (PAD_ID, EOS_ID))

    result = greedy_generate_mechanism(model, task, device=torch.device("cpu"))

    assert result.valid is False
    assert result.expression is None
    assert result.error is not None


def test_hidden_evaluation_runs_only_after_output_is_fixed() -> None:
    task = _qualification()
    prompt = encode_inference_prompt(task.public)
    planned = encode_mechanism(Var("V0"))[2:]
    model = _ScriptedModel(len(prompt), planned)

    report = evaluate_checkpoint(
        model,
        (task,),
        device=torch.device("cpu"),
    )

    assert report.parse_rate == 1.0
    assert report.exact_accuracy == 1.0
    assert report.visible_consistency_rate == 1.0
    assert report.mean_semantic_accuracy == 1.0
    assert report.mean_hidden_accuracy == 1.0


def test_generation_refuses_prompt_without_answer_capacity() -> None:
    task = _public()
    prompt = encode_inference_prompt(task)
    model = _ScriptedModel(len(prompt), (EOS_ID,), max_seq_len=len(prompt))

    result = greedy_generate_mechanism(model, task, device=torch.device("cpu"))
    assert result.valid is False
    assert "capacity" in result.error
