"""Fresh untouched twelve-task Repository Surgery selection pack for candidate-pool v3.

The exact four-member V3 development population is frozen before this module
exists. This module authors a balanced twelve-task selection split, proves
freshness against all consumed calibration/selection blueprints available in the
repository, and deterministically qualifies only project-authored baselines and
gold repairs through qualified Docker.

No candidate model is invoked here and no selection outcome is observed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v3_expansion_calibration_outcome_freeze import (
    EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3,
    V3_FROZEN_POPULATION_CANDIDATE_IDS,
    validate_candidate_pool_v3_expansion_calibration_outcome_freeze,
)
from .candidate_pool_v3_full_file import (
    OUTPUT_CONTRACT_V3,
    extract_full_file_patch_v3,
    gold_full_file_output_v3,
    solver_prompt_transport_v3,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_SELECTION_MIN_VALID_RATE,
    V3_SELECTION_POPULATION_SIZE,
)
from .content_store import FileContentStore
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository_surgery import MutationKind
from .repository_surgery_calibration_matrix import (
    _evaluate_patch,
    _metric,
    calibration_blueprints,
)
from .repository_surgery_calibration_pack_v3_repair import (
    repaired_calibration_blueprints_v3,
)
from .repository_surgery_selection_pack_v1 import (
    SelectionBlueprint,
    build_selection_material,
    selection_blueprints as selection_blueprints_v1,
)
from .repository_surgery_selection_pack_v2 import selection_blueprints_v2

SELECTION_PACK_SCHEMA_V3 = "plural-cognition-repository-surgery-selection-pack-v3"
SELECTION_QUALIFICATION_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-selection-qualification-v3"
)
SELECTION_TASK_COUNT_V3 = 12
SELECTION_GENERATION_SEEDS_V3 = tuple(range(401, 413))
SELECTION_QUALIFICATION_ARTIFACT_ROOT_V3 = "artifacts/capable-collective/s3q"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _src(text: str) -> bytes:
    return text.encode("utf-8")


def _blueprint(
    *,
    task_id: str,
    kind: MutationKind,
    seed: int,
    clean_files: tuple[tuple[str, bytes], ...],
    buggy_files: tuple[tuple[str, bytes], ...],
    issue: str,
    public: tuple[dict[str, Any], ...],
    protected: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...],
    mutation: dict[str, Any],
) -> SelectionBlueprint:
    return SelectionBlueprint(
        task_id=task_id,
        mutation_kind=kind,
        generation_seed=seed,
        clean_files=tuple(sorted(clean_files)),
        buggy_files=tuple(sorted(buggy_files)),
        issue_prompt=issue.encode("utf-8") + b"\n",
        public_cases=public,
        protected_cases=protected,
        mutation_configuration=mutation,
    )


def selection_blueprints_v3() -> tuple[SelectionBlueprint, ...]:
    api1_clean = _src('''import json
import sys

def checkout_total(subtotal: int, tip: int) -> int:
    return subtotal + tip

def main() -> None:
    payload = json.loads(sys.stdin.read())
    tip = int(payload.get("tip", 0))
    result = {"total": checkout_total(int(payload["subtotal"]), tip)}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    api1_buggy = api1_clean.replace(b'payload.get("tip", 0)', b'payload["tip"]')

    api2_clean = _src('''import json
import sys

def main() -> None:
    payload = json.loads(sys.stdin.read())
    balance = int(payload["credits"]) - int(payload["debits"])
    result = {"balance": balance}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    api2_buggy = api2_clean.replace(b'{"balance": balance}', b'{"amount": balance}')

    boundary1_clean = _src('''import json
import sys

def support_fee(score: int) -> int:
    return 0 if score >= 80 else 5

def main() -> None:
    payload = json.loads(sys.stdin.read())
    result = {"fee": support_fee(int(payload["score"]))}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    boundary1_buggy = boundary1_clean.replace(b"score >= 80", b"score > 80")

    boundary2_clean = _src('''import json
import sys

def lane_cost(lane: int) -> int:
    return 3 if lane <= 5 else 8

def main() -> None:
    payload = json.loads(sys.stdin.read())
    result = {"cost": lane_cost(int(payload["lane"]))}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    boundary2_buggy = boundary2_clean.replace(b"lane <= 5", b"lane < 5")

    error1_clean = _src('''import json
import sys

def retry_limit(value: int) -> int:
    if value < 1:
        raise ValueError("retry limit must be positive")
    return value

def main() -> None:
    payload = json.loads(sys.stdin.read())
    try:
        result = {"limit": retry_limit(int(payload["limit"])), "ok": True}
    except (KeyError, TypeError, ValueError):
        result = {"error": "invalid-input", "ok": False}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    error1_buggy = error1_clean.replace(b"value < 1", b"value < 0")

    error2_clean = _src('''import json
import sys

def summarize(values: list[int], mode: str) -> int:
    if mode == "count":
        return len(values)
    if mode == "mean":
        if not values:
            raise ValueError("mean requires values")
        return sum(values) // len(values)
    raise ValueError("unsupported mode")

def main() -> None:
    payload = json.loads(sys.stdin.read())
    try:
        values = [int(value) for value in payload["values"]]
        result = {"ok": True, "value": summarize(values, str(payload["mode"]))}
    except (KeyError, TypeError, ValueError):
        result = {"error": "invalid-input", "ok": False}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    error2_buggy = error2_clean.replace(
        b'    raise ValueError("unsupported mode")\n',
        b'    return len(values)\n',
        1,
    )

    local1_clean = _src('''import json
import sys

def loyalty_points(items: int, member: bool) -> int:
    return items * 7 + (1 if member else 0)

def main() -> None:
    payload = json.loads(sys.stdin.read())
    result = {"points": loyalty_points(int(payload["items"]), bool(payload["member"]))}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    local1_buggy = local1_clean.replace(b"items * 7", b"items * 6")

    local2_clean = _src('''import json
import sys

def cash_balance(opening: int, withdrawal: int) -> int:
    return opening - withdrawal

def main() -> None:
    payload = json.loads(sys.stdin.read())
    result = {"balance": cash_balance(int(payload["opening"]), int(payload["withdrawal"]))}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    local2_buggy = local2_clean.replace(b"opening - withdrawal", b"opening + withdrawal")

    multi1_app_clean = _src('''import json
import sys
from rules import region_credit

def main() -> None:
    payload = json.loads(sys.stdin.read())
    total = int(payload["subtotal"]) - region_credit(str(payload["region"]))
    result = {"total": total}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    multi1_rules_clean = _src('''def region_credit(region: str) -> int:
    return 9 if region == "EAST" else 4
''')
    multi1_app_buggy = multi1_app_clean.replace(
        b' - region_credit(str(payload["region"]))',
        b' + region_credit(str(payload["region"]))',
    )
    multi1_rules_buggy = multi1_rules_clean.replace(b"return 9 if", b"return 8 if")

    multi2_app_clean = _src('''import json
import sys
from labels import canonical_label

def main() -> None:
    payload = json.loads(sys.stdin.read())
    label = canonical_label(str(payload["label"]))
    result = {"label": label}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    multi2_labels_clean = _src('''def canonical_label(value: str) -> str:
    return value.strip().lower()
''')
    multi2_app_buggy = multi2_app_clean.replace(b'{"label": label}', b'{"value": label}')
    multi2_labels_buggy = multi2_labels_clean.replace(
        b"value.strip().lower()", b"value.lower()"
    )

    state1_clean = _src('''import json
import sys

class Inventory:
    def __init__(self, opening: int) -> None:
        self.remaining = opening

    def ship(self, units: int) -> int:
        self.remaining -= units
        return self.remaining

def main() -> None:
    payload = json.loads(sys.stdin.read())
    inventory = Inventory(int(payload["opening"]))
    remaining = [inventory.ship(int(value)) for value in payload["shipments"]]
    result = {"remaining": remaining}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    state1_buggy = state1_clean.replace(
        b"self.remaining -= units", b"self.remaining = -units"
    )

    state2_clean = _src('''import json
import sys

class MinimumTracker:
    def __init__(self) -> None:
        self.minimum: int | None = None

    def push(self, value: int) -> int:
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        return self.minimum

def main() -> None:
    payload = json.loads(sys.stdin.read())
    tracker = MinimumTracker()
    minima = [tracker.push(int(value)) for value in payload["values"]]
    result = {"minima": minima}
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")

if __name__ == "__main__":
    main()
''')
    state2_buggy = state2_clean.replace(
        b"self.minimum = value if self.minimum is None else min(self.minimum, value)",
        b"self.minimum = value",
    )

    blueprints = (
        _blueprint(
            task_id="repository-surgery-selection-v3-api-contract-0001",
            kind=MutationKind.API_CONTRACT,
            seed=401,
            clean_files=(("app.py", api1_clean),),
            buggy_files=(("app.py", api1_buggy),),
            issue="Fix the checkout JSON API. tip is optional and defaults to zero; subtotal remains required.",
            public=({"input": {"subtotal": 20, "tip": 2}, "expected": {"total": 22}},),
            protected=(
                ("case-01-explicit", {"subtotal": 20, "tip": 2}, {"total": 22}),
                ("case-02-default", {"subtotal": 20}, {"total": 20}),
                ("case-03-zero", {"subtotal": 0}, {"total": 0}),
                ("case-04-negative-tip", {"subtotal": 8, "tip": -1}, {"total": 7}),
            ),
            mutation={"schema": "selection-v3-api-contract", "mutation": "optional-to-required", "field": "tip"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-api-contract-0002",
            kind=MutationKind.API_CONTRACT,
            seed=402,
            clean_files=(("app.py", api2_clean),),
            buggy_files=(("app.py", api2_buggy),),
            issue="Fix the ledger response contract. The computed result must be returned under the key 'balance'.",
            public=({"input": {"credits": 14, "debits": 5}, "expected": {"balance": 9}},),
            protected=(
                ("case-01-basic", {"credits": 14, "debits": 5}, {"balance": 9}),
                ("case-02-equal", {"credits": 7, "debits": 7}, {"balance": 0}),
                ("case-03-negative", {"credits": 3, "debits": 8}, {"balance": -5}),
                ("case-04-zero", {"credits": 0, "debits": 0}, {"balance": 0}),
            ),
            mutation={"schema": "selection-v3-api-contract", "mutation": "wrong-output-key", "field": "balance"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-boundary-0001",
            kind=MutationKind.BOUNDARY,
            seed=403,
            clean_files=(("app.py", boundary1_clean),),
            buggy_files=(("app.py", boundary1_buggy),),
            issue="Fix support pricing. Scores of 80 or more have zero fee; lower scores cost 5.",
            public=(
                {"input": {"score": 79}, "expected": {"fee": 5}},
                {"input": {"score": 81}, "expected": {"fee": 0}},
            ),
            protected=(
                ("case-01-below", {"score": 79}, {"fee": 5}),
                ("case-02-threshold", {"score": 80}, {"fee": 0}),
                ("case-03-above", {"score": 95}, {"fee": 0}),
                ("case-04-zero", {"score": 0}, {"fee": 5}),
            ),
            mutation={"schema": "selection-v3-boundary", "from": ">=", "to": ">", "threshold": 80},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-boundary-0002",
            kind=MutationKind.BOUNDARY,
            seed=404,
            clean_files=(("app.py", boundary2_clean),),
            buggy_files=(("app.py", boundary2_buggy),),
            issue="Fix lane pricing. Lanes 1 through 5 cost 3; only later lanes cost 8.",
            public=(
                {"input": {"lane": 4}, "expected": {"cost": 3}},
                {"input": {"lane": 6}, "expected": {"cost": 8}},
            ),
            protected=(
                ("case-01-first", {"lane": 1}, {"cost": 3}),
                ("case-02-middle", {"lane": 4}, {"cost": 3}),
                ("case-03-threshold", {"lane": 5}, {"cost": 3}),
                ("case-04-after", {"lane": 6}, {"cost": 8}),
            ),
            mutation={"schema": "selection-v3-boundary", "from": "<=", "to": "<", "threshold": 5},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-error-handling-0001",
            kind=MutationKind.ERROR_HANDLING,
            seed=405,
            clean_files=(("app.py", error1_clean),),
            buggy_files=(("app.py", error1_buggy),),
            issue="Fix retry-limit validation. Zero and negative limits are invalid and must return the existing invalid-input response.",
            public=({"input": {"limit": 2}, "expected": {"limit": 2, "ok": True}},),
            protected=(
                ("case-01-positive", {"limit": 2}, {"limit": 2, "ok": True}),
                ("case-02-one", {"limit": 1}, {"limit": 1, "ok": True}),
                ("case-03-zero", {"limit": 0}, {"error": "invalid-input", "ok": False}),
                ("case-04-negative", {"limit": -3}, {"error": "invalid-input", "ok": False}),
            ),
            mutation={"schema": "selection-v3-error-handling", "mutation": "invalid-zero-accepted", "field": "limit"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-error-handling-0002",
            kind=MutationKind.ERROR_HANDLING,
            seed=406,
            clean_files=(("app.py", error2_clean),),
            buggy_files=(("app.py", error2_buggy),),
            issue="Fix summary-mode validation. Only 'count' and 'mean' are supported; any other mode must return the existing invalid-input response.",
            public=({"input": {"values": [3, 5, 7], "mode": "count"}, "expected": {"ok": True, "value": 3}},),
            protected=(
                ("case-01-count", {"values": [3, 5, 7], "mode": "count"}, {"ok": True, "value": 3}),
                ("case-02-mean", {"values": [3, 5, 7], "mode": "mean"}, {"ok": True, "value": 5}),
                ("case-03-unsupported", {"values": [3, 5, 7], "mode": "median"}, {"error": "invalid-input", "ok": False}),
                ("case-04-empty-mean", {"values": [], "mode": "mean"}, {"error": "invalid-input", "ok": False}),
            ),
            mutation={"schema": "selection-v3-error-handling", "mutation": "unsupported-mode-fallback", "fallback": "count"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-local-logic-0001",
            kind=MutationKind.LOCAL_LOGIC,
            seed=407,
            clean_files=(("app.py", local1_clean),),
            buggy_files=(("app.py", local1_buggy),),
            issue="Fix loyalty points. Each item contributes 7 points, plus one extra point for members.",
            public=({"input": {"items": 2, "member": False}, "expected": {"points": 14}},),
            protected=(
                ("case-01-basic", {"items": 2, "member": False}, {"points": 14}),
                ("case-02-member", {"items": 2, "member": True}, {"points": 15}),
                ("case-03-zero", {"items": 0, "member": False}, {"points": 0}),
                ("case-04-zero-member", {"items": 0, "member": True}, {"points": 1}),
            ),
            mutation={"schema": "selection-v3-local-logic", "mutation": "wrong-multiplier", "from": 7, "to": 6},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-local-logic-0002",
            kind=MutationKind.LOCAL_LOGIC,
            seed=408,
            clean_files=(("app.py", local2_clean),),
            buggy_files=(("app.py", local2_buggy),),
            issue="Fix cash balance calculation. A withdrawal reduces the opening balance.",
            public=({"input": {"opening": 20, "withdrawal": 6}, "expected": {"balance": 14}},),
            protected=(
                ("case-01-basic", {"opening": 20, "withdrawal": 6}, {"balance": 14}),
                ("case-02-zero-withdrawal", {"opening": 20, "withdrawal": 0}, {"balance": 20}),
                ("case-03-equal", {"opening": 9, "withdrawal": 9}, {"balance": 0}),
                ("case-04-overdraw", {"opening": 4, "withdrawal": 7}, {"balance": -3}),
            ),
            mutation={"schema": "selection-v3-local-logic", "mutation": "wrong-arithmetic-operator", "from": "-", "to": "+"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-multi-file-0001",
            kind=MutationKind.MULTI_FILE_BEHAVIOR,
            seed=409,
            clean_files=(("app.py", multi1_app_clean), ("rules.py", multi1_rules_clean)),
            buggy_files=(("app.py", multi1_app_buggy), ("rules.py", multi1_rules_buggy)),
            issue="Fix regional credits. Credits reduce the subtotal, and EAST receives a credit of 9 while other regions receive 4.",
            public=({"input": {"subtotal": 30, "region": "EAST"}, "expected": {"total": 21}},),
            protected=(
                ("case-01-east", {"subtotal": 30, "region": "EAST"}, {"total": 21}),
                ("case-02-west", {"subtotal": 30, "region": "WEST"}, {"total": 26}),
                ("case-03-east-small", {"subtotal": 9, "region": "EAST"}, {"total": 0}),
                ("case-04-other", {"subtotal": 4, "region": "OTHER"}, {"total": 0}),
            ),
            mutation={"schema": "selection-v3-multi-file", "mutation": "cross-file-sign-and-constant", "files": ["app.py", "rules.py"]},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-multi-file-0002",
            kind=MutationKind.MULTI_FILE_BEHAVIOR,
            seed=410,
            clean_files=(("app.py", multi2_app_clean), ("labels.py", multi2_labels_clean)),
            buggy_files=(("app.py", multi2_app_buggy), ("labels.py", multi2_labels_buggy)),
            issue="Fix label normalization. Return the normalized value under 'label', trimming surrounding whitespace and lowercasing it.",
            public=({"input": {"label": "  AbC  "}, "expected": {"label": "abc"}},),
            protected=(
                ("case-01-spaces", {"label": "  AbC  "}, {"label": "abc"}),
                ("case-02-upper", {"label": "XYZ"}, {"label": "xyz"}),
                ("case-03-lower", {"label": "ready"}, {"label": "ready"}),
                ("case-04-tabs", {"label": "\tMiXeD\t"}, {"label": "mixed"}),
            ),
            mutation={"schema": "selection-v3-multi-file", "mutation": "cross-file-key-and-normalization", "files": ["app.py", "labels.py"]},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-state-management-0001",
            kind=MutationKind.STATE_MANAGEMENT,
            seed=411,
            clean_files=(("app.py", state1_clean),),
            buggy_files=(("app.py", state1_buggy),),
            issue="Fix inventory state. Each shipment must subtract from the current remaining inventory, preserving prior shipments.",
            public=({"input": {"opening": 20, "shipments": [3, 4]}, "expected": {"remaining": [17, 13]}},),
            protected=(
                ("case-01-two", {"opening": 20, "shipments": [3, 4]}, {"remaining": [17, 13]}),
                ("case-02-one", {"opening": 10, "shipments": [2]}, {"remaining": [8]}),
                ("case-03-zero", {"opening": 5, "shipments": [0, 2]}, {"remaining": [5, 3]}),
                ("case-04-empty", {"opening": 6, "shipments": []}, {"remaining": []}),
            ),
            mutation={"schema": "selection-v3-state-management", "mutation": "state-reset-instead-of-update", "field": "remaining"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v3-state-management-0002",
            kind=MutationKind.STATE_MANAGEMENT,
            seed=412,
            clean_files=(("app.py", state2_clean),),
            buggy_files=(("app.py", state2_buggy),),
            issue="Fix minimum tracking. Each emitted value must be the minimum seen so far, not merely the latest input.",
            public=({"input": {"values": [7, 3, 5]}, "expected": {"minima": [7, 3, 3]}},),
            protected=(
                ("case-01-drop-rise", {"values": [7, 3, 5]}, {"minima": [7, 3, 3]}),
                ("case-02-increasing", {"values": [1, 2, 3]}, {"minima": [1, 1, 1]}),
                ("case-03-negative", {"values": [2, -1, 0]}, {"minima": [2, -1, -1]}),
                ("case-04-single", {"values": [4]}, {"minima": [4]}),
            ),
            mutation={"schema": "selection-v3-state-management", "mutation": "latest-instead-of-running-minimum", "field": "minimum"},
        ),
    )
    if tuple(item.task_id for item in blueprints) != tuple(sorted(item.task_id for item in blueprints)):
        raise AssertionError("v3 selection task IDs must be sorted")
    return blueprints


def _content_fingerprint(blueprint: Any) -> str:
    return _canonical_sha256({
        "mutation_kind": blueprint.mutation_kind.value,
        "clean_files": [[path, hashlib.sha256(raw).hexdigest()] for path, raw in blueprint.clean_files],
        "buggy_files": [[path, hashlib.sha256(raw).hexdigest()] for path, raw in blueprint.buggy_files],
        "issue_prompt_sha256": hashlib.sha256(blueprint.issue_prompt).hexdigest(),
        "public_cases": list(blueprint.public_cases),
        "protected_cases": [[case_id, input_payload, expected_payload] for case_id, input_payload, expected_payload in blueprint.protected_cases],
    })


def validate_selection_pack_v3_freshness() -> None:
    validate_candidate_pool_v3_expansion_calibration_outcome_freeze()
    tasks = selection_blueprints_v3()
    if len(tasks) != SELECTION_TASK_COUNT_V3:
        raise AssertionError("v3 selection pack must contain twelve tasks")
    ids = tuple(item.task_id for item in tasks)
    if len(ids) != len(set(ids)):
        raise AssertionError("v3 selection task IDs must be unique")
    seeds = tuple(item.generation_seed for item in tasks)
    if seeds != SELECTION_GENERATION_SEEDS_V3 or len(seeds) != len(set(seeds)):
        raise AssertionError("v3 selection seeds drifted")
    expected_kinds = {
        MutationKind.API_CONTRACT, MutationKind.BOUNDARY, MutationKind.ERROR_HANDLING,
        MutationKind.LOCAL_LOGIC, MutationKind.MULTI_FILE_BEHAVIOR, MutationKind.STATE_MANAGEMENT,
    }
    counts = {kind: 0 for kind in expected_kinds}
    for item in tasks:
        if item.mutation_kind not in counts:
            raise AssertionError("v3 selection pack contains unexpected defect family")
        counts[item.mutation_kind] += 1
    if any(count != 2 for count in counts.values()):
        raise AssertionError("v3 selection pack must contain two tasks per defect family")
    legacy_groups = (
        tuple(calibration_blueprints()), tuple(selection_blueprints_v1()),
        tuple(selection_blueprints_v2()), tuple(repaired_calibration_blueprints_v3()),
    )
    legacy = tuple(item for group in legacy_groups for item in group)
    if set(ids) & {item.task_id for item in legacy}:
        raise AssertionError("v3 selection task IDs overlap consumed task IDs")
    if set(seeds) & {item.generation_seed for item in legacy}:
        raise AssertionError("v3 selection generation seeds overlap consumed seeds")
    old_content = {_content_fingerprint(item) for item in legacy}
    new_content = [_content_fingerprint(item) for item in tasks]
    if len(new_content) != len(set(new_content)):
        raise AssertionError("v3 selection pack contains duplicate task material")
    if set(new_content) & old_content:
        raise AssertionError("v3 selection task material duplicates consumed material")
    if tuple(V3_FROZEN_POPULATION_CANDIDATE_IDS) != (
        "qwen2.5-coder-14b-q5km", "devstral-24b-q4km", "gpt-oss-20b-mxfp4", "qwen3-14b-q5km",
    ):
        raise AssertionError("v3 frozen four-member population drifted")
    if len(V3_FROZEN_POPULATION_CANDIDATE_IDS) != V3_SELECTION_POPULATION_SIZE:
        raise AssertionError("v3 frozen population size drifted")


@dataclass(frozen=True, slots=True)
class SelectionPackEntryV3:
    task_id: str
    mutation_kind: str
    generation_seed: int
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str
    solver_prompt_sha256: str
    gold_output_sha256: str
    gold_patch_sha256: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "mutation_kind": self.mutation_kind,
            "generation_seed": self.generation_seed, "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
            "solver_prompt_sha256": self.solver_prompt_sha256,
            "gold_output_sha256": self.gold_output_sha256,
            "gold_patch_sha256": self.gold_patch_sha256,
        }


@dataclass(frozen=True, slots=True)
class SelectionTaskQualificationV3:
    task_id: str
    baseline_evaluation_sha256: str
    gold_evaluation_sha256: str
    baseline_exact_accuracy: float
    gold_exact_accuracy: float
    baseline_valid_rate: float
    gold_valid_rate: float
    gold_parse_mode: str
    parsed_gold_patch_sha256: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "baseline_evaluation_sha256": self.baseline_evaluation_sha256,
            "gold_evaluation_sha256": self.gold_evaluation_sha256,
            "baseline_exact_accuracy": self.baseline_exact_accuracy,
            "gold_exact_accuracy": self.gold_exact_accuracy,
            "baseline_valid_rate": self.baseline_valid_rate,
            "gold_valid_rate": self.gold_valid_rate,
            "gold_parse_mode": self.gold_parse_mode,
            "parsed_gold_patch_sha256": self.parsed_gold_patch_sha256,
        }


@dataclass(frozen=True, slots=True)
class SelectionQualificationReportV3:
    software_revision: str
    entries: tuple[SelectionPackEntryV3, ...]
    qualifications: tuple[SelectionTaskQualificationV3, ...]

    def __post_init__(self) -> None:
        ids = tuple(item.task_id for item in self.entries)
        qids = tuple(item.task_id for item in self.qualifications)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("v3 selection entries must be sorted and unique")
        if qids != ids or len(ids) != SELECTION_TASK_COUNT_V3:
            raise ValueError("v3 selection qualifications must bind exactly twelve pack entries")

    def pack_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_PACK_SCHEMA_V3,
            "scientific_status": "fresh-untouched-v3-selection-pack-before-selection-inference",
            "predecessor_expansion_calibration_outcome_freeze_sha256": EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "candidate_ids": list(V3_FROZEN_POPULATION_CANDIDATE_IDS),
            "task_count": len(self.entries), "min_valid_rate": V3_SELECTION_MIN_VALID_RATE,
            "population_size": V3_SELECTION_POPULATION_SIZE,
            "tasks": [item.payload() for item in self.entries],
            "selection_outcomes_observed": False,
        }

    @property
    def pack_sha256(self) -> str:
        return _canonical_sha256(self.pack_payload())

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_QUALIFICATION_SCHEMA_V3,
            "scientific_status": "deterministic-v3-selection-pack-qualification-no-model-inference",
            "software_revision": self.software_revision,
            "predecessor_expansion_calibration_outcome_freeze_sha256": EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "selection_pack_sha256": self.pack_sha256,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "candidate_ids": list(V3_FROZEN_POPULATION_CANDIDATE_IDS),
            "task_count": len(self.entries), "tasks": [item.payload() for item in self.entries],
            "qualifications": [item.payload() for item in self.qualifications],
            "candidate_model_inference_performed": False,
            "selection_outcomes_observed": False, "selection_evidence": False,
        }

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.payload())


def run_selection_pack_v3_qualification(
    *, artifact_root: Path, software_revision: str, docker_executable: str = "docker"
) -> SelectionQualificationReportV3:
    validate_selection_pack_v3_freshness()
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision, docker_executable=docker_executable
    )
    empty_patch_sha256 = store.put_bytes(b"")
    entries: list[SelectionPackEntryV3] = []
    qualifications: list[SelectionTaskQualificationV3] = []
    for blueprint in selection_blueprints_v3():
        material = build_selection_material(
            blueprint=blueprint, store=store,
            work_root=build_root / blueprint.task_id, software_revision=software_revision,
        )
        prompt_sha256 = store.put_bytes(solver_prompt_transport_v3(blueprint))
        gold_output = gold_full_file_output_v3(blueprint)
        gold_output_sha256 = store.put_bytes(gold_output)
        parsed_gold_patch, parse_mode = extract_full_file_patch_v3(gold_output, blueprint)
        if parsed_gold_patch != blueprint.gold_patch:
            raise RuntimeError(f"{blueprint.task_id}: v3 gold interpreter changed canonical gold patch")
        parsed_gold_patch_sha256 = store.put_bytes(parsed_gold_patch)
        if parsed_gold_patch_sha256 != material.gold_submission.patch_sha256:
            raise RuntimeError(f"{blueprint.task_id}: parsed v3 gold patch identity drifted")
        entries.append(SelectionPackEntryV3(
            task_id=blueprint.task_id, mutation_kind=blueprint.mutation_kind.value,
            generation_seed=blueprint.generation_seed, task_sha256=material.visible_task.sha256,
            generation_record_sha256=material.generation_record.sha256,
            evaluation_plan_sha256=material.evaluation_plan.sha256,
            solver_prompt_sha256=prompt_sha256, gold_output_sha256=gold_output_sha256,
            gold_patch_sha256=material.gold_submission.patch_sha256,
        ))
        baseline_submission_sha256 = store.put_bytes(_canonical_json_bytes({
            "schema": "project-authored-selection-pack-baseline-v3", "task_id": blueprint.task_id,
        }))
        baseline = _evaluate_patch(
            material=material, configuration=configuration, store=store, staging_root=staging_root,
            patch_sha256=empty_patch_sha256, submission_sha256=baseline_submission_sha256,
            artifact_sha256=baseline_submission_sha256, docker_executable=docker_executable,
        )
        gold = _evaluate_patch(
            material=material, configuration=configuration, store=store, staging_root=staging_root,
            patch_sha256=material.gold_submission.patch_sha256,
            submission_sha256=material.gold_submission.sha256,
            artifact_sha256=material.gold_submission.sha256, docker_executable=docker_executable,
        )
        baseline_accuracy = _metric(baseline, "exact_accuracy")
        gold_accuracy = _metric(gold, "exact_accuracy")
        baseline_valid = _metric(baseline, "valid_rate")
        gold_valid = _metric(gold, "valid_rate")
        if baseline.qualified is not False or baseline_accuracy >= 1.0:
            raise RuntimeError(f"{blueprint.task_id}: mutation is not observably defective")
        if gold.qualified is not True or gold_accuracy != 1.0 or gold_valid != 1.0:
            raise RuntimeError(f"{blueprint.task_id}: gold repair did not fully restore behavior")
        qualifications.append(SelectionTaskQualificationV3(
            task_id=blueprint.task_id, baseline_evaluation_sha256=baseline.sha256,
            gold_evaluation_sha256=gold.sha256, baseline_exact_accuracy=baseline_accuracy,
            gold_exact_accuracy=gold_accuracy, baseline_valid_rate=baseline_valid,
            gold_valid_rate=gold_valid, gold_parse_mode=parse_mode,
            parsed_gold_patch_sha256=parsed_gold_patch_sha256,
        ))
    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("v3 selection qualification left staging residue")
    report = SelectionQualificationReportV3(
        software_revision=software_revision, entries=tuple(entries), qualifications=tuple(qualifications)
    )
    (artifact_root / "selection-pack-v3.json").write_bytes(_canonical_json_bytes(report.pack_payload()) + b"\n")
    (artifact_root / "selection-qualification-v3.json").write_bytes(_canonical_json_bytes(report.payload()) + b"\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and Docker-qualify the fresh untouched v3 selection pack without candidate-model inference.")
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    report = run_selection_pack_v3_qualification(
        artifact_root=args.artifact_root, software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print("status=SELECTION_PACK_V3_QUALIFIED")
    print(f"selection_pack_sha256={report.pack_sha256}")
    print(f"qualification_report_sha256={report.sha256}")
    print("predecessor_expansion_calibration_outcome_freeze_sha256=" + EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3)
    print("representation_protocol_sha256=" + EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256)
    print("candidate_ids=" + ",".join(V3_FROZEN_POPULATION_CANDIDATE_IDS))
    print(f"task_count={len(report.entries)}")
    print("candidate_model_inference_performed=False")
    print("selection_outcomes_observed=False")
    print("selection_evidence=False")
    for entry, qualification in zip(report.entries, report.qualifications, strict=True):
        print(
            f"task={entry.task_id} kind={entry.mutation_kind} seed={entry.generation_seed} "
            f"baseline={qualification.baseline_exact_accuracy:.6f} gold={qualification.gold_exact_accuracy:.6f} "
            f"baseline_valid={qualification.baseline_valid_rate:.6f} gold_valid={qualification.gold_valid_rate:.6f} "
            f"gold_parse_mode={qualification.gold_parse_mode}"
        )
    print(f"pack_output={args.artifact_root / 'selection-pack-v3.json'}")
    print(f"qualification_output={args.artifact_root / 'selection-qualification-v3.json'}")
    return 0


validate_selection_pack_v3_freshness()


if __name__ == "__main__":
    raise SystemExit(main())
