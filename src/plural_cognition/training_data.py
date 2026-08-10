"""Deterministic supervised data stream for the one-member learning preflight.

Training targets are returned in a separate object and are never included in the
public model input. Qualification and final evaluation continue to use the
hidden ``QualificationTask`` boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from random import Random
from typing import Iterator, Literal

from .boolean_world.ast import Expr
from .boolean_world.catalog import build_catalog
from .boolean_world.codec import CausalExample, encode_causal_example
from .boolean_world.generator import GenerationConfig
from .boolean_world.qualification import (
    AmbiguousTaskError,
    EvidenceConfig,
    _choose_visible_indices,
    _output,
)
from .boolean_world.world import EvidenceCase, InterventionCase, PublicTask, evaluate_visible

DataSplit = Literal["train", "validation", "test"]
_VALID_SPLITS = ("train", "validation", "test")


@dataclass(frozen=True, slots=True)
class SupervisedBooleanExample:
    seed: int
    public: PublicTask
    target: Expr
    target_semantic_bitset: int

    def causal(self, *, max_tokens: int = 256) -> CausalExample:
        return encode_causal_example(self.public, self.target, max_tokens=max_tokens)


@dataclass(frozen=True, slots=True)
class TrainingDataConfig:
    base_seed: int = 20260806
    catalog_size: int = 128
    generation: GenerationConfig = GenerationConfig()
    evidence: EvidenceConfig = EvidenceConfig()
    max_tokens: int = 256

    def __post_init__(self) -> None:
        if type(self.base_seed) is not int:
            raise TypeError("base_seed must be int")
        if self.catalog_size < 2:
            raise ValueError("catalog_size must be at least 2")
        if self.max_tokens < 2:
            raise ValueError("max_tokens must be at least 2")


def derive_example_seed(base_seed: int, split: DataSplit, index: int) -> int:
    """Derive a stable 63-bit seed with disjoint split namespaces."""

    if split not in _VALID_SPLITS:
        raise ValueError(f"unknown data split: {split!r}")
    if type(index) is not int or index < 0:
        raise ValueError("example index must be a non-negative int")
    digest = sha256(
        f"plural-cognition-data-v1:{base_seed}:{split}:{index}".encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def build_supervised_example(
    seed: int,
    config: TrainingDataConfig | None = None,
) -> SupervisedBooleanExample:
    """Build one public task and its physically separate supervised target."""

    effective = config or TrainingDataConfig()
    catalog = build_catalog(
        seed ^ 0xA17E5EED,
        effective.catalog_size,
        effective.generation,
    )
    rng = Random(seed)
    target_index = rng.randrange(len(catalog.entries))
    target_entry = catalog.entries[target_index]
    visible_indices, intervention_pairs = _choose_visible_indices(
        seed ^ 0x51A7E,
        catalog,
        target_index,
        effective.evidence,
    )

    variable_order = catalog.variable_order
    assignment_count = 1 << len(variable_order)
    all_assignments = tuple(
        tuple(bool((index >> (len(variable_order) - position - 1)) & 1) for position in range(len(variable_order)))
        for index in range(assignment_count)
    )
    evidence = tuple(
        EvidenceCase(
            f"E{index:04d}",
            all_assignments[index],
            _output(target_entry.semantic_bitset, index),
        )
        for index in sorted(visible_indices)
    )
    case_id_by_index = {index: f"E{index:04d}" for index in visible_indices}
    interventions = tuple(
        InterventionCase(
            f"I{pair_index:03d}",
            variable_order[variable_index],
            case_id_by_index[left],
            case_id_by_index[right],
            _output(target_entry.semantic_bitset, left)
            != _output(target_entry.semantic_bitset, right),
        )
        for pair_index, (left, right, variable_index) in enumerate(intervention_pairs)
    )
    fingerprint = sha256(
        (
            "boolean-world-supervised-v1:"
            f"{seed}:{effective.catalog_size}:"
            f"{effective.generation}:{effective.evidence}"
        ).encode("ascii")
    ).hexdigest()[:20]
    public = PublicTask(
        f"BW1S-{fingerprint}",
        variable_order,
        evidence,
        interventions,
    )

    consistent = sum(
        evaluate_visible(entry.mechanism, public).consistent
        for entry in catalog.entries
    )
    if consistent != 1:
        raise AmbiguousTaskError(
            f"supervised task ambiguity audit found {consistent} consistent catalog entries"
        )

    example = SupervisedBooleanExample(
        seed,
        public,
        target_entry.mechanism,
        target_entry.semantic_bitset,
    )
    example.causal(max_tokens=effective.max_tokens)
    return example


def example_at(
    split: DataSplit,
    index: int,
    config: TrainingDataConfig | None = None,
) -> SupervisedBooleanExample:
    effective = config or TrainingDataConfig()
    return build_supervised_example(
        derive_example_seed(effective.base_seed, split, index),
        effective,
    )


def iter_causal_examples(
    split: DataSplit,
    *,
    start: int = 0,
    count: int | None = None,
    config: TrainingDataConfig | None = None,
) -> Iterator[CausalExample]:
    """Yield a reproducible index-addressable stream without mutable RNG state."""

    if type(start) is not int or start < 0:
        raise ValueError("start must be a non-negative int")
    if count is not None and (type(count) is not int or count < 0):
        raise ValueError("count must be a non-negative int or None")
    effective = config or TrainingDataConfig()
    index = start
    emitted = 0
    while count is None or emitted < count:
        yield example_at(split, index, effective).causal(
            max_tokens=effective.max_tokens
        )
        index += 1
        emitted += 1
