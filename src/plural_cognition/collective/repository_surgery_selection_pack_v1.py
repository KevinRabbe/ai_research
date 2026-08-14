"""Frozen-candidate Repository Surgery selection-pack construction and qualification.

This module is the first post-calibration task construction step.  It binds the
final five-candidate operational freeze before any selection-model inference is
run, creates a balanced twelve-task selection split, and qualifies only the
project-authored buggy baselines and gold repairs through the already-qualified
Docker evaluator.

Candidate outputs are deliberately absent from this module.  Once a target run
of ``run_selection_pack_qualification`` is accepted and its pack/report digests
are frozen, task contents and evaluator material must not be changed in response
to selection outcomes.
"""
from __future__ import annotations

import argparse
import difflib
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from .artifacts import EvaluationRecord
from .content_store import FileContentStore
from .grading import (
    BlackBoxEvaluationPlan,
    ComparisonMode,
    ProtectedCase,
    protected_expectation_set_sha256,
    protected_input_set_sha256,
)
from .local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository import snapshot_directory
from .repository_surgery import (
    MutationKind,
    PatchFormat,
    RepositorySurgeryGenerationRecord,
    RepositorySurgerySubmission,
    build_visible_repository_surgery_task,
)
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric
from .sandbox import SandboxLimits
from .tasks import ProtectedEvaluatorSpec, SolverVisibleTask, TaskSplit

SELECTION_PACK_SCHEMA = "plural-cognition-repository-surgery-selection-pack-v1"
SELECTION_QUALIFICATION_SCHEMA = "plural-cognition-repository-surgery-selection-qualification-v1"
SELECTION_EVALUATOR_ID = "repository-surgery-selection-exact-stdout-v1"
SELECTION_COMMAND = ("/usr/local/bin/python3", "app.py")
SELECTION_TASK_COUNT = 12
MAX_VISIBLE_BYTES = 65_536


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_json(payload: Any) -> str:
    return sha256(_canonical_json_bytes(payload)).hexdigest()


def _json_line(payload: Any) -> bytes:
    return _canonical_json_bytes(payload) + b"\n"


def _sorted_files(files: tuple[tuple[str, bytes], ...], field: str) -> None:
    paths = tuple(path for path, _ in files)
    if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
        raise ValueError(f"{field} paths must be sorted and unique")
    if any(type(data) is not bytes for _, data in files):
        raise TypeError(f"{field} contents must be bytes")


