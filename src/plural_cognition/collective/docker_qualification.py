"""Exact-scope adversarial qualification orchestrator for the protected Docker runner.

This is the first project CLI that deliberately starts containers. It executes
only deterministic project-authored probes from ``docker_qualification_probes``;
model-generated patches and protected grader state remain excluded.
"""

from __future__ import annotations

import argparse
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from .content_store import FileContentStore, validate_sha256
from .docker_bootstrap_guard import CORE_BOOTSTRAP_SHA256
from .docker_candidate import DockerRunnerConfiguration
from .docker_identity import probe_docker_qualification_identity
from .docker_local_image import probe_local_qualification_image
from .docker_qualification_exec import execute_probe
from .docker_qualification_model import (
    QUALIFIED,
    DockerQualificationReport,
    QualificationFailure,
    QualificationProbeRecord,
    canonical_json_bytes,
    validate_git_revision,
)
from .docker_qualification_probes import qualification_probe_definitions

_BASE_IMAGE = (
    "python@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3"
)


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"qualification source file does not exist: {path}")
    return sha256(path.read_bytes()).hexdigest()


def _qualification_source_sha256() -> str:
    root = Path(__file__).parent
    payload = {
        name: _sha256_file(root / name)
        for name in (
            "docker_qualification.py",
            "docker_qualification_exec.py",
            "docker_qualification_model.py",
            "docker_qualification_probes.py",
        )
    }
    return sha256(canonical_json_bytes(payload)).hexdigest()


def run_docker_qualification(
    *,
    image_reference: str,
    software_revision: str,
    expected_engine_sha256: str,
    output: Path,
    evidence_root: Path,
    dockerfile: Path,
    bootstrap_guard: Path,
    bootstrap_core: Path,
    sandbox_contract: Path,
    docker_executable: str = "docker",
) -> DockerQualificationReport:
    """Run the frozen Repository Surgery v0 qualification matrix."""

    validate_git_revision(software_revision)
    validate_sha256(expected_engine_sha256)
    if not image_reference.startswith("sha256:"):
        raise ValueError(
            "qualification image must be an immutable local sha256 reference"
        )
    validate_sha256(image_reference.split(":", 1)[1])

    evidence_root = Path(evidence_root)
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise ValueError("evidence_root must be absent or empty")
    evidence_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(evidence_root / "store")
    staging_root = evidence_root / "staging"
    staging_root.mkdir()
    work_root = evidence_root / "work"
    work_root.mkdir()

    base_identity = probe_docker_qualification_identity(
        image_reference=_BASE_IMAGE,
        software_revision=software_revision,
        docker_executable=docker_executable,
    )
    engine = base_identity.engine
    if engine.sha256 != expected_engine_sha256:
        raise QualificationFailure(
            "Docker Engine fingerprint changed; rerun the non-starting identity "
            "freeze before qualification"
        )

    local_image = probe_local_qualification_image(
        image_reference=image_reference,
        software_revision=software_revision,
        dockerfile=Path(dockerfile),
        bootstrap=Path(bootstrap_guard),
        docker_executable=docker_executable,
    )
    if local_image.immutable_reference != image_reference:
        raise QualificationFailure(
            "local image identity does not match requested immutable image"
        )

    core_sha256 = _sha256_file(Path(bootstrap_core))
    if core_sha256 != CORE_BOOTSTRAP_SHA256:
        raise QualificationFailure(
            "bootstrap core no longer matches the guard's frozen SHA-256"
        )

    configuration = DockerRunnerConfiguration(image_reference=image_reference)
    records: list[QualificationProbeRecord] = []
    for definition in qualification_probe_definitions():
        records.append(
            execute_probe(
                name=definition.name,
                command_argv=definition.command_argv,
                case_limits=definition.limits,
                verifier=definition.verifier,
                configuration=configuration,
                store=store,
                work_root=work_root,
                staging_root=staging_root,
                docker_executable=docker_executable,
            )
        )

    shutil.rmtree(work_root)
    remaining_staging = list(staging_root.iterdir())
    if remaining_staging:
        records.append(
            QualificationProbeRecord(
                name="final-staging-cleanup",
                passed=False,
                request_sha256=None,
                sandbox_result=None,
                evidence={"staging_entry_count": len(remaining_staging)},
                error="staging root was non-empty after qualification matrix",
            )
        )

    report = DockerQualificationReport(
        software_revision=software_revision,
        engine_sha256=engine.sha256,
        image_identity_sha256=local_image.sha256,
        immutable_image=local_image.immutable_reference,
        runner_configuration_sha256=configuration.sha256,
        sandbox_contract_sha256=_sha256_file(Path(sandbox_contract)),
        qualification_source_sha256=_qualification_source_sha256(),
        bootstrap_core_sha256=core_sha256,
        bootstrap_guard_sha256=local_image.bootstrap_sha256,
        dockerfile_sha256=local_image.dockerfile_sha256,
        probes=tuple(records),
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(canonical_json_bytes(report.canonical_payload()))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run project-authored adversarial qualification of the protected "
            "Docker runner."
        )
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--expected-engine-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument(
        "--dockerfile",
        default=Path("docker/protected-runner/Dockerfile"),
        type=Path,
    )
    parser.add_argument(
        "--bootstrap-guard",
        default=Path(
            "src/plural_cognition/collective/docker_bootstrap_guard.py"
        ),
        type=Path,
    )
    parser.add_argument(
        "--bootstrap-core",
        default=Path("src/plural_cognition/collective/docker_bootstrap.py"),
        type=Path,
    )
    parser.add_argument(
        "--sandbox-contract",
        default=Path("docs/26-protected-sandbox-interface.md"),
        type=Path,
    )
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = run_docker_qualification(
        image_reference=args.image,
        software_revision=args.software_revision,
        expected_engine_sha256=args.expected_engine_sha256,
        output=args.output,
        evidence_root=args.evidence_root,
        dockerfile=args.dockerfile,
        bootstrap_guard=args.bootstrap_guard,
        bootstrap_core=args.bootstrap_core,
        sandbox_contract=args.sandbox_contract,
        docker_executable=args.docker_executable,
    )
    print(f"status={report.status}")
    print(f"report_sha256={report.sha256}")
    print(f"engine_sha256={report.engine_sha256}")
    print(f"image_identity_sha256={report.image_identity_sha256}")
    print(f"immutable_image={report.immutable_image}")
    for probe in report.probes:
        print(f"probe={probe.name}:{'PASS' if probe.passed else 'FAIL'}")
        if probe.error is not None:
            print(f"probe_error={probe.name}:{probe.error}")
    print(f"output={args.output}")
    return 0 if report.status == QUALIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
