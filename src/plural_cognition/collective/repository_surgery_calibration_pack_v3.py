"""Fresh six-task development-calibration pack for candidate-pool v3.

The v3 representation protocol is already frozen before this task material exists.
These tasks are new development evidence: one task for each repository-surgery
defect family, with no ID reuse from v2 calibration or the consumed v2 selection
split. Qualification executes only project-authored baselines and gold repairs in
the qualified Docker evaluator; candidate models are never invoked here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_calibration_protocol import CALIBRATION_TASK_IDS_V2
from .candidate_pool_v2_selection_protocol import SELECTION_TASK_IDS_V2
from .candidate_pool_v3_full_file import gold_full_file_output_v3, solver_prompt_transport_v3
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEFECT_FAMILIES,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_FRESH_CALIBRATION_TASK_COUNT,
    validate_v3_representation_protocol,
)
from .content_store import FileContentStore
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository_surgery import MutationKind
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric
from .repository_surgery_selection_pack_v1 import SelectionBlueprint, build_selection_material

CALIBRATION_PACK_SCHEMA_V3 = "plural-cognition-repository-surgery-calibration-pack-v3"
CALIBRATION_QUALIFICATION_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-calibration-qualification-v3"
)

CALIBRATION_TASK_IDS_V3 = (
    "repository-surgery-calibration-v3-api-contract-0001",
    "repository-surgery-calibration-v3-boundary-0001",
    "repository-surgery-calibration-v3-error-handling-0001",
    "repository-surgery-calibration-v3-local-logic-0001",
    "repository-surgery-calibration-v3-multi-file-0001",
    "repository-surgery-calibration-v3-state-management-0001",
)
CALIBRATION_SEEDS_V3 = (301, 302, 303, 304, 305, 306)


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


def calibration_blueprints_v3() -> tuple[SelectionBlueprint, ...]:
    api_clean = _src('''import json\nimport sys\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    locale = str(payload.get("locale", "en"))\n    result = {"locale": locale, "message": str(payload["message"])}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    api_buggy = api_clean.replace(b'payload.get("locale", "en")', b'payload["locale"]')

    boundary_clean = _src('''import json\nimport sys\n\ndef handling_fee(weight: int) -> int:\n    return 4 if weight <= 10 else 9\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"fee": handling_fee(int(payload["weight"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    boundary_buggy = boundary_clean.replace(b"weight <= 10", b"weight < 10")

    error_clean = _src('''import json\nimport sys\n\ndef reciprocal(divisor: int) -> float:\n    if divisor == 0:\n        raise ValueError("zero divisor")\n    return 1.0 / divisor\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        result = {"ok": True, "value": reciprocal(int(payload["divisor"]))}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    error_buggy = error_clean.replace(b"divisor == 0", b"divisor < 0")

    local_clean = _src('''import json\nimport sys\n\ndef net_points(base: int, penalty: int) -> int:\n    return base - penalty\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"points": net_points(int(payload["base"]), int(payload["penalty"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    local_buggy = local_clean.replace(b"base - penalty", b"base + penalty")

    multi_app_clean = _src('''import json\nimport sys\nfrom fees import service_fee\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    total = int(payload["subtotal"]) + service_fee(str(payload["plan"]))\n    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    multi_helper_clean = _src('''def service_fee(plan: str) -> int:\n    return 2 if plan == "pro" else 5\n''')
    multi_app_buggy = multi_app_clean.replace(b" + service_fee", b" - service_fee")
    multi_helper_buggy = multi_helper_clean.replace(b"return 2 if", b"return 3 if")

    state_clean = _src('''import json\nimport sys\n\nclass DistinctTracker:\n    def __init__(self) -> None:\n        self.seen: set[int] = set()\n\n    def push(self, value: int) -> int:\n        self.seen.add(value)\n        return len(self.seen)\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    tracker = DistinctTracker()\n    counts = [tracker.push(int(value)) for value in payload["values"]]\n    sys.stdout.write(json.dumps({"counts": counts}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n''')
    state_buggy = state_clean.replace(b"self.seen.add(value)", b"self.seen = {value}")

    blueprints = (
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[0],
            kind=MutationKind.API_CONTRACT,
            seed=CALIBRATION_SEEDS_V3[0],
            clean_files=(("app.py", api_clean),),
            buggy_files=(("app.py", api_buggy),),
            issue=(
                "Fix the message JSON API. 'message' remains required; 'locale' is optional "
                "and must default to 'en' when omitted."
            ),
            public=(
                {"input": {"message": "hi", "locale": "de"}, "expected": {"locale": "de", "message": "hi"}},
            ),
            protected=(
                ("case-01-explicit", {"message": "hi", "locale": "de"}, {"locale": "de", "message": "hi"}),
                ("case-02-default", {"message": "hello"}, {"locale": "en", "message": "hello"}),
                ("case-03-empty", {"message": ""}, {"locale": "en", "message": ""}),
                ("case-04-other", {"message": "x", "locale": "fr"}, {"locale": "fr", "message": "x"}),
            ),
            mutation={"schema": "calibration-v3-api-contract", "mutation": "optional-to-required", "field": "locale"},
        ),
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[1],
            kind=MutationKind.BOUNDARY,
            seed=CALIBRATION_SEEDS_V3[1],
            clean_files=(("app.py", boundary_clean),),
            buggy_files=(("app.py", boundary_buggy),),
            issue="Fix handling fees. Weights up to and including 10 cost 4; heavier packages cost 9.",
            public=(
                {"input": {"weight": 9}, "expected": {"fee": 4}},
                {"input": {"weight": 11}, "expected": {"fee": 9}},
            ),
            protected=(
                ("case-01-light", {"weight": 1}, {"fee": 4}),
                ("case-02-below", {"weight": 9}, {"fee": 4}),
                ("case-03-threshold", {"weight": 10}, {"fee": 4}),
                ("case-04-heavy", {"weight": 12}, {"fee": 9}),
            ),
            mutation={"schema": "calibration-v3-boundary", "from": "<=", "to": "<", "threshold": 10},
        ),
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[2],
            kind=MutationKind.ERROR_HANDLING,
            seed=CALIBRATION_SEEDS_V3[2],
            clean_files=(("app.py", error_clean),),
            buggy_files=(("app.py", error_buggy),),
            issue=(
                "Fix reciprocal error handling. A zero divisor is invalid input and must return "
                "the existing invalid-input JSON response rather than crashing."
            ),
            public=(
                {"input": {"divisor": 2}, "expected": {"ok": True, "value": 0.5}},
            ),
            protected=(
                ("case-01-positive", {"divisor": 4}, {"ok": True, "value": 0.25}),
                ("case-02-one", {"divisor": 1}, {"ok": True, "value": 1.0}),
                ("case-03-zero", {"divisor": 0}, {"error": "invalid-input", "ok": False}),
                ("case-04-negative", {"divisor": -2}, {"ok": True, "value": -0.5}),
            ),
            mutation={"schema": "calibration-v3-error-handling", "mutation": "wrong-invalid-boundary", "field": "divisor"},
        ),
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[3],
            kind=MutationKind.LOCAL_LOGIC,
            seed=CALIBRATION_SEEDS_V3[3],
            clean_files=(("app.py", local_clean),),
            buggy_files=(("app.py", local_buggy),),
            issue="Fix points accounting. Penalty points must be subtracted from the base score, not added.",
            public=(
                {"input": {"base": 20, "penalty": 3}, "expected": {"points": 17}},
            ),
            protected=(
                ("case-01-basic", {"base": 20, "penalty": 3}, {"points": 17}),
                ("case-02-zero", {"base": 5, "penalty": 0}, {"points": 5}),
                ("case-03-equal", {"base": 7, "penalty": 7}, {"points": 0}),
                ("case-04-negative-base", {"base": -2, "penalty": 3}, {"points": -5}),
            ),
            mutation={"schema": "calibration-v3-local-logic", "from": "subtract", "to": "add", "field": "penalty"},
        ),
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[4],
            kind=MutationKind.MULTI_FILE_BEHAVIOR,
            seed=CALIBRATION_SEEDS_V3[4],
            clean_files=(("app.py", multi_app_clean), ("fees.py", multi_helper_clean)),
            buggy_files=(("app.py", multi_app_buggy), ("fees.py", multi_helper_buggy)),
            issue=(
                "Fix checkout service fees. The service fee is added to subtotal, and the 'pro' "
                "plan fee is 2 while other plans cost 5. Repair all files needed."
            ),
            public=(
                {"input": {"subtotal": 20, "plan": "pro"}, "expected": {"total": 22}},
                {"input": {"subtotal": 20, "plan": "basic"}, "expected": {"total": 25}},
            ),
            protected=(
                ("case-01-pro", {"subtotal": 20, "plan": "pro"}, {"total": 22}),
                ("case-02-basic", {"subtotal": 20, "plan": "basic"}, {"total": 25}),
                ("case-03-zero", {"subtotal": 0, "plan": "pro"}, {"total": 2}),
                ("case-04-other", {"subtotal": 7, "plan": "team"}, {"total": 12}),
            ),
            mutation={"schema": "calibration-v3-multi-file", "mutations": ["wrong-operation", "wrong-pro-fee"]},
        ),
        _blueprint(
            task_id=CALIBRATION_TASK_IDS_V3[5],
            kind=MutationKind.STATE_MANAGEMENT,
            seed=CALIBRATION_SEEDS_V3[5],
            clean_files=(("app.py", state_clean),),
            buggy_files=(("app.py", state_buggy),),
            issue=(
                "Fix DistinctTracker state. Each returned count must be the number of distinct "
                "values observed across the entire sequence so far."
            ),
            public=(
                {"input": {"values": [2, 2, 5]}, "expected": {"counts": [1, 1, 2]}},
            ),
            protected=(
                ("case-01-repeat", {"values": [2, 2, 5]}, {"counts": [1, 1, 2]}),
                ("case-02-growing", {"values": [1, 2, 3]}, {"counts": [1, 2, 3]}),
                ("case-03-return", {"values": [1, 2, 1, 3]}, {"counts": [1, 2, 2, 3]}),
                ("case-04-negative", {"values": [-1, -1, 0]}, {"counts": [1, 1, 2]}),
            ),
            mutation={"schema": "calibration-v3-state-management", "mutation": "replace-history-with-current"},
        ),
    )
    if tuple(item.task_id for item in blueprints) != CALIBRATION_TASK_IDS_V3:
        raise AssertionError("v3 calibration task order drifted")
    return blueprints


def validate_calibration_pack_v3_freshness() -> None:
    validate_v3_representation_protocol()
    blueprints = calibration_blueprints_v3()
    ids = tuple(item.task_id for item in blueprints)
    seeds = tuple(item.generation_seed for item in blueprints)
    kinds = tuple(item.mutation_kind.value for item in blueprints)
    if len(blueprints) != V3_FRESH_CALIBRATION_TASK_COUNT or len(set(ids)) != len(ids):
        raise RuntimeError("v3 calibration pack must contain six unique tasks")
    if seeds != CALIBRATION_SEEDS_V3 or len(set(seeds)) != len(seeds):
        raise RuntimeError("v3 calibration seeds drifted")
    if set(ids) & set(CALIBRATION_TASK_IDS_V2):
        raise RuntimeError("v3 calibration IDs overlap v2 calibration")
    if set(ids) & set(SELECTION_TASK_IDS_V2):
        raise RuntimeError("v3 calibration IDs overlap consumed v2 selection")
    if kinds != V3_DEFECT_FAMILIES:
        raise RuntimeError(f"v3 calibration defect-family coverage drifted: {kinds!r}")
    for blueprint in blueprints:
        prompt = solver_prompt_transport_v3(blueprint)
        if b"relative/file.py" in prompt or b"FILE relative/" in prompt:
            raise RuntimeError(f"v3 prompt path defect survived: {blueprint.task_id}")
        gold_full_file_output_v3(blueprint)


@dataclass(frozen=True, slots=True)
class CalibrationPackEntryV3:
    task_id: str
    mutation_kind: str
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str
    solver_prompt_sha256: str

    def payload(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "mutation_kind": self.mutation_kind,
            "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
            "solver_prompt_sha256": self.solver_prompt_sha256,
        }


@dataclass(frozen=True, slots=True)
class CalibrationTaskQualificationV3:
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
class CalibrationQualificationReportV3:
    software_revision: str
    entries: tuple[CalibrationPackEntryV3, ...]
    qualifications: tuple[CalibrationTaskQualificationV3, ...]

    def pack_payload(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_PACK_SCHEMA_V3,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "task_count": len(self.entries),
            "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
            "tasks": [item.payload() for item in self.entries],
            "selection_evidence": False,
        }

    @property
    def pack_sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.pack_payload())).hexdigest()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_QUALIFICATION_SCHEMA_V3,
            "software_revision": self.software_revision,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "calibration_pack_sha256": self.pack_sha256,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "task_count": len(self.entries),
            "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
            "tasks": [item.payload() for item in self.entries],
            "qualifications": [item.payload() for item in self.qualifications],
            "candidate_model_inference_performed": False,
            "calibration_candidate_outcomes_observed": False,
            "selection_outcomes_observed": False,
            "selection_evidence": False,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload())).hexdigest()


def run_calibration_pack_v3_qualification(
    *,
    artifact_root: Path,
    software_revision: str,
    docker_executable: str = "docker",
) -> CalibrationQualificationReportV3:
    validate_calibration_pack_v3_freshness()
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
    entries: list[CalibrationPackEntryV3] = []
    qualifications: list[CalibrationTaskQualificationV3] = []

    for blueprint in calibration_blueprints_v3():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        prompt_sha256 = hashlib.sha256(solver_prompt_transport_v3(blueprint)).hexdigest()
        entries.append(
            CalibrationPackEntryV3(
                task_id=blueprint.task_id,
                mutation_kind=blueprint.mutation_kind.value,
                task_sha256=material.visible_task.sha256,
                generation_record_sha256=material.generation_record.sha256,
                evaluation_plan_sha256=material.evaluation_plan.sha256,
                solver_prompt_sha256=prompt_sha256,
            )
        )

        baseline_submission_sha256 = store.put_bytes(
            _canonical_json_bytes(
                {
                    "schema": "project-authored-calibration-pack-baseline-v3",
                    "task_id": blueprint.task_id,
                }
            )
        )
        baseline = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=empty_patch_sha256,
            submission_sha256=baseline_submission_sha256,
            artifact_sha256=baseline_submission_sha256,
            docker_executable=docker_executable,
        )
        gold = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=material.gold_submission.patch_sha256,
            submission_sha256=material.gold_submission.sha256,
            artifact_sha256=material.gold_submission.sha256,
            docker_executable=docker_executable,
        )
        baseline_exact = _metric(baseline, "exact_accuracy")
        gold_exact = _metric(gold, "exact_accuracy")
        baseline_valid = _metric(baseline, "valid_rate")
        gold_valid = _metric(gold, "valid_rate")
        if baseline_exact >= 1.0:
            raise RuntimeError(f"v3 calibration baseline is not observably defective: {blueprint.task_id}")
        if gold_exact != 1.0 or gold_valid != 1.0 or not gold.qualified:
            raise RuntimeError(f"v3 calibration gold repair did not fully qualify: {blueprint.task_id}")
        qualifications.append(
            CalibrationTaskQualificationV3(
                task_id=blueprint.task_id,
                baseline_evaluation_sha256=baseline.sha256,
                gold_evaluation_sha256=gold.sha256,
                baseline_exact_accuracy=baseline_exact,
                gold_exact_accuracy=gold_exact,
                baseline_valid_rate=baseline_valid,
                gold_valid_rate=gold_valid,
            )
        )

    report = CalibrationQualificationReportV3(
        software_revision=software_revision,
        entries=tuple(entries),
        qualifications=tuple(qualifications),
    )
    pack_path = artifact_root / "calibration-pack-v3.json"
    qualification_path = artifact_root / "calibration-qualification-v3.json"
    pack_path.write_bytes(_canonical_json_bytes(report.pack_payload()) + b"\n")
    qualification_path.write_bytes(_canonical_json_bytes(report.payload()) + b"\n")

    print("status=CALIBRATION_PACK_V3_QUALIFIED")
    print(f"representation_protocol_sha256={EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256}")
    print(f"calibration_pack_sha256={report.pack_sha256}")
    print(f"qualification_report_sha256={report.sha256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_count={len(report.entries)}")
    print("candidate_ids=" + ",".join(V3_DEVELOPMENT_CANDIDATE_IDS))
    print("candidate_model_inference_performed=False")
    print("calibration_candidate_outcomes_observed=False")
    print("selection_outcomes_observed=False")
    for item in report.qualifications:
        print(
            "task=" + item.task_id
            + f" baseline_exact={item.baseline_exact_accuracy:.6f}"
            + f" gold_exact={item.gold_exact_accuracy:.6f}"
            + f" baseline_valid={item.baseline_valid_rate:.6f}"
            + f" gold_valid={item.gold_valid_rate:.6f}"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    run_calibration_pack_v3_qualification(
        artifact_root=Path(args.artifact_root),
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