def _canonical_gold_patch(
    clean_files: tuple[tuple[str, bytes], ...],
    buggy_files: tuple[tuple[str, bytes], ...],
) -> bytes:
    clean = dict(clean_files)
    buggy = dict(buggy_files)
    pieces: list[str] = []
    for path in sorted(clean):
        before = buggy[path].decode("utf-8")
        after = clean[path].decode("utf-8")
        if before == after:
            continue
        pieces.extend(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
                lineterm="",
            )
        )
    if not pieces:
        raise ValueError("selection blueprint contains no repository mutation")
    return ("\n".join(pieces) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class SelectionBlueprint:
    task_id: str
    mutation_kind: MutationKind
    generation_seed: int
    clean_files: tuple[tuple[str, bytes], ...]
    buggy_files: tuple[tuple[str, bytes], ...]
    issue_prompt: bytes
    public_cases: tuple[dict[str, Any], ...]
    protected_cases: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...]
    mutation_configuration: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.task_id.startswith("repository-surgery-selection-"):
            raise ValueError("selection task_id must use the selection namespace")
        if not isinstance(self.mutation_kind, MutationKind):
            raise TypeError("mutation_kind must be MutationKind")
        if type(self.generation_seed) is not int:
            raise TypeError("generation_seed must be int")
        _sorted_files(self.clean_files, "clean_files")
        _sorted_files(self.buggy_files, "buggy_files")
        if tuple(path for path, _ in self.clean_files) != tuple(path for path, _ in self.buggy_files):
            raise ValueError("clean and buggy file sets must have identical paths")
        if self.clean_files == self.buggy_files:
            raise ValueError("selection blueprint must contain a real mutation")
        if type(self.issue_prompt) is not bytes or not self.issue_prompt:
            raise ValueError("issue_prompt must be non-empty bytes")
        case_ids = tuple(case_id for case_id, _, _ in self.protected_cases)
        if case_ids != tuple(sorted(case_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("protected case ids must be sorted and unique")
        if len(case_ids) < 4:
            raise ValueError("selection tasks require at least four protected cases")
        _canonical_gold_patch(self.clean_files, self.buggy_files)

    @property
    def gold_patch(self) -> bytes:
        return _canonical_gold_patch(self.clean_files, self.buggy_files)


@dataclass(frozen=True, slots=True)
class SelectionMaterial:
    blueprint: SelectionBlueprint
    visible_task: SolverVisibleTask
    generation_record: RepositorySurgeryGenerationRecord
    evaluation_plan: BlackBoxEvaluationPlan
    gold_submission: RepositorySurgerySubmission
    limits: SandboxLimits


@dataclass(frozen=True, slots=True)
class SelectionPackEntry:
    task_id: str
    mutation_kind: str
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str

    def canonical_payload(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "mutation_kind": self.mutation_kind,
            "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
        }


@dataclass(frozen=True, slots=True)
class SelectionTaskQualification:
    task_id: str
    baseline_evaluation_sha256: str
    gold_evaluation_sha256: str
    baseline_exact_accuracy: float
    gold_exact_accuracy: float
    baseline_valid_rate: float
    gold_valid_rate: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "baseline_evaluation_sha256": self.baseline_evaluation_sha256,
            "gold_evaluation_sha256": self.gold_evaluation_sha256,
            "baseline_exact_accuracy": self.baseline_exact_accuracy,
            "gold_exact_accuracy": self.gold_exact_accuracy,
            "baseline_valid_rate": self.baseline_valid_rate,
            "gold_valid_rate": self.gold_valid_rate,
        }


@dataclass(frozen=True, slots=True)
class SelectionQualificationReport:
    software_revision: str
    operational_config_freeze_sha256: str
    pack_entries: tuple[SelectionPackEntry, ...]
    qualifications: tuple[SelectionTaskQualification, ...]

    def __post_init__(self) -> None:
        ids = tuple(item.task_id for item in self.pack_entries)
        qids = tuple(item.task_id for item in self.qualifications)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("selection pack entries must be sorted and unique")
        if qids != ids:
            raise ValueError("selection qualifications must exactly bind pack entries")
        if len(ids) != SELECTION_TASK_COUNT:
            raise ValueError("selection pack must contain exactly twelve tasks")
        if self.operational_config_freeze_sha256 != FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256:
            raise ValueError("selection pack operational freeze binding drifted")

    def pack_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_PACK_SCHEMA,
            "operational_config_freeze_sha256": self.operational_config_freeze_sha256,
            "task_count": len(self.pack_entries),
            "tasks": [item.canonical_payload() for item in self.pack_entries],
        }

    @property
    def pack_sha256(self) -> str:
        return _sha256_json(self.pack_payload())

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_QUALIFICATION_SCHEMA,
            "software_revision": self.software_revision,
            "operational_config_freeze_sha256": self.operational_config_freeze_sha256,
            "selection_pack_sha256": self.pack_sha256,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "qualified_docker_source_revision": QUALIFIED_DOCKER.source_revision,
            "qualified_docker_qualification_source_sha256": QUALIFIED_DOCKER.qualification_source_sha256,
            "qualified_docker_engine_sha256": QUALIFIED_DOCKER.engine_qualification_sha256,
            "qualified_docker_image": QUALIFIED_DOCKER.immutable_image,
            "task_count": len(self.pack_entries),
            "tasks": [item.canonical_payload() for item in self.pack_entries],
            "qualifications": [item.canonical_payload() for item in self.qualifications],
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()


