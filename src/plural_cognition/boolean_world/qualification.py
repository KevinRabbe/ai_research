"""Hidden qualification task construction and exact evaluation.

Only ``PublicTask`` should be serialized or passed to models. This module owns the
hidden target, catalog, and exhaustive evaluator used after a candidate is fixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from random import Random

from .ast import Expr
from .catalog import MechanismCatalog, build_catalog
from .generator import GenerationConfig
from .semantics import assignments, evaluate, semantic_distance
from .world import (
    Assignment,
    EvidenceCase,
    InterventionCase,
    PublicTask,
    assignment_mapping,
    evaluate_visible,
)


class AmbiguousTaskError(RuntimeError):
    """Raised when visible evidence cannot uniquely identify the catalog target."""


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    max_visible_cases: int = 16
    boundary_interventions: int = 2
    stable_interventions: int = 1
    require_both_outputs: bool = True
    require_hidden_cases: bool = True

    def __post_init__(self) -> None:
        if self.max_visible_cases < 2:
            raise ValueError("max_visible_cases must be at least 2")
        if self.boundary_interventions < 0 or self.stable_interventions < 0:
            raise ValueError("intervention counts must not be negative")
        if self.max_visible_cases < 2 * (self.boundary_interventions + self.stable_interventions):
            raise ValueError("max_visible_cases is too small for the requested intervention pairs")


@dataclass(frozen=True, slots=True)
class HiddenEvaluation:
    valid: bool
    exact: bool
    visible_consistent: bool
    semantic_distance: int
    assignment_count: int
    hidden_matched: int
    hidden_total: int
    error: str | None = None

    @property
    def semantic_accuracy(self) -> float:
        if not self.valid or self.assignment_count == 0:
            return 0.0
        return 1.0 - (self.semantic_distance / self.assignment_count)

    @property
    def hidden_accuracy(self) -> float:
        if not self.valid or self.hidden_total == 0:
            return 0.0
        return self.hidden_matched / self.hidden_total


class QualificationTask:
    """Container that separates public evidence from hidden exact evaluation."""

    __slots__ = (
        "public",
        "__target",
        "__catalog",
        "__hidden_assignments",
        "__target_bitset",
    )

    def __init__(
        self,
        public: PublicTask,
        target: Expr,
        target_bitset: int,
        catalog: MechanismCatalog,
        hidden_assignments: tuple[Assignment, ...],
    ) -> None:
        self.public = public
        self.__target = target
        self.__target_bitset = target_bitset
        self.__catalog = catalog
        self.__hidden_assignments = hidden_assignments

    def hidden_evaluate(self, candidate: Expr) -> HiddenEvaluation:
        visible = evaluate_visible(candidate, self.public)
        assignment_count = 1 << len(self.public.variable_order)
        try:
            distance = semantic_distance(candidate, self.__target, self.public.variable_order)
            hidden_matched = sum(
                evaluate(candidate, assignment_mapping(self.public.variable_order, assignment))
                == evaluate(self.__target, assignment_mapping(self.public.variable_order, assignment))
                for assignment in self.__hidden_assignments
            )
        except (KeyError, TypeError, ValueError) as exc:
            return HiddenEvaluation(
                False,
                False,
                visible.consistent,
                assignment_count,
                assignment_count,
                0,
                len(self.__hidden_assignments),
                str(exc),
            )

        return HiddenEvaluation(
            True,
            distance == 0,
            visible.consistent,
            distance,
            assignment_count,
            hidden_matched,
            len(self.__hidden_assignments),
        )

    def catalog_consistent_count(self) -> int:
        """Qualification-only ambiguity audit; never expose this to model code."""

        return sum(evaluate_visible(entry.mechanism, self.public).consistent for entry in self.__catalog.entries)

    def target_is_catalog_entry(self) -> bool:
        return any(entry.semantic_bitset == self.__target_bitset for entry in self.__catalog.entries)


def _output(bitset: int, assignment_index: int) -> bool:
    return bool((bitset >> assignment_index) & 1)


def _differing_variable(left: Assignment, right: Assignment) -> int | None:
    differences = [index for index, (a, b) in enumerate(zip(left, right, strict=True)) if a != b]
    return differences[0] if len(differences) == 1 else None


def _candidate_intervention_pairs(
    all_assignments: tuple[Assignment, ...], target_bitset: int
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    boundary: list[tuple[int, int, int]] = []
    stable: list[tuple[int, int, int]] = []
    for left_index, left in enumerate(all_assignments):
        for right_index in range(left_index + 1, len(all_assignments)):
            right = all_assignments[right_index]
            variable_index = _differing_variable(left, right)
            if variable_index is None:
                continue
            pair = (left_index, right_index, variable_index)
            if _output(target_bitset, left_index) != _output(target_bitset, right_index):
                boundary.append(pair)
            else:
                stable.append(pair)
    return boundary, stable


def _choose_visible_indices(
    seed: int,
    catalog: MechanismCatalog,
    target_index: int,
    config: EvidenceConfig,
) -> tuple[set[int], list[tuple[int, int, int]]]:
    target_bitset = catalog.entries[target_index].semantic_bitset
    all_assignments = tuple(tuple(item[name] for name in catalog.variable_order) for item in assignments(catalog.variable_order))
    rng = Random(seed)
    selected: set[int] = set()
    selected_pairs: list[tuple[int, int, int]] = []

    boundary, stable = _candidate_intervention_pairs(all_assignments, target_bitset)
    rng.shuffle(boundary)
    rng.shuffle(stable)

    for pairs, count in (
        (boundary, config.boundary_interventions),
        (stable, config.stable_interventions),
    ):
        for pair in pairs[:count]:
            selected.update(pair[:2])
            selected_pairs.append(pair)

    if len(selected) > config.max_visible_cases:
        raise AmbiguousTaskError("requested intervention evidence exceeds max_visible_cases")

    if config.require_both_outputs:
        for desired in (False, True):
            if not any(_output(target_bitset, index) == desired for index in selected):
                candidate = next(
                    index
                    for index in range(len(all_assignments))
                    if _output(target_bitset, index) == desired
                )
                selected.add(candidate)

    alternatives = {
        index
        for index, entry in enumerate(catalog.entries)
        if index != target_index
        and all(
            _output(entry.semantic_bitset, case_index) == _output(target_bitset, case_index)
            for case_index in selected
        )
    }

    while alternatives and len(selected) < config.max_visible_cases:
        choices: list[tuple[int, int]] = []
        for case_index in range(len(all_assignments)):
            if case_index in selected:
                continue
            eliminated = sum(
                _output(catalog.entries[alternative].semantic_bitset, case_index)
                != _output(target_bitset, case_index)
                for alternative in alternatives
            )
            choices.append((eliminated, case_index))

        best_elimination = max(eliminated for eliminated, _ in choices)
        if best_elimination == 0:
            break
        best_indices = [index for eliminated, index in choices if eliminated == best_elimination]
        chosen = rng.choice(best_indices)
        selected.add(chosen)
        alternatives = {
            alternative
            for alternative in alternatives
            if _output(catalog.entries[alternative].semantic_bitset, chosen)
            == _output(target_bitset, chosen)
        }

    if alternatives:
        raise AmbiguousTaskError(
            f"{len(alternatives) + 1} catalog mechanisms remain consistent after "
            f"{len(selected)} visible cases"
        )
    if config.require_hidden_cases and len(selected) == len(all_assignments):
        raise AmbiguousTaskError("qualification task has no hidden assignments")
    return selected, selected_pairs


def build_qualification_task(
    seed: int,
    catalog_size: int = 128,
    generation_config: GenerationConfig | None = None,
    evidence_config: EvidenceConfig | None = None,
) -> QualificationTask:
    """Build a deterministic public task plus isolated hidden evaluator."""

    generator_config = generation_config or GenerationConfig()
    visible_config = evidence_config or EvidenceConfig()
    catalog = build_catalog(seed ^ 0xA17E5EED, catalog_size, generator_config)
    rng = Random(seed)
    target_index = rng.randrange(len(catalog.entries))
    target_entry = catalog.entries[target_index]

    visible_indices, intervention_pairs = _choose_visible_indices(
        seed ^ 0x51A7E, catalog, target_index, visible_config
    )
    all_assignment_maps = assignments(catalog.variable_order)
    all_assignments = tuple(
        tuple(assignment[name] for name in catalog.variable_order)
        for assignment in all_assignment_maps
    )

    evidence = tuple(
        EvidenceCase(
            case_id=f"E{index:04d}",
            assignment=all_assignments[index],
            output=_output(target_entry.semantic_bitset, index),
        )
        for index in sorted(visible_indices)
    )
    case_id_by_index = {index: f"E{index:04d}" for index in visible_indices}
    interventions = tuple(
        InterventionCase(
            intervention_id=f"I{pair_index:03d}",
            variable=catalog.variable_order[variable_index],
            before_case_id=case_id_by_index[left],
            after_case_id=case_id_by_index[right],
            changed_output=_output(target_entry.semantic_bitset, left)
            != _output(target_entry.semantic_bitset, right),
        )
        for pair_index, (left, right, variable_index) in enumerate(intervention_pairs)
    )

    fingerprint = sha256(
        f"boolean-world-v1:{seed}:{catalog_size}:{generator_config}:{visible_config}".encode()
    ).hexdigest()[:20]
    public = PublicTask(
        task_id=f"BW1-{fingerprint}",
        variable_order=catalog.variable_order,
        evidence=evidence,
        interventions=interventions,
    )
    hidden_assignments = tuple(
        assignment for index, assignment in enumerate(all_assignments) if index not in visible_indices
    )
    task = QualificationTask(
        public,
        target_entry.mechanism,
        target_entry.semantic_bitset,
        catalog,
        hidden_assignments,
    )
    if task.catalog_consistent_count() != 1:
        raise AmbiguousTaskError("constructed task failed the final ambiguity audit")
    return task
