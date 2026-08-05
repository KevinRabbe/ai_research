"""Public task contracts and visible-only evaluation for Boolean worlds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast import Expr
from .semantics import evaluate

Assignment = tuple[bool, ...]


def assignment_mapping(variable_order: tuple[str, ...], assignment: Assignment) -> dict[str, bool]:
    if len(variable_order) != len(assignment):
        raise ValueError("assignment length must match variable_order")
    if any(type(value) is not bool for value in assignment):
        raise TypeError("assignment values must be bool")
    return dict(zip(variable_order, assignment, strict=True))


@dataclass(frozen=True, slots=True)
class EvidenceCase:
    case_id: str
    assignment: Assignment
    output: bool

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("case_id must not be empty")
        if any(type(value) is not bool for value in self.assignment):
            raise TypeError("assignment values must be bool")
        if type(self.output) is not bool:
            raise TypeError("output must be bool")


@dataclass(frozen=True, slots=True)
class InterventionCase:
    intervention_id: str
    variable: str
    before_case_id: str
    after_case_id: str
    changed_output: bool

    def __post_init__(self) -> None:
        if not self.intervention_id or not self.variable:
            raise ValueError("intervention_id and variable must not be empty")
        if self.before_case_id == self.after_case_id:
            raise ValueError("an intervention must connect two different cases")
        if type(self.changed_output) is not bool:
            raise TypeError("changed_output must be bool")


@dataclass(frozen=True, slots=True)
class PublicTask:
    task_id: str
    variable_order: tuple[str, ...]
    evidence: tuple[EvidenceCase, ...]
    interventions: tuple[InterventionCase, ...]

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.variable_order or len(self.variable_order) != len(set(self.variable_order)):
            raise ValueError("variable_order must be non-empty and unique")
        if not self.evidence:
            raise ValueError("public task requires evidence")

        case_ids = {case.case_id for case in self.evidence}
        if len(case_ids) != len(self.evidence):
            raise ValueError("evidence case IDs must be unique")
        for case in self.evidence:
            if len(case.assignment) != len(self.variable_order):
                raise ValueError("evidence assignment length must match variable_order")

        variables = set(self.variable_order)
        for intervention in self.interventions:
            if intervention.variable not in variables:
                raise ValueError("intervention variable must occur in variable_order")
            if intervention.before_case_id not in case_ids or intervention.after_case_id not in case_ids:
                raise ValueError("intervention must reference visible evidence cases")

    def to_payload(self) -> dict[str, Any]:
        """Return the complete public model input without hidden evaluator state."""

        return {
            "task_id": self.task_id,
            "variable_order": list(self.variable_order),
            "evidence": [
                {
                    "case_id": case.case_id,
                    "assignment": list(case.assignment),
                    "output": case.output,
                }
                for case in self.evidence
            ],
            "interventions": [
                {
                    "intervention_id": item.intervention_id,
                    "variable": item.variable,
                    "before_case_id": item.before_case_id,
                    "after_case_id": item.after_case_id,
                    "changed_output": item.changed_output,
                }
                for item in self.interventions
            ],
        }


@dataclass(frozen=True, slots=True)
class VisibleEvaluation:
    valid: bool
    matched: int
    total: int
    mismatch_case_ids: tuple[str, ...]
    error: str | None = None

    @property
    def consistent(self) -> bool:
        return self.valid and self.matched == self.total


def evaluate_visible(candidate: Expr, task: PublicTask) -> VisibleEvaluation:
    """Evaluate only against evidence available to every model and synthesizer."""

    mismatches: list[str] = []
    matched = 0
    try:
        for case in task.evidence:
            observed = evaluate(candidate, assignment_mapping(task.variable_order, case.assignment))
            if observed == case.output:
                matched += 1
            else:
                mismatches.append(case.case_id)
    except (KeyError, TypeError, ValueError) as exc:
        return VisibleEvaluation(False, 0, len(task.evidence), tuple(), str(exc))

    return VisibleEvaluation(True, matched, len(task.evidence), tuple(mismatches))
