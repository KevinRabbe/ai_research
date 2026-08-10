"""Deterministic bounded catalogs used to define qualification ambiguity."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .ast import Expr
from .canonical import canonical_text
from .generator import GenerationConfig, generate_mechanism
from .semantics import semantic_key


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    mechanism: Expr
    semantic_bitset: int
    canonical: str


@dataclass(frozen=True, slots=True)
class MechanismCatalog:
    variable_order: tuple[str, ...]
    entries: tuple[CatalogEntry, ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("catalog must not be empty")
        bitsets = [entry.semantic_bitset for entry in self.entries]
        if len(bitsets) != len(set(bitsets)):
            raise ValueError("catalog entries must be semantically unique")


def build_catalog(
    seed: int,
    size: int,
    generation_config: GenerationConfig | None = None,
    max_attempt_multiplier: int = 100,
) -> MechanismCatalog:
    """Build a semantically deduplicated catalog reproducibly."""

    if size < 2:
        raise ValueError("catalog size must be at least 2")
    config = generation_config or GenerationConfig()
    rng = Random(seed)
    variable_order = config.variable_names()
    by_semantics: dict[int, CatalogEntry] = {}

    max_attempts = size * max_attempt_multiplier
    for _ in range(max_attempts):
        mechanism_seed = rng.getrandbits(63)
        mechanism = generate_mechanism(mechanism_seed, config)
        order, bitset = semantic_key(mechanism, variable_order)
        if order != variable_order:
            raise AssertionError("generator semantic order violated the catalog contract")
        by_semantics.setdefault(bitset, CatalogEntry(mechanism, bitset, canonical_text(mechanism)))
        if len(by_semantics) == size:
            break

    if len(by_semantics) != size:
        raise RuntimeError(
            f"could only build {len(by_semantics)} unique mechanisms; requested {size}"
        )

    entries = tuple(sorted(by_semantics.values(), key=lambda entry: (entry.semantic_bitset, entry.canonical)))
    return MechanismCatalog(variable_order, entries)
