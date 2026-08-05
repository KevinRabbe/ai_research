"""Deterministic procedural generation of bounded Boolean mechanisms."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .ast import And, Const, Expr, Ite, Not, Or, Var, depth, variables
from .canonical import normalize
from .semantics import semantic_key


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    variable_count: int = 6
    min_atoms: int = 2
    max_atoms: int = 5
    max_depth: int = 4
    negation_probability: float = 0.30
    ite_probability: float = 0.15
    max_attempts: int = 512

    def __post_init__(self) -> None:
        if not 2 <= self.variable_count <= 20:
            raise ValueError("variable_count must be in [2, 20]")
        if not 2 <= self.min_atoms <= self.max_atoms:
            raise ValueError("atom range must satisfy 2 <= min_atoms <= max_atoms")
        if self.max_depth < 2:
            raise ValueError("max_depth must be at least 2")
        if not 0.0 <= self.negation_probability <= 1.0:
            raise ValueError("negation_probability must be in [0, 1]")
        if not 0.0 <= self.ite_probability <= 1.0:
            raise ValueError("ite_probability must be in [0, 1]")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    def variable_names(self) -> tuple[str, ...]:
        return tuple(f"V{index}" for index in range(self.variable_count))


def _random_atom(rng: Random, names: tuple[str, ...], negation_probability: float) -> Expr:
    atom: Expr = Var(rng.choice(names))
    if rng.random() < negation_probability:
        atom = Not(atom)
    return atom


def _pop_random(rng: Random, pool: list[Expr]) -> Expr:
    return pool.pop(rng.randrange(len(pool)))


def _build_candidate(rng: Random, config: GenerationConfig) -> Expr:
    names = config.variable_names()
    atom_count = rng.randint(config.min_atoms, config.max_atoms)
    pool = [_random_atom(rng, names, config.negation_probability) for _ in range(atom_count)]

    while len(pool) > 1:
        use_ite = len(pool) >= 3 and rng.random() < config.ite_probability
        if use_ite:
            condition = _pop_random(rng, pool)
            when_true = _pop_random(rng, pool)
            when_false = _pop_random(rng, pool)
            pool.append(Ite(condition, when_true, when_false))
        else:
            left = _pop_random(rng, pool)
            right = _pop_random(rng, pool)
            if rng.random() < 0.5:
                pool.append(And((left, right)))
            else:
                pool.append(Or((left, right)))

    return normalize(pool[0])


def _is_nontrivial(expr: Expr, config: GenerationConfig) -> bool:
    if isinstance(expr, (Const, Var, Not)):
        return False
    if depth(expr) > config.max_depth:
        return False
    if len(variables(expr)) < 2:
        return False

    order, bitset = semantic_key(expr, config.variable_names())
    assignment_count = 1 << len(order)
    all_true = (1 << assignment_count) - 1
    return bitset not in (0, all_true)


def generate_mechanism(seed: int, config: GenerationConfig | None = None) -> Expr:
    """Generate one bounded nontrivial mechanism reproducibly from ``seed``."""

    effective_config = config or GenerationConfig()
    rng = Random(seed)

    for _ in range(effective_config.max_attempts):
        candidate = _build_candidate(rng, effective_config)
        if _is_nontrivial(candidate, effective_config):
            return candidate

    raise RuntimeError(
        "could not generate a nontrivial mechanism within max_attempts; "
        "relax the generation constraints"
    )
