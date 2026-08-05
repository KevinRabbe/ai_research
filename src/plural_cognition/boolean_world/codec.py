"""Deterministic symbolic codec for Version 1 model inputs and outputs.

The model-facing task representation deliberately removes opaque identifiers while
preserving every semantically relevant field. Decoding produces a canonical task
with stable local identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .ast import And, Const, Expr, Ite, Not, Or, Var, variables
from .canonical import normalize
from .world import EvidenceCase, InterventionCase, PublicTask


class CodecError(ValueError):
    """Raised when symbolic input or model output violates the fixed grammar."""


SPECIAL_TOKENS = (
    "<PAD>",
    "<BOS>",
    "<EOS>",
    "<TASK>",
    "<VARS>",
    "<EVIDENCE>",
    "<CASE>",
    "<OUTPUT>",
    "<INTERVENTIONS>",
    "<INTERVENTION>",
    "<BEFORE>",
    "<AFTER>",
    "<CHANGED>",
    "<ANSWER>",
    "<TRUE>",
    "<FALSE>",
    "<NOT>",
    "<AND>",
    "<OR>",
    "<ITE>",
    "<0>",
    "<1>",
)
VARIABLE_TOKENS = tuple(f"V{index}" for index in range(20))
NUMBER_TOKENS = tuple(f"N{index}" for index in range(33))
TOKENS = SPECIAL_TOKENS + VARIABLE_TOKENS + NUMBER_TOKENS
TOKEN_TO_ID = {token: index for index, token in enumerate(TOKENS)}
ID_TO_TOKEN = TOKENS

if len(TOKEN_TO_ID) != len(TOKENS):
    raise RuntimeError("symbolic vocabulary contains duplicate tokens")

PAD_ID = TOKEN_TO_ID["<PAD>"]
BOS_ID = TOKEN_TO_ID["<BOS>"]
EOS_ID = TOKEN_TO_ID["<EOS>"]
VOCAB_SIZE = len(TOKENS)
DEFAULT_MAX_TOKENS = 256
MAX_EXPRESSION_NODES = 128
MAX_EXPRESSION_DEPTH = 16


def encode_tokens(tokens: Iterable[str]) -> tuple[int, ...]:
    result: list[int] = []
    for token in tokens:
        try:
            result.append(TOKEN_TO_ID[token])
        except KeyError as exc:
            raise CodecError(f"unknown symbolic token: {token!r}") from exc
    return tuple(result)


def decode_tokens(token_ids: Iterable[int]) -> tuple[str, ...]:
    result: list[str] = []
    for token_id in token_ids:
        if type(token_id) is not int:
            raise CodecError("token IDs must be plain integers")
        if not 0 <= token_id < VOCAB_SIZE:
            raise CodecError(f"token ID out of range: {token_id}")
        result.append(ID_TO_TOKEN[token_id])
    return tuple(result)


def _number_token(value: int) -> str:
    if type(value) is not int or not 0 <= value <= 32:
        raise CodecError("symbolic numbers must be integers in [0, 32]")
    return f"N{value}"


def _variable_token(name: str) -> str:
    if name not in VARIABLE_TOKENS:
        raise CodecError(f"unsupported variable name: {name!r}")
    return name


def _bit_token(value: bool) -> str:
    if type(value) is not bool:
        raise CodecError("Boolean fields must contain bool values")
    return "<1>" if value else "<0>"


def canonicalize_public_task(task: PublicTask) -> PublicTask:
    """Replace opaque identifiers with stable local identifiers.

    Task IDs and original case IDs have no problem-solving semantics. Removing them
    avoids wasting context or letting models exploit identifier artifacts.
    """

    case_ids = {
        case.case_id: f"C{index}" for index, case in enumerate(task.evidence)
    }
    evidence = tuple(
        EvidenceCase(f"C{index}", case.assignment, case.output)
        for index, case in enumerate(task.evidence)
    )
    interventions = tuple(
        InterventionCase(
            f"I{index}",
            item.variable,
            case_ids[item.before_case_id],
            case_ids[item.after_case_id],
            item.changed_output,
        )
        for index, item in enumerate(task.interventions)
    )
    return PublicTask("MODEL-TASK", task.variable_order, evidence, interventions)


def _validate_intervention_semantics(task: PublicTask) -> None:
    cases = {case.case_id: case for case in task.evidence}
    variable_index = {
        name: index for index, name in enumerate(task.variable_order)
    }

    for item in task.interventions:
        before = cases[item.before_case_id]
        after = cases[item.after_case_id]
        differences = tuple(
            index
            for index, (left, right) in enumerate(
                zip(before.assignment, after.assignment, strict=True)
            )
            if left != right
        )
        expected_index = variable_index[item.variable]
        if differences != (expected_index,):
            raise CodecError(
                "intervention cases must differ only in the declared variable"
            )
        if item.changed_output is not (before.output != after.output):
            raise CodecError(
                "intervention changed_output must match the referenced case outputs"
            )


def encode_public_task(
    task: PublicTask,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[int, ...]:
    """Encode all model-relevant public evidence into a fixed sequence."""

    canonical = canonicalize_public_task(task)
    _validate_intervention_semantics(canonical)

    if len(canonical.evidence) > 32 or len(canonical.interventions) > 32:
        raise CodecError("task sections may contain at most 32 items")

    tokens = [
        "<BOS>",
        "<TASK>",
        "<VARS>",
        _number_token(len(canonical.variable_order)),
    ]
    tokens.extend(_variable_token(name) for name in canonical.variable_order)
    tokens.extend(("<EVIDENCE>", _number_token(len(canonical.evidence))))

    for case in canonical.evidence:
        tokens.append("<CASE>")
        tokens.extend(_bit_token(value) for value in case.assignment)
        tokens.extend(("<OUTPUT>", _bit_token(case.output)))

    case_index = {
        case.case_id: index for index, case in enumerate(canonical.evidence)
    }
    tokens.extend(
        ("<INTERVENTIONS>", _number_token(len(canonical.interventions)))
    )

    for item in canonical.interventions:
        tokens.extend(
            (
                "<INTERVENTION>",
                _variable_token(item.variable),
                "<BEFORE>",
                _number_token(case_index[item.before_case_id]),
                "<AFTER>",
                _number_token(case_index[item.after_case_id]),
                "<CHANGED>",
                _bit_token(item.changed_output),
            )
        )

    tokens.append("<EOS>")
    encoded = encode_tokens(tokens)
    if len(encoded) > max_tokens:
        raise CodecError(
            f"encoded task length {len(encoded)} exceeds limit {max_tokens}"
        )
    return encoded


@dataclass(frozen=True, slots=True)
class CausalExample:
    """One decoder-only training sequence with an explicit label mask.

    ``label_mask[index]`` is true exactly for answer tokens that should be scored.
    A training loop that shifts labels by one position must shift this mask in the
    same way.
    """

    token_ids: tuple[int, ...]
    label_mask: tuple[bool, ...]
    answer_start: int

    def __post_init__(self) -> None:
        if len(self.token_ids) != len(self.label_mask):
            raise ValueError("token_ids and label_mask must have equal length")
        if not 0 <= self.answer_start < len(self.token_ids):
            raise ValueError("answer_start must identify a token in the sequence")


def encode_causal_example(
    task: PublicTask,
    answer: Expr,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> CausalExample:
    """Encode one prompt and canonical answer for decoder-only supervision."""

    task_ids = encode_public_task(task, max_tokens=max_tokens)
    answer_ids = encode_mechanism(answer, max_tokens=max_tokens)

    # Remove the task EOS and answer BOS so the result has one BOS and one EOS.
    token_ids = (*task_ids[:-1], *answer_ids[1:])
    if len(token_ids) > max_tokens:
        raise CodecError(
            f"causal example length {len(token_ids)} exceeds limit {max_tokens}"
        )

    answer_start = len(task_ids) - 1
    if token_ids[answer_start] != TOKEN_TO_ID["<ANSWER>"]:
        raise AssertionError("causal example answer boundary is inconsistent")

    label_mask = tuple(
        index > answer_start for index in range(len(token_ids))
    )
    return CausalExample(tuple(token_ids), label_mask, answer_start)


@dataclass(slots=True)
class _Reader:
    tokens: tuple[str, ...]
    position: int = 0

    def pop(self) -> str:
        if self.position >= len(self.tokens):
            raise CodecError("unexpected end of symbolic sequence")
        token = self.tokens[self.position]
        self.position += 1
        return token

    def expect(self, expected: str) -> None:
        actual = self.pop()
        if actual != expected:
            raise CodecError(f"expected {expected}, received {actual}")

    def number(self) -> int:
        token = self.pop()
        if not token.startswith("N") or not token[1:].isdigit():
            raise CodecError(f"expected number token, received {token}")
        value = int(token[1:])
        if not 0 <= value <= 32:
            raise CodecError("number token out of range")
        return value

    def variable(self) -> str:
        token = self.pop()
        if token not in VARIABLE_TOKENS:
            raise CodecError(f"expected variable token, received {token}")
        return token

    def bit(self) -> bool:
        token = self.pop()
        if token == "<0>":
            return False
        if token == "<1>":
            return True
        raise CodecError(f"expected Boolean token, received {token}")

    def finish(self) -> None:
        if self.position != len(self.tokens):
            raise CodecError("trailing tokens after complete symbolic value")


def decode_public_task(
    token_ids: Sequence[int],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> PublicTask:
    if len(token_ids) > max_tokens:
        raise CodecError("symbolic task exceeds configured token limit")

    reader = _Reader(decode_tokens(token_ids))
    reader.expect("<BOS>")
    reader.expect("<TASK>")
    reader.expect("<VARS>")

    variable_count = reader.number()
    if not 1 <= variable_count <= 20:
        raise CodecError("variable count must be in [1, 20]")

    variable_order = tuple(reader.variable() for _ in range(variable_count))
    if len(set(variable_order)) != len(variable_order):
        raise CodecError("variable order contains duplicates")

    reader.expect("<EVIDENCE>")
    evidence_count = reader.number()
    if evidence_count < 1:
        raise CodecError("task must contain at least one evidence case")

    evidence: list[EvidenceCase] = []
    for index in range(evidence_count):
        reader.expect("<CASE>")
        assignment = tuple(reader.bit() for _ in range(variable_count))
        reader.expect("<OUTPUT>")
        output = reader.bit()
        evidence.append(EvidenceCase(f"C{index}", assignment, output))

    reader.expect("<INTERVENTIONS>")
    intervention_count = reader.number()
    interventions: list[InterventionCase] = []

    for index in range(intervention_count):
        reader.expect("<INTERVENTION>")
        variable = reader.variable()
        reader.expect("<BEFORE>")
        before = reader.number()
        reader.expect("<AFTER>")
        after = reader.number()
        reader.expect("<CHANGED>")
        changed = reader.bit()

        if before >= evidence_count or after >= evidence_count:
            raise CodecError(
                "intervention case index is outside the evidence section"
            )

        interventions.append(
            InterventionCase(
                f"I{index}",
                variable,
                f"C{before}",
                f"C{after}",
                changed,
            )
        )

    reader.expect("<EOS>")
    reader.finish()

    try:
        task = PublicTask(
            "MODEL-TASK",
            variable_order,
            tuple(evidence),
            tuple(interventions),
        )
        _validate_intervention_semantics(task)
        return task
    except (TypeError, ValueError) as exc:
        raise CodecError(f"invalid decoded public task: {exc}") from exc


def _expression_tokens(expr: Expr) -> list[str]:
    match expr:
        case Const(value=True):
            return ["<TRUE>"]
        case Const(value=False):
            return ["<FALSE>"]
        case Var(name=name):
            return [_variable_token(name)]
        case Not(child=child):
            return ["<NOT>", *_expression_tokens(child)]
        case And(children=children):
            if len(children) > 16:
                raise CodecError(
                    "AND arity exceeds the Version 1 grammar limit"
                )
            return [
                "<AND>",
                _number_token(len(children)),
                *(
                    token
                    for child in children
                    for token in _expression_tokens(child)
                ),
            ]
        case Or(children=children):
            if len(children) > 16:
                raise CodecError(
                    "OR arity exceeds the Version 1 grammar limit"
                )
            return [
                "<OR>",
                _number_token(len(children)),
                *(
                    token
                    for child in children
                    for token in _expression_tokens(child)
                ),
            ]
        case Ite(
            condition=condition,
            when_true=when_true,
            when_false=when_false,
        ):
            return [
                "<ITE>",
                *_expression_tokens(condition),
                *_expression_tokens(when_true),
                *_expression_tokens(when_false),
            ]
        case _:
            raise CodecError(f"unsupported expression type: {type(expr)!r}")


def encode_mechanism(
    expr: Expr,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[int, ...]:
    tokens = [
        "<BOS>",
        "<ANSWER>",
        *_expression_tokens(normalize(expr)),
        "<EOS>",
    ]
    encoded = encode_tokens(tokens)
    if len(encoded) > max_tokens:
        raise CodecError("encoded mechanism exceeds configured token limit")
    return encoded


def decode_mechanism(
    token_ids: Sequence[int],
    *,
    allowed_variables: tuple[str, ...] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Expr:
    if len(token_ids) > max_tokens:
        raise CodecError("symbolic mechanism exceeds configured token limit")

    reader = _Reader(decode_tokens(token_ids))
    reader.expect("<BOS>")
    reader.expect("<ANSWER>")
    nodes = 0

    def parse(depth: int) -> Expr:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_EXPRESSION_NODES:
            raise CodecError("mechanism exceeds node limit")
        if depth > MAX_EXPRESSION_DEPTH:
            raise CodecError("mechanism exceeds depth limit")

        token = reader.pop()
        if token == "<TRUE>":
            return Const(True)
        if token == "<FALSE>":
            return Const(False)
        if token in VARIABLE_TOKENS:
            return Var(token)
        if token == "<NOT>":
            return Not(parse(depth + 1))
        if token in ("<AND>", "<OR>"):
            arity = reader.number()
            if not 1 <= arity <= 16:
                raise CodecError("AND/OR arity must be in [1, 16]")
            children = tuple(parse(depth + 1) for _ in range(arity))
            return And(children) if token == "<AND>" else Or(children)
        if token == "<ITE>":
            return Ite(
                parse(depth + 1),
                parse(depth + 1),
                parse(depth + 1),
            )
        raise CodecError(f"unexpected mechanism token: {token}")

    raw = parse(1)
    reader.expect("<EOS>")
    reader.finish()

    raw_variables = set(variables(raw))
    if allowed_variables is not None:
        unknown = raw_variables.difference(allowed_variables)
        if unknown:
            raise CodecError(
                f"mechanism uses variables outside task: {sorted(unknown)}"
            )

    return normalize(raw)
