from types import SimpleNamespace

import torch
from torch import nn

from plural_cognition.boolean_world import (
    EvidenceCase,
    PublicTask,
    Var,
    encode_causal_example,
    encode_mechanism,
)
from plural_cognition.boolean_world.codec import PAD_ID, VOCAB_SIZE
from plural_cognition.inference import encode_inference_prompt
from plural_cognition.validation import (
    decode_supervised_causal_example,
    evaluate_validation_examples,
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


def _example():
    task = PublicTask(
        "TASK-VALIDATION",
        ("V0",),
        (
            EvidenceCase("E0", (False,), False),
            EvidenceCase("E1", (True,), True),
        ),
        (),
    )
    return encode_causal_example(task, Var("V0"))


def test_supervised_decoder_separates_public_task_and_target() -> None:
    decoded = decode_supervised_causal_example(_example())

    assert decoded.public.variable_order == ("V0",)
    assert decoded.target == Var("V0")


def test_validation_evaluation_scores_fixed_generated_program() -> None:
    decoded = decode_supervised_causal_example(_example())
    planned = encode_mechanism(Var("V0"))[2:]
    model = _ScriptedModel(len(encode_inference_prompt(decoded.public)), planned)

    result = evaluate_validation_examples(
        model,
        (_example(),),
        device=torch.device("cpu"),
    )

    assert result.parse_rate == 1.0
    assert result.exact_accuracy == 1.0
    assert result.visible_consistency_rate == 1.0
    assert result.mean_semantic_accuracy == 1.0


def test_invalid_generation_receives_zero_validation_credit() -> None:
    decoded = decode_supervised_causal_example(_example())
    model = _ScriptedModel(
        len(encode_inference_prompt(decoded.public)),
        (PAD_ID,),
    )

    result = evaluate_validation_examples(
        model,
        (_example(),),
        device=torch.device("cpu"),
        max_new_tokens=1,
    )

    assert result.parse_rate == 0.0
    assert result.exact_accuracy == 0.0
    assert result.mean_semantic_accuracy == 0.0
