"""Fresh untouched twelve-task Repository Surgery selection pack for candidate-pool v2.

The five-survivor operational configuration is already frozen before this module
exists. This module creates a new balanced selection split with no task-ID overlap
with calibration or the consumed v1 selection pack, and qualifies only project-
authored buggy baselines and gold repairs through qualified Docker. No candidate
model is invoked here and no candidate selection output is imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_operational_freeze import (
    CALIBRATION_SUITE_FILE_SHA256_V2,
    CALIBRATION_SUITE_REPORT_SHA256_V2,
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
    validate_operational_freeze_against_repository,
)
from .candidate_pool_v2_full_file import extract_full_file_patch_v2, gold_full_file_output_v2
from .content_store import FileContentStore
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository_surgery import MutationKind
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric, calibration_blueprints
from .repository_surgery_selection_pack_v1 import (
    SelectionBlueprint,
    build_selection_material,
    selection_blueprints as selection_blueprints_v1,
)

SELECTION_PACK_SCHEMA_V2 = "plural-cognition-repository-surgery-selection-pack-v2"
SELECTION_QUALIFICATION_SCHEMA_V2 = (
    "plural-cognition-repository-surgery-selection-qualification-v2"
)
SELECTION_TASK_COUNT_V2 = 12


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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


def selection_blueprints_v2() -> tuple[SelectionBlueprint, ...]:
    api1_clean = _src('''import json\nimport sys\n\ndef shipping_total(subtotal: int, surcharge: int) -> int:\n    return subtotal + surcharge\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    surcharge = int(payload.get("surcharge", 0))\n    result = {"total": shipping_total(int(payload["subtotal"]), surcharge)}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    api1_buggy = api1_clean.replace(b'payload.get("surcharge", 0)', b'payload["surcharge"]')
    api2_clean = _src('''import json\nimport sys\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    remaining = int(payload["limit"]) - int(payload["used"])\n    sys.stdout.write(json.dumps({"remaining": remaining}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    api2_buggy = api2_clean.replace(b'{"remaining": remaining}', b'{"available": remaining}')

    boundary1_clean = _src('''import json\nimport sys\n\ndef shipping_fee(subtotal: int) -> int:\n    return 0 if subtotal >= 50 else 6\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    sys.stdout.write(json.dumps({"fee": shipping_fee(int(payload["subtotal"]))}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    boundary1_buggy = boundary1_clean.replace(b"subtotal >= 50", b"subtotal > 50")
    boundary2_clean = _src('''import json\nimport sys\n\ndef queue_fee(position: int) -> int:\n    return 2 if position <= 3 else 7\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    sys.stdout.write(json.dumps({"fee": queue_fee(int(payload["position"]))}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    boundary2_buggy = boundary2_clean.replace(b"position <= 3", b"position < 3")

    error1_clean = _src('''import json\nimport sys\n\ndef batch_size(value: int) -> int:\n    if value < 1:\n        raise ValueError("batch size must be positive")\n    return value\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        result = {"batch": batch_size(int(payload["batch"])) , "ok": True}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    error1_buggy = error1_clean.replace(b"value < 1", b"value < 0")
    error2_clean = _src('''import json\nimport sys\n\ndef aggregate(values: list[int], mode: str) -> int:\n    if mode == "min":\n        return min(values)\n    if mode == "sum":\n        return sum(values)\n    raise ValueError("unsupported mode")\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        values = [int(value) for value in payload["values"]]\n        result = {"ok": True, "value": aggregate(values, str(payload["mode"]))}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    error2_buggy = error2_clean.replace(
        b'    if mode == "sum":\n        return sum(values)\n    raise ValueError("unsupported mode")\n',
        b'    return sum(values)\n',
    )

    local1_clean = _src('''import json\nimport sys\n\ndef credits(units: int, premium: bool) -> int:\n    return units * 5 + (2 if premium else 0)\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"credits": credits(int(payload["units"]), bool(payload["premium"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    local1_buggy = local1_clean.replace(b"units * 5", b"units * 4")
    local2_clean = _src('''import json\nimport sys\n\ndef after_tax(gross: int, tax: int) -> int:\n    return gross - tax\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"net": after_tax(int(payload["gross"]), int(payload["tax"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    local2_buggy = local2_clean.replace(b"gross - tax", b"gross + tax")

    multi1_app_clean = _src('''import json\nimport sys\nfrom pricing import regional_discount\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    total = int(payload["subtotal"]) - regional_discount(str(payload["region"]))\n    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    multi1_helper_clean = _src('''def regional_discount(region: str) -> int:\n    return 7 if region == "NW" else 3\n''')
    multi1_app_buggy = multi1_app_clean.replace(b" - regional_discount", b" + regional_discount")
    multi1_helper_buggy = multi1_helper_clean.replace(b"return 7 if", b"return 6 if")

    multi2_app_clean = _src('''import json\nimport sys\nfrom normalize import canonical_sku\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    value = canonical_sku(str(payload["sku"]))\n    sys.stdout.write(json.dumps({"sku": value}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    multi2_helper_clean = _src('''def canonical_sku(value: str) -> str:\n    return value.strip().upper()\n''')
    multi2_app_buggy = multi2_app_clean.replace(b'{"sku": value}', b'{"value": value}')
    multi2_helper_buggy = multi2_helper_clean.replace(b"value.strip().upper()", b"value.upper()")

    state1_clean = _src('''import json\nimport sys\n\nclass RunningTotal:\n    def __init__(self) -> None:\n        self.total = 0\n\n    def add(self, value: int) -> int:\n        self.total += value\n        return self.total\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    counter = RunningTotal()\n    totals = [counter.add(int(value)) for value in payload["values"]]\n    sys.stdout.write(json.dumps({"totals": totals}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    state1_buggy = state1_clean.replace(b"self.total += value", b"self.total = value")
    state2_clean = _src('''import json\nimport sys\n\nclass MaximumTracker:\n    def __init__(self) -> None:\n        self.maximum: int | None = None\n\n    def push(self, value: int) -> int:\n        self.maximum = value if self.maximum is None else max(self.maximum, value)\n        return self.maximum\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    tracker = MaximumTracker()\n    maxima = [tracker.push(int(value)) for value in payload["values"]]\n    sys.stdout.write(json.dumps({"maxima": maxima}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    state2_buggy = state2_clean.replace(
        b"self.maximum = value if self.maximum is None else max(self.maximum, value)",
        b"self.maximum = value",
    )

    blueprints = (
        _blueprint(
            task_id="repository-surgery-selection-v2-api-contract-0001", kind=MutationKind.API_CONTRACT, seed=201,
            clean_files=(("app.py", api1_clean),), buggy_files=(("app.py", api1_buggy),),
            issue="Fix the shipping JSON API. surcharge is optional and defaults to zero; subtotal remains required.",
            public=({"input":{"subtotal":12,"surcharge":3},"expected":{"total":15}},),
            protected=(("case-01-explicit",{"subtotal":12,"surcharge":3},{"total":15}),("case-02-default",{"subtotal":12},{"total":12}),("case-03-zero",{"subtotal":0},{"total":0}),("case-04-negative",{"subtotal":-2,"surcharge":1},{"total":-1})),
            mutation={"schema":"selection-v2-api-contract","mutation":"optional-to-required","field":"surcharge"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-api-contract-0002", kind=MutationKind.API_CONTRACT, seed=202,
            clean_files=(("app.py", api2_clean),), buggy_files=(("app.py", api2_buggy),),
            issue="Fix the quota response contract. The computed value must be returned under the key 'remaining'.",
            public=({"input":{"limit":10,"used":3},"expected":{"remaining":7}},),
            protected=(("case-01-basic",{"limit":10,"used":3},{"remaining":7}),("case-02-equal",{"limit":5,"used":5},{"remaining":0}),("case-03-zero",{"limit":0,"used":0},{"remaining":0}),("case-04-over",{"limit":3,"used":8},{"remaining":-5})),
            mutation={"schema":"selection-v2-api-contract","mutation":"wrong-output-key","field":"remaining"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-boundary-0001", kind=MutationKind.BOUNDARY, seed=203,
            clean_files=(("app.py", boundary1_clean),), buggy_files=(("app.py", boundary1_buggy),),
            issue="Fix free-shipping policy. Subtotals of 50 or more have zero shipping fee; smaller orders cost 6.",
            public=({"input":{"subtotal":49},"expected":{"fee":6}},{"input":{"subtotal":51},"expected":{"fee":0}}),
            protected=(("case-01-below",{"subtotal":49},{"fee":6}),("case-02-threshold",{"subtotal":50},{"fee":0}),("case-03-above",{"subtotal":80},{"fee":0}),("case-04-zero",{"subtotal":0},{"fee":6})),
            mutation={"schema":"selection-v2-boundary","from":">=","to":">","threshold":50},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-boundary-0002", kind=MutationKind.BOUNDARY, seed=204,
            clean_files=(("app.py", boundary2_clean),), buggy_files=(("app.py", boundary2_buggy),),
            issue="Fix queue pricing. Positions 1 through 3 cost 2; only later positions cost 7.",
            public=({"input":{"position":2},"expected":{"fee":2}},{"input":{"position":4},"expected":{"fee":7}}),
            protected=(("case-01-first",{"position":1},{"fee":2}),("case-02-middle",{"position":2},{"fee":2}),("case-03-threshold",{"position":3},{"fee":2}),("case-04-after",{"position":4},{"fee":7})),
            mutation={"schema":"selection-v2-boundary","from":"<=","to":"<","threshold":3},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-error-handling-0001", kind=MutationKind.ERROR_HANDLING, seed=205,
            clean_files=(("app.py", error1_clean),), buggy_files=(("app.py", error1_buggy),),
            issue="Fix batch-size validation. Batch sizes must be strictly positive; zero and negatives use the existing invalid-input response.",
            public=({"input":{"batch":3},"expected":{"batch":3,"ok":True}},{"input":{"batch":-1},"expected":{"error":"invalid-input","ok":False}}),
            protected=(("case-01-positive",{"batch":3},{"batch":3,"ok":True}),("case-02-one",{"batch":1},{"batch":1,"ok":True}),("case-03-zero",{"batch":0},{"error":"invalid-input","ok":False}),("case-04-negative",{"batch":-5},{"error":"invalid-input","ok":False})),
            mutation={"schema":"selection-v2-error-handling","mutation":"zero-accepted"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-error-handling-0002", kind=MutationKind.ERROR_HANDLING, seed=206,
            clean_files=(("app.py", error2_clean),), buggy_files=(("app.py", error2_buggy),),
            issue="Fix aggregation error handling. Only 'min' and 'sum' are supported; every other mode must use the existing invalid-input response.",
            public=({"input":{"mode":"min","values":[4,2]},"expected":{"ok":True,"value":2}},{"input":{"mode":"sum","values":[4,2]},"expected":{"ok":True,"value":6}}),
            protected=(("case-01-min",{"mode":"min","values":[4,2]},{"ok":True,"value":2}),("case-02-sum",{"mode":"sum","values":[4,2]},{"ok":True,"value":6}),("case-03-unknown",{"mode":"max","values":[4,2]},{"error":"invalid-input","ok":False}),("case-04-empty",{"mode":"","values":[1]},{"error":"invalid-input","ok":False})),
            mutation={"schema":"selection-v2-error-handling","mutation":"unknown-mode-defaults-to-sum"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-local-logic-0001", kind=MutationKind.LOCAL_LOGIC, seed=207,
            clean_files=(("app.py", local1_clean),), buggy_files=(("app.py", local1_buggy),),
            issue="Fix credit calculation. Each unit earns 5 credits, plus 2 extra credits for premium accounts.",
            public=({"input":{"units":2,"premium":False},"expected":{"credits":10}},{"input":{"units":2,"premium":True},"expected":{"credits":12}}),
            protected=(("case-01-basic",{"units":2,"premium":False},{"credits":10}),("case-02-premium",{"units":2,"premium":True},{"credits":12}),("case-03-zero",{"units":0,"premium":True},{"credits":2}),("case-04-negative",{"units":-1,"premium":False},{"credits":-5})),
            mutation={"schema":"selection-v2-local-logic","mutation":"wrong-multiplier","expected":5},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-local-logic-0002", kind=MutationKind.LOCAL_LOGIC, seed=208,
            clean_files=(("app.py", local2_clean),), buggy_files=(("app.py", local2_buggy),),
            issue="Fix net amount calculation. Tax is subtracted from gross, not added.",
            public=({"input":{"gross":20,"tax":3},"expected":{"net":17}},),
            protected=(("case-01-basic",{"gross":20,"tax":3},{"net":17}),("case-02-zero-tax",{"gross":20,"tax":0},{"net":20}),("case-03-equal",{"gross":5,"tax":5},{"net":0}),("case-04-negative",{"gross":-2,"tax":1},{"net":-3})),
            mutation={"schema":"selection-v2-local-logic","mutation":"addition-for-subtraction"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-multi-file-0001", kind=MutationKind.MULTI_FILE, seed=209,
            clean_files=(("app.py", multi1_app_clean),("pricing.py", multi1_helper_clean)), buggy_files=(("app.py", multi1_app_buggy),("pricing.py", multi1_helper_buggy)),
            issue="Fix regional discount behavior. The discount is subtracted from subtotal, and region NW receives 7 while all other regions receive 3. Both modules must agree.",
            public=({"input":{"subtotal":20,"region":"NW"},"expected":{"total":13}},{"input":{"subtotal":20,"region":"SE"},"expected":{"total":17}}),
            protected=(("case-01-nw",{"subtotal":20,"region":"NW"},{"total":13}),("case-02-other",{"subtotal":20,"region":"SE"},{"total":17}),("case-03-small",{"subtotal":4,"region":"NW"},{"total":-3}),("case-04-zero",{"subtotal":0,"region":"X"},{"total":-3})),
            mutation={"schema":"selection-v2-multi-file","changed_files":2,"mutation":"sign-and-regional-value"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-multi-file-0002", kind=MutationKind.MULTI_FILE, seed=210,
            clean_files=(("app.py", multi2_app_clean),("normalize.py", multi2_helper_clean)), buggy_files=(("app.py", multi2_app_buggy),("normalize.py", multi2_helper_buggy)),
            issue="Fix SKU normalization across the repository. Trim surrounding whitespace, uppercase the SKU, and expose it under the output key 'sku'.",
            public=({"input":{"sku":" ab-1 "},"expected":{"sku":"AB-1"}},),
            protected=(("case-01-spaces",{"sku":" ab-1 "},{"sku":"AB-1"}),("case-02-clean",{"sku":"xy"},{"sku":"XY"}),("case-03-tabs",{"sku":"\tq7\t"},{"sku":"Q7"}),("case-04-empty",{"sku":"   "},{"sku":""})),
            mutation={"schema":"selection-v2-multi-file","changed_files":2,"mutation":"normalization-and-output-key"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-state-management-0001", kind=MutationKind.STATE_MANAGEMENT, seed=211,
            clean_files=(("app.py", state1_clean),), buggy_files=(("app.py", state1_buggy),),
            issue="Fix the running total. Each add operation must accumulate onto prior state and return the cumulative total.",
            public=({"input":{"values":[2,3]},"expected":{"totals":[2,5]}},),
            protected=(("case-01-two",{"values":[2,3]},{"totals":[2,5]}),("case-02-three",{"values":[1,1,1]},{"totals":[1,2,3]}),("case-03-negative",{"values":[5,-2]},{"totals":[5,3]}),("case-04-zero",{"values":[0,4]},{"totals":[0,4]})),
            mutation={"schema":"selection-v2-state-management","mutation":"reset-instead-of-accumulate"},
        ),
        _blueprint(
            task_id="repository-surgery-selection-v2-state-management-0002", kind=MutationKind.STATE_MANAGEMENT, seed=212,
            clean_files=(("app.py", state2_clean),), buggy_files=(("app.py", state2_buggy),),
            issue="Fix the maximum tracker. It must retain the greatest value observed so far after every push.",
            public=({"input":{"values":[3,1,5]},"expected":{"maxima":[3,3,5]}},),
            protected=(("case-01-mixed",{"values":[3,1,5]},{"maxima":[3,3,5]}),("case-02-descending",{"values":[5,4,3]},{"maxima":[5,5,5]}),("case-03-negative",{"values":[-3,-1,-2]},{"maxima":[-3,-1,-1]}),("case-04-equal",{"values":[2,2]},{"maxima":[2,2]})),
            mutation={"schema":"selection-v2-state-management","mutation":"reset-instead-of-maximum"},
        ),
    )
    if tuple(item.task_id for item in blueprints) != tuple(sorted(item.task_id for item in blueprints)):
        raise AssertionError("v2 selection task IDs must be sorted")
    return blueprints


def validate_selection_pack_v2_freshness() -> None:
    validate_operational_freeze_against_repository()
    tasks = selection_blueprints_v2()
    if len(tasks) != SELECTION_TASK_COUNT_V2:
        raise AssertionError("v2 selection pack must contain twelve tasks")
    ids = {item.task_id for item in tasks}
    if ids.intersection(item.task_id for item in calibration_blueprints()):
        raise AssertionError("v2 selection pack overlaps calibration task IDs")
    if ids.intersection(item.task_id for item in selection_blueprints_v1()):
        raise AssertionError("v2 selection pack overlaps consumed v1 selection task IDs")
    counts = {kind: 0 for kind in MutationKind}
    for item in tasks:
        counts[item.mutation_kind] += 1
    expected = {
        MutationKind.API_CONTRACT,
        MutationKind.BOUNDARY,
        MutationKind.ERROR_HANDLING,
        MutationKind.LOCAL_LOGIC,
        MutationKind.MULTI_FILE,
        MutationKind.STATE_MANAGEMENT,
    }
    if set(kind for kind, count in counts.items() if count) != expected:
        raise AssertionError("v2 selection pack defect-family set drifted")
    if any(counts[kind] != 2 for kind in expected):
        raise AssertionError("v2 selection pack must contain two tasks per defect family")


def build_solver_prompt_selection_v2(blueprint: SelectionBlueprint) -> bytes:
    files: list[str] = []
    for path, raw in blueprint.buggy_files:
        text = raw.decode("utf-8")
        files.append(f"===== FILE: {path} =====\n{text}===== END FILE =====")
    public = json.dumps(list(blueprint.public_cases), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository files, and public examples below. "
        "Return only one or more FILE blocks and nothing else. Do not use markdown fences or JSON.\n\n"
        "OUTPUT FORMAT:\nFILE relative/file.py\n<<<<<<< CONTENT\n<complete corrected contents of that file>\n>>>>>>> CONTENT\n\n"
        "RULES:\n"
        "- Emit exactly one FILE block for each file you change; omit unchanged files.\n"
        "- path must exactly name one solver-visible repository file.\n"
        "- Between CONTENT markers, emit the complete corrected file, not a diff or fragment.\n"
        "- Preserve indentation and all unchanged source exactly; make only the smallest repair needed.\n"
        "- Do not include FILE/CONTENT wrapper lines inside the file body.\n"
        "- Do not include explanations, line numbers, JSON quoting, or markdown fences.\n"
        "- The harness preserves the original file's terminal-newline convention deterministically.\n"
        "- Horizontal spaces around FILE/CONTENT control lines are wrapper syntax only and are ignored.\n\n"
        f"ISSUE:\n{issue}\n\n" + "\n\n".join(files) + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


def solver_prompt_transport_selection_v2(blueprint: SelectionBlueprint) -> bytes:
    raw = build_solver_prompt_selection_v2(blueprint)
    if not raw.endswith(b"\n"):
        raise RuntimeError("v2 selection prompt must end in one LF before transport")
    return raw[:-1]


@dataclass(frozen=True, slots=True)
class SelectionPackEntryV2:
    task_id: str
    mutation_kind: str
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str

    def payload(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "mutation_kind": self.mutation_kind,
            "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
        }


@dataclass(frozen=True, slots=True)
class SelectionTaskQualificationV2:
    task_id: str
    baseline_evaluation_sha256: str
    gold_evaluation_sha256: str
    baseline_exact_accuracy: float
    gold_exact_accuracy: float
    baseline_valid_rate: float
    gold_valid_rate: float

    def payload(self) -> dict[str, Any]:
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
class SelectionQualificationReportV2:
    software_revision: str
    entries: tuple[SelectionPackEntryV2, ...]
    qualifications: tuple[SelectionTaskQualificationV2, ...]

    def pack_payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_PACK_SCHEMA_V2,
            "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
            "task_count": len(self.entries),
            "candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
            "tasks": [item.payload() for item in self.entries],
        }

    @property
    def pack_sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.pack_payload())).hexdigest()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SELECTION_QUALIFICATION_SCHEMA_V2,
            "software_revision": self.software_revision,
            "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
            "selection_pack_sha256": self.pack_sha256,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "task_count": len(self.entries),
            "tasks": [item.payload() for item in self.entries],
            "qualifications": [item.payload() for item in self.qualifications],
            "candidate_model_inference_performed": False,
            "selection_outcomes_observed": False,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload())).hexdigest()


def _verify_calibration_suite(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"completed v2 calibration suite is missing: {path}")
    if _sha256_file(path) != CALIBRATION_SUITE_FILE_SHA256_V2:
        raise RuntimeError("completed v2 calibration suite file SHA-256 drifted")
    suite = json.loads(path.read_text(encoding="ascii"))
    if suite.get("report_sha256") != CALIBRATION_SUITE_REPORT_SHA256_V2:
        raise RuntimeError("completed v2 calibration suite report identity drifted")
    if tuple(suite.get("eligible_candidate_ids", ())) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("completed v2 calibration eligible population drifted")
    if suite.get("pair_count") != 36 or suite.get("selection_evidence") is not False:
        raise RuntimeError("completed v2 calibration evidence fields drifted")


def run_selection_pack_v2_qualification(
    *, artifact_root: Path, calibration_suite_path: Path, software_revision: str, docker_executable: str = "docker"
) -> SelectionQualificationReportV2:
    validate_selection_pack_v2_freshness()
    _verify_calibration_suite(calibration_suite_path)
    artifact_root = Path(artifact_root)
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("artifact_root must be absent or empty")
    artifact_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision, docker_executable=docker_executable
    )
    empty_patch_sha256 = store.put_bytes(b"")
    entries: list[SelectionPackEntryV2] = []
    qualifications: list[SelectionTaskQualificationV2] = []
    for blueprint in selection_blueprints_v2():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        entries.append(SelectionPackEntryV2(
            task_id=blueprint.task_id,
            mutation_kind=blueprint.mutation_kind.value,
            task_sha256=material.visible_task.sha256,
            generation_record_sha256=material.generation_record.sha256,
            evaluation_plan_sha256=material.evaluation_plan.sha256,
        ))
        baseline_submission_sha256 = store.put_bytes(_canonical_json_bytes({
            "schema": "project-authored-selection-pack-baseline-v2", "task_id": blueprint.task_id
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
        qualifications.append(SelectionTaskQualificationV2(
            task_id=blueprint.task_id,
            baseline_evaluation_sha256=baseline.sha256,
            gold_evaluation_sha256=gold.sha256,
            baseline_exact_accuracy=baseline_accuracy,
            gold_exact_accuracy=gold_accuracy,
            baseline_valid_rate=baseline_valid,
            gold_valid_rate=gold_valid,
        ))
    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("v2 selection qualification left staging residue")
    report = SelectionQualificationReportV2(
        software_revision=software_revision,
        entries=tuple(entries),
        qualifications=tuple(qualifications),
    )
    (artifact_root / "selection-pack-v2.json").write_bytes(_canonical_json_bytes(report.pack_payload()))
    (artifact_root / "selection-qualification-v2.json").write_bytes(_canonical_json_bytes(report.payload()))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and Docker-qualify the untouched v2 selection pack without model inference.")
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--calibration-suite-path", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    report = run_selection_pack_v2_qualification(
        artifact_root=args.artifact_root,
        calibration_suite_path=args.calibration_suite_path,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print("status=SELECTION_PACK_V2_QUALIFIED")
    print(f"selection_pack_sha256={report.pack_sha256}")
    print(f"qualification_report_sha256={report.sha256}")
    print(f"operational_config_freeze_sha256={FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_count={len(report.entries)}")
    print("candidate_model_inference_performed=False")
    for entry, qualification in zip(report.entries, report.qualifications, strict=True):
        print(
            f"task={entry.task_id} kind={entry.mutation_kind} "
            f"baseline={qualification.baseline_exact_accuracy:.6f} gold={qualification.gold_exact_accuracy:.6f} "
            f"baseline_valid={qualification.baseline_valid_rate:.6f} gold_valid={qualification.gold_valid_rate:.6f}"
        )
    print(f"pack_output={args.artifact_root / 'selection-pack-v2.json'}")
    print(f"qualification_output={args.artifact_root / 'selection-qualification-v2.json'}")
    return 0


validate_selection_pack_v2_freshness()

if __name__ == "__main__":
    raise SystemExit(main())