def selection_blueprints() -> tuple[SelectionBlueprint, ...]:
    api1_clean = b'''import json\nimport sys\n\ndef invoice_total(amount: int, fee: int) -> int:\n    return amount + fee\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    fee = int(payload.get("fee", 0))\n    result = {"total": invoice_total(int(payload["amount"]), fee)}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    api1_buggy = api1_clean.replace(b'payload.get("fee", 0)', b'payload["fee"]')

    api2_clean = b'''import json\nimport sys\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    total = int(payload["quantity"]) * int(payload["unit_price"])\n    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    api2_buggy = api2_clean.replace(b'{"total": total}', b'{"value": total}')

    boundary1_clean = b'''import json\nimport sys\n\ndef loyalty_total(points: int, subtotal: int) -> int:\n    discount = 8 if points >= 100 else 0\n    return subtotal - discount\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"total": loyalty_total(int(payload["points"]), int(payload["subtotal"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    boundary1_buggy = boundary1_clean.replace(b"points >= 100", b"points > 100")

    boundary2_clean = b'''import json\nimport sys\n\ndef handling_fee(weight: int) -> int:\n    return 4 if weight <= 20 else 9\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"fee": handling_fee(int(payload["weight"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    boundary2_buggy = boundary2_clean.replace(b"weight <= 20", b"weight < 20")

    error1_clean = b'''import json\nimport sys\n\ndef validate_port(port: int) -> int:\n    if port <= 0:\n        raise ValueError("port must be positive")\n    return port\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        result = {"ok": True, "port": validate_port(int(payload["port"]))}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    error1_buggy = error1_clean.replace(b"port <= 0", b"port < 0")

    error2_clean = b'''import json\nimport sys\n\ndef aggregate(values: list[int], mode: str) -> int:\n    if mode == "sum":\n        return sum(values)\n    if mode == "max":\n        return max(values)\n    raise ValueError("unsupported mode")\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        values = [int(value) for value in payload["values"]]\n        result = {"ok": True, "value": aggregate(values, str(payload["mode"]))}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    error2_buggy = error2_clean.replace(
        b'    if mode == "max":\n        return max(values)\n    raise ValueError("unsupported mode")\n',
        b'    return max(values)\n',
    )

    local1_clean = b'''import json\nimport sys\n\ndef reward_points(orders: int, priority: bool) -> int:\n    base = orders * 4\n    return base + (3 if priority else 0)\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"points": reward_points(int(payload["orders"]), bool(payload["priority"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    local1_buggy = local1_clean.replace(b"orders * 4", b"orders * 3")

    local2_clean = b'''import json\nimport sys\n\ndef net_total(subtotal: int, discount: int) -> int:\n    return subtotal - discount\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"net": net_total(int(payload["subtotal"]), int(payload["discount"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    local2_buggy = local2_clean.replace(b"subtotal - discount", b"subtotal + discount")

    multi1_app = b'''import json\nimport sys\nfrom fees import regional_fee\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    total = int(payload["subtotal"]) + regional_fee(str(payload["region"]))\n    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    multi1_fee_clean = b'''def regional_fee(region: str) -> int:\n    return 6 if region == "CA" else 2\n'''
    multi1_fee_buggy = multi1_fee_clean.replace(b"return 6 if", b"return 5 if")

    multi2_app = b'''import json\nimport sys\nfrom normalize import canonical_name\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    sys.stdout.write(json.dumps({"name": canonical_name(str(payload["name"]))}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    multi2_helper_clean = b'''def canonical_name(name: str) -> str:\n    return name.strip().lower()\n'''
    multi2_helper_buggy = multi2_helper_clean.replace(b"name.strip().lower()", b"name.lower()")

    state1_clean = b'''import json\nimport sys\n\nclass Meter:\n    def __init__(self) -> None:\n        self.total = 0\n\n    def record(self, value: int) -> int:\n        self.total += value\n        return self.total\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    meter = Meter()\n    totals = [meter.record(int(value)) for value in payload["values"]]\n    sys.stdout.write(json.dumps({"totals": totals}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    state1_buggy = state1_clean.replace(b"self.total += value", b"self.total = value")

    state2_clean = b'''import json\nimport sys\n\nclass MinimumTracker:\n    def __init__(self) -> None:\n        self.minimum: int | None = None\n\n    def push(self, value: int) -> int:\n        self.minimum = value if self.minimum is None else min(self.minimum, value)\n        return self.minimum\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    tracker = MinimumTracker()\n    minima = [tracker.push(int(value)) for value in payload["values"]]\n    sys.stdout.write(json.dumps({"minima": minima}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    state2_buggy = state2_clean.replace(
        b"self.minimum = value if self.minimum is None else min(self.minimum, value)",
        b"self.minimum = value",
    )

    blueprints = (
        SelectionBlueprint(
            task_id="repository-surgery-selection-api-contract-0001",
            mutation_kind=MutationKind.API_CONTRACT,
            generation_seed=101,
            clean_files=(("app.py", api1_clean),),
            buggy_files=(("app.py", api1_buggy),),
            issue_prompt=b"Fix the invoice JSON API. The fee field is optional and defaults to zero; amount remains required. Preserve the JSON stdin/stdout behavior.\n",
            public_cases=(
                {"input": {"amount": 10, "fee": 3}, "expected": {"total": 13}},
                {"input": {"amount": 0, "fee": 2}, "expected": {"total": 2}},
            ),
            protected_cases=(
                ("case-01-explicit", {"amount": 10, "fee": 3}, {"total": 13}),
                ("case-02-default", {"amount": 11}, {"total": 11}),
                ("case-03-zero", {"amount": 0}, {"total": 0}),
                ("case-04-negative", {"amount": -4, "fee": 1}, {"total": -3}),
            ),
            mutation_configuration={"schema": "selection-api-contract-v1", "field": "fee", "mutation": "optional-to-required"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-api-contract-0002",
            mutation_kind=MutationKind.API_CONTRACT,
            generation_seed=102,
            clean_files=(("app.py", api2_clean),),
            buggy_files=(("app.py", api2_buggy),),
            issue_prompt=b"Fix the checkout response contract. The output object must expose the computed amount under the key 'total'. Preserve the existing required input fields.\n",
            public_cases=(
                {"input": {"quantity": 2, "unit_price": 5}, "expected": {"total": 10}},
            ),
            protected_cases=(
                ("case-01-basic", {"quantity": 2, "unit_price": 5}, {"total": 10}),
                ("case-02-one", {"quantity": 1, "unit_price": 7}, {"total": 7}),
                ("case-03-zero", {"quantity": 0, "unit_price": 9}, {"total": 0}),
                ("case-04-negative", {"quantity": 3, "unit_price": -2}, {"total": -6}),
            ),
            mutation_configuration={"schema": "selection-api-contract-v1", "field": "output-key", "mutation": "total-to-value"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-boundary-0001",
            mutation_kind=MutationKind.BOUNDARY,
            generation_seed=103,
            clean_files=(("app.py", boundary1_clean),),
            buggy_files=(("app.py", boundary1_buggy),),
            issue_prompt=b"Fix the loyalty threshold. Customers receive an 8-unit discount once points reach 100 or more. Preserve all other behavior.\n",
            public_cases=(
                {"input": {"points": 99, "subtotal": 30}, "expected": {"total": 30}},
                {"input": {"points": 101, "subtotal": 30}, "expected": {"total": 22}},
            ),
            protected_cases=(
                ("case-01-below", {"points": 99, "subtotal": 30}, {"total": 30}),
                ("case-02-threshold", {"points": 100, "subtotal": 30}, {"total": 22}),
                ("case-03-above", {"points": 120, "subtotal": 11}, {"total": 3}),
                ("case-04-zero", {"points": 0, "subtotal": 8}, {"total": 8}),
            ),
            mutation_configuration={"schema": "selection-boundary-v1", "symbol": "loyalty_total", "from": ">=", "to": ">", "threshold": 100},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-boundary-0002",
            mutation_kind=MutationKind.BOUNDARY,
            generation_seed=104,
            clean_files=(("app.py", boundary2_clean),),
            buggy_files=(("app.py", boundary2_buggy),),
            issue_prompt=b"Fix handling-fee policy. Packages weighing 20 units or less cost 4; only heavier packages cost 9.\n",
            public_cases=(
                {"input": {"weight": 19}, "expected": {"fee": 4}},
                {"input": {"weight": 21}, "expected": {"fee": 9}},
            ),
            protected_cases=(
                ("case-01-light", {"weight": 1}, {"fee": 4}),
                ("case-02-below", {"weight": 19}, {"fee": 4}),
                ("case-03-threshold", {"weight": 20}, {"fee": 4}),
                ("case-04-above", {"weight": 21}, {"fee": 9}),
            ),
            mutation_configuration={"schema": "selection-boundary-v1", "symbol": "handling_fee", "from": "<=", "to": "<", "threshold": 20},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-error-handling-0001",
            mutation_kind=MutationKind.ERROR_HANDLING,
            generation_seed=105,
            clean_files=(("app.py", error1_clean),),
            buggy_files=(("app.py", error1_buggy),),
            issue_prompt=b"Fix input validation. Port numbers must be strictly positive; zero and negative values must produce the existing invalid-input response.\n",
            public_cases=(
                {"input": {"port": 7}, "expected": {"ok": True, "port": 7}},
                {"input": {"port": -1}, "expected": {"error": "invalid-input", "ok": False}},
            ),
            protected_cases=(
                ("case-01-positive", {"port": 7}, {"ok": True, "port": 7}),
                ("case-02-one", {"port": 1}, {"ok": True, "port": 1}),
                ("case-03-zero", {"port": 0}, {"error": "invalid-input", "ok": False}),
                ("case-04-negative", {"port": -3}, {"error": "invalid-input", "ok": False}),
            ),
            mutation_configuration={"schema": "selection-error-handling-v1", "symbol": "validate_port", "mutation": "zero-accepted"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-error-handling-0002",
            mutation_kind=MutationKind.ERROR_HANDLING,
            generation_seed=106,
            clean_files=(("app.py", error2_clean),),
            buggy_files=(("app.py", error2_buggy),),
            issue_prompt=b"Fix aggregation error handling. Only modes 'sum' and 'max' are supported; every other mode must use the existing invalid-input response.\n",
            public_cases=(
                {"input": {"mode": "sum", "values": [2, 3]}, "expected": {"ok": True, "value": 5}},
                {"input": {"mode": "max", "values": [2, 3]}, "expected": {"ok": True, "value": 3}},
            ),
            protected_cases=(
                ("case-01-sum", {"mode": "sum", "values": [2, 3]}, {"ok": True, "value": 5}),
                ("case-02-max", {"mode": "max", "values": [2, 3]}, {"ok": True, "value": 3}),
                ("case-03-unknown", {"mode": "median", "values": [2, 3]}, {"error": "invalid-input", "ok": False}),
                ("case-04-empty-mode", {"mode": "", "values": [7]}, {"error": "invalid-input", "ok": False}),
            ),
            mutation_configuration={"schema": "selection-error-handling-v1", "symbol": "aggregate", "mutation": "unknown-mode-defaults-to-max"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-local-logic-0001",
            mutation_kind=MutationKind.LOCAL_LOGIC,
            generation_seed=107,
            clean_files=(("app.py", local1_clean),),
            buggy_files=(("app.py", local1_buggy),),
            issue_prompt=b"Fix reward-point calculation. Every order contributes 4 points and priority adds exactly 3 points once.\n",
            public_cases=(
                {"input": {"orders": 1, "priority": False}, "expected": {"points": 4}},
                {"input": {"orders": 2, "priority": True}, "expected": {"points": 11}},
            ),
            protected_cases=(
                ("case-01-one", {"orders": 1, "priority": False}, {"points": 4}),
                ("case-02-priority", {"orders": 2, "priority": True}, {"points": 11}),
                ("case-03-zero", {"orders": 0, "priority": False}, {"points": 0}),
                ("case-04-five", {"orders": 5, "priority": True}, {"points": 23}),
            ),
            mutation_configuration={"schema": "selection-local-logic-v1", "symbol": "reward_points", "from": "multiply-4", "to": "multiply-3"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-local-logic-0002",
            mutation_kind=MutationKind.LOCAL_LOGIC,
            generation_seed=108,
            clean_files=(("app.py", local2_clean),),
            buggy_files=(("app.py", local2_buggy),),
            issue_prompt=b"Fix net-total arithmetic. The discount must be subtracted from subtotal, not added. Preserve the JSON contract.\n",
            public_cases=(
                {"input": {"discount": 3, "subtotal": 20}, "expected": {"net": 17}},
            ),
            protected_cases=(
                ("case-01-basic", {"discount": 3, "subtotal": 20}, {"net": 17}),
                ("case-02-zero", {"discount": 0, "subtotal": 9}, {"net": 9}),
                ("case-03-equal", {"discount": 5, "subtotal": 5}, {"net": 0}),
                ("case-04-large", {"discount": 12, "subtotal": 8}, {"net": -4}),
            ),
            mutation_configuration={"schema": "selection-local-logic-v1", "symbol": "net_total", "from": "subtract", "to": "add"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-multi-file-0001",
            mutation_kind=MutationKind.MULTI_FILE_BEHAVIOR,
            generation_seed=109,
            clean_files=(("app.py", multi1_app), ("fees.py", multi1_fee_clean)),
            buggy_files=(("app.py", multi1_app), ("fees.py", multi1_fee_buggy)),
            issue_prompt=b"Fix regional fees across the repository. CA adds 6 units; every other region adds 2. Keep app.py's JSON interface unchanged.\n",
            public_cases=(
                {"input": {"region": "US", "subtotal": 10}, "expected": {"total": 12}},
            ),
            protected_cases=(
                ("case-01-us", {"region": "US", "subtotal": 10}, {"total": 12}),
                ("case-02-ca", {"region": "CA", "subtotal": 10}, {"total": 16}),
                ("case-03-ca-zero", {"region": "CA", "subtotal": 0}, {"total": 6}),
                ("case-04-other", {"region": "MX", "subtotal": 4}, {"total": 6}),
            ),
            mutation_configuration={"schema": "selection-multi-file-v1", "path": "fees.py", "symbol": "regional_fee", "from": 6, "to": 5},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-multi-file-0002",
            mutation_kind=MutationKind.MULTI_FILE_BEHAVIOR,
            generation_seed=110,
            clean_files=(("app.py", multi2_app), ("normalize.py", multi2_helper_clean)),
            buggy_files=(("app.py", multi2_app), ("normalize.py", multi2_helper_buggy)),
            issue_prompt=b"Fix canonical-name behavior across the repository. Names must have surrounding whitespace removed and then be lowercased. Keep app.py unchanged.\n",
            public_cases=(
                {"input": {"name": "ALICE"}, "expected": {"name": "alice"}},
            ),
            protected_cases=(
                ("case-01-case", {"name": "ALICE"}, {"name": "alice"}),
                ("case-02-leading", {"name": "  Bob"}, {"name": "bob"}),
                ("case-03-trailing", {"name": "Cara  "}, {"name": "cara"}),
                ("case-04-both", {"name": "  DAVE  "}, {"name": "dave"}),
            ),
            mutation_configuration={"schema": "selection-multi-file-v1", "path": "normalize.py", "symbol": "canonical_name", "mutation": "missing-strip"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-state-management-0001",
            mutation_kind=MutationKind.STATE_MANAGEMENT,
            generation_seed=111,
            clean_files=(("app.py", state1_clean),),
            buggy_files=(("app.py", state1_buggy),),
            issue_prompt=b"Fix meter state. Each record call must return the cumulative total including every value seen so far.\n",
            public_cases=(
                {"input": {"values": [4]}, "expected": {"totals": [4]}},
            ),
            protected_cases=(
                ("case-01-single", {"values": [4]}, {"totals": [4]}),
                ("case-02-two", {"values": [4, 3]}, {"totals": [4, 7]}),
                ("case-03-zero", {"values": [5, 0, 2]}, {"totals": [5, 5, 7]}),
                ("case-04-negative", {"values": [5, -2, 1]}, {"totals": [5, 3, 4]}),
            ),
            mutation_configuration={"schema": "selection-state-management-v1", "symbol": "Meter.record", "mutation": "overwrite-instead-of-accumulate"},
        ),
        SelectionBlueprint(
            task_id="repository-surgery-selection-state-management-0002",
            mutation_kind=MutationKind.STATE_MANAGEMENT,
            generation_seed=112,
            clean_files=(("app.py", state2_clean),),
            buggy_files=(("app.py", state2_buggy),),
            issue_prompt=b"Fix running-minimum state. Each push must return the smallest value observed at or before that call.\n",
            public_cases=(
                {"input": {"values": [5, 3]}, "expected": {"minima": [5, 3]}},
            ),
            protected_cases=(
                ("case-01-decreasing", {"values": [5, 3]}, {"minima": [5, 3]}),
                ("case-02-rise", {"values": [5, 3, 4]}, {"minima": [5, 3, 3]}),
                ("case-03-negative", {"values": [2, -1, 7]}, {"minima": [2, -1, -1]}),
                ("case-04-repeat", {"values": [4, 4, 6]}, {"minima": [4, 4, 4]}),
            ),
            mutation_configuration={"schema": "selection-state-management-v1", "symbol": "MinimumTracker.push", "mutation": "overwrite-running-minimum"},
        ),
    )
    ids = tuple(item.task_id for item in blueprints)
    if ids != tuple(sorted(ids)):
        raise AssertionError("selection blueprints must be sorted by task_id")
    if len(ids) != SELECTION_TASK_COUNT:
        raise AssertionError("selection blueprint count drifted")
    counts: dict[MutationKind, int] = {}
    for item in blueprints:
        counts[item.mutation_kind] = counts.get(item.mutation_kind, 0) + 1
    expected = {
        MutationKind.API_CONTRACT,
        MutationKind.BOUNDARY,
        MutationKind.ERROR_HANDLING,
        MutationKind.LOCAL_LOGIC,
        MutationKind.MULTI_FILE_BEHAVIOR,
        MutationKind.STATE_MANAGEMENT,
    }
    if set(counts) != expected or any(counts[kind] != 2 for kind in expected):
        raise AssertionError("selection pack must contain two tasks in each frozen defect class")
    return blueprints


def _write_tree(root: Path, files: tuple[tuple[str, bytes], ...]) -> None:
    root.mkdir(parents=True)
    for relative, data in files:
        destination = root.joinpath(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def build_selection_material(
    *,
    blueprint: SelectionBlueprint,
    store: FileContentStore,
    work_root: Path,
    software_revision: str,
) -> SelectionMaterial:
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    if any(work_root.iterdir()):
        raise ValueError("selection task work_root must be empty")

    clean_root = work_root / "clean"
    buggy_root = work_root / "buggy"
    _write_tree(clean_root, blueprint.clean_files)
    _write_tree(buggy_root, blueprint.buggy_files)
    clean_repository = snapshot_directory(clean_root, store)
    buggy_repository = snapshot_directory(buggy_root, store)
    if clean_repository.manifest_sha256 == buggy_repository.manifest_sha256:
        raise AssertionError("selection mutation did not change repository identity")

    prompt_sha256 = store.put_bytes(blueprint.issue_prompt)
    public_tests_sha256 = store.put_bytes(
        _canonical_json_bytes({"schema": "repository-surgery-selection-public-cases-v1", "cases": blueprint.public_cases})
    )
    visible_task = build_visible_repository_surgery_task(
        task_id=blueprint.task_id,
        split=TaskSplit.SELECTION,
        buggy_repository_sha256=buggy_repository.manifest_sha256,
        issue_prompt_sha256=prompt_sha256,
        public_tests_sha256=public_tests_sha256,
        max_visible_bytes=MAX_VISIBLE_BYTES,
    )

    cases = tuple(
        ProtectedCase(
            case_id=case_id,
            runtime_input_sha256=store.put_bytes(_json_line(input_payload)),
            expected_output_sha256=store.put_bytes(_json_line(expected_payload)),
        )
        for case_id, input_payload, expected_payload in blueprint.protected_cases
    )
    evaluator_configuration_sha256 = _sha256_json(
        {
            "schema": "repository-surgery-selection-exact-stdout-evaluator-v1",
            "comparison_mode": ComparisonMode.EXACT_BYTES.value,
            "command_argv": SELECTION_COMMAND,
            "pass_threshold": 1.0,
        }
    )
    evaluator = ProtectedEvaluatorSpec(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        evaluator_id=SELECTION_EVALUATOR_ID,
        evaluator_configuration_sha256=evaluator_configuration_sha256,
        evaluator_software_revision=software_revision,
        protected_inputs_sha256=protected_input_set_sha256(cases),
        protected_expectations_sha256=protected_expectation_set_sha256(cases),
        primary_metric="exact_accuracy",
        pass_threshold=1.0,
    )
    plan = BlackBoxEvaluationPlan(task=visible_task.task, evaluator=evaluator, cases=cases)

    gold_patch = blueprint.gold_patch
    gold_patch_sha256 = store.put_bytes(gold_patch)
    producer_artifact_sha256 = store.put_bytes(
        _canonical_json_bytes({"schema": "project-authored-selection-pack-gold-v1", "task_id": blueprint.task_id})
    )
    gold_submission = RepositorySurgerySubmission(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        producer_artifact_sha256=producer_artifact_sha256,
        patch_sha256=gold_patch_sha256,
        patch_format=PatchFormat.UNIFIED_DIFF,
        patch_size_bytes=len(gold_patch),
    )
    if store.put_bytes(gold_submission.canonical_bytes()) != gold_submission.sha256:
        raise AssertionError("selection gold submission storage identity mismatch")

    generation = RepositorySurgeryGenerationRecord(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        split=TaskSplit.SELECTION,
        generation_seed=blueprint.generation_seed,
        mutation_kind=blueprint.mutation_kind,
        mutation_configuration_sha256=_sha256_json(blueprint.mutation_configuration),
        generator_software_revision=software_revision,
        clean_repository_sha256=clean_repository.manifest_sha256,
        buggy_repository_sha256=buggy_repository.manifest_sha256,
        issue_prompt_sha256=prompt_sha256,
        public_tests_sha256=public_tests_sha256,
        protected_inputs_sha256=evaluator.protected_inputs_sha256,
        protected_expectations_sha256=evaluator.protected_expectations_sha256,
        gold_patch_sha256=gold_patch_sha256,
    )
    if not generation.binds(visible_task):
        raise AssertionError("selection generation record does not bind visible task")

    return SelectionMaterial(
        blueprint=blueprint,
        visible_task=visible_task,
        generation_record=generation,
        evaluation_plan=plan,
        gold_submission=gold_submission,
        limits=SandboxLimits(
            wall_time_ms=2_000,
            cpu_time_ms=1_000,
            memory_bytes=67_108_864,
            writable_bytes=1_048_576,
            process_count=8,
            stdout_bytes=4_096,
            stderr_bytes=4_096,
        ),
    )


def build_selection_pack_entries(
    *, artifact_root: Path, software_revision: str
) -> tuple[SelectionPackEntry, ...]:
    root = Path(artifact_root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("artifact_root must be absent or empty")
    root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(root / "store")
    build_root = root / "build"
    build_root.mkdir()
    entries: list[SelectionPackEntry] = []
    for blueprint in selection_blueprints():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        entries.append(
            SelectionPackEntry(
                task_id=blueprint.task_id,
                mutation_kind=blueprint.mutation_kind.value,
                task_sha256=material.visible_task.sha256,
                generation_record_sha256=material.generation_record.sha256,
                evaluation_plan_sha256=material.evaluation_plan.sha256,
            )
        )
    return tuple(entries)


def run_selection_pack_qualification(
    *, artifact_root: Path, software_revision: str, docker_executable: str = "docker"
) -> SelectionQualificationReport:
    artifact_root = Path(artifact_root)
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("artifact_root must be absent or empty")
    artifact_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    empty_patch_sha256 = store.put_bytes(b"")
    entries: list[SelectionPackEntry] = []
    qualifications: list[SelectionTaskQualification] = []
    for blueprint in selection_blueprints():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        entries.append(
            SelectionPackEntry(
                task_id=blueprint.task_id,
                mutation_kind=blueprint.mutation_kind.value,
                task_sha256=material.visible_task.sha256,
                generation_record_sha256=material.generation_record.sha256,
                evaluation_plan_sha256=material.evaluation_plan.sha256,
            )
        )
        baseline_submission_sha256 = store.put_bytes(
            _canonical_json_bytes({"schema": "project-authored-selection-pack-baseline-v1", "task_id": blueprint.task_id})
        )
        baseline: EvaluationRecord = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=empty_patch_sha256,
            submission_sha256=baseline_submission_sha256,
            artifact_sha256=baseline_submission_sha256,
            docker_executable=docker_executable,
        )
        gold: EvaluationRecord = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=material.gold_submission.patch_sha256,
            submission_sha256=material.gold_submission.sha256,
            artifact_sha256=material.gold_submission.sha256,
            docker_executable=docker_executable,
        )
        baseline_accuracy = _metric(baseline, "exact_accuracy")
        gold_accuracy = _metric(gold, "exact_accuracy")
        baseline_valid = _metric(baseline, "valid_rate")
        gold_valid = _metric(gold, "valid_rate")
        if baseline.qualified is not False or baseline_accuracy >= 1.0:
            raise RuntimeError(f"{blueprint.task_id}: selection mutation is not observably defective")
        if gold.qualified is not True or gold_accuracy != 1.0 or gold_valid != 1.0:
            raise RuntimeError(f"{blueprint.task_id}: selection gold repair did not fully restore behavior")
        qualifications.append(
            SelectionTaskQualification(
                task_id=blueprint.task_id,
                baseline_evaluation_sha256=baseline.sha256,
                gold_evaluation_sha256=gold.sha256,
                baseline_exact_accuracy=baseline_accuracy,
                gold_exact_accuracy=gold_accuracy,
                baseline_valid_rate=baseline_valid,
                gold_valid_rate=gold_valid,
            )
        )

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("selection qualification left staging residue")

    report = SelectionQualificationReport(
        software_revision=software_revision,
        operational_config_freeze_sha256=FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        pack_entries=tuple(entries),
        qualifications=tuple(qualifications),
    )
    (artifact_root / "selection-pack.json").write_bytes(_canonical_json_bytes(report.pack_payload()))
    (artifact_root / "selection-qualification.json").write_bytes(report.canonical_bytes)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and qualify the untouched Repository Surgery selection pack through qualified Docker."
    )
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    report = run_selection_pack_qualification(
        artifact_root=args.artifact_root,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print("status=SELECTION_PACK_QUALIFIED")
    print(f"selection_pack_sha256={report.pack_sha256}")
    print(f"qualification_report_sha256={report.sha256}")
    print(f"operational_config_freeze_sha256={report.operational_config_freeze_sha256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_count={len(report.pack_entries)}")
    for entry, qualification in zip(report.pack_entries, report.qualifications, strict=True):
        print(
            f"task={entry.task_id} kind={entry.mutation_kind} "
            f"baseline={qualification.baseline_exact_accuracy:.6f} "
            f"gold={qualification.gold_exact_accuracy:.6f} "
            f"baseline_valid={qualification.baseline_valid_rate:.6f} "
            f"gold_valid={qualification.gold_valid_rate:.6f}"
        )
    print(f"pack_output={args.artifact_root / 'selection-pack.json'}")
    print(f"qualification_output={args.artifact_root / 'selection-qualification.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
