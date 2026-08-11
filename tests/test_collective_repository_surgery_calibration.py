from __future__ import annotations

import pytest

from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.docker_bootstrap import apply_unified_diff
from plural_cognition.collective.docker_identity import DockerEngineIdentity
from plural_cognition.collective.qualified_docker import (
    QUALIFIED_DOCKER,
    QUALIFIED_DOCKER_ENGINE_SHA256,
    QUALIFIED_DOCKER_RUNNER_CONFIGURATION_SHA256,
    QualifiedDockerError,
)
from plural_cognition.collective.repository import (
    load_repository_snapshot,
    materialize_repository_snapshot,
    snapshot_directory,
)
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration import (
    CALIBRATION_TASK_ID,
    build_calibration_material,
)
from plural_cognition.collective.tasks import TaskSplit

REVISION = "a" * 40


def _qualified_engine() -> DockerEngineIdentity:
    return DockerEngineIdentity(
        client_version="29.7.2",
        client_api_version="1.55",
        client_git_commit="a7dcaa6",
        server_version="29.7.2",
        server_api_version="1.55",
        server_git_commit="6a43e3d",
        platform_name="Docker Desktop 4.86.0 (236216)",
        os_type="linux",
        architecture="x86_64",
        kernel_version="6.18.33.2-microsoft-standard-WSL2",
        operating_system="Docker Desktop",
        cgroup_version="2",
        cgroup_driver="cgroupfs",
        docker_root_dir="/var/lib/docker",
        security_options=("name=cgroupns", "name=seccomp,profile=builtin"),
        ncpu=24,
        memory_bytes=16_634_265_600,
    )


def test_qualified_docker_binding_matches_v10_source_and_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        "plural_cognition.collective.qualified_docker._qualification_source_sha256",
        lambda: QUALIFIED_DOCKER.qualification_source_sha256,
    )
    configuration = QUALIFIED_DOCKER.configuration()
    assert configuration.sha256 == QUALIFIED_DOCKER_RUNNER_CONFIGURATION_SHA256
    assert QUALIFIED_DOCKER.engine_qualification_sha256 == QUALIFIED_DOCKER_ENGINE_SHA256
    QUALIFIED_DOCKER.assert_engine(_qualified_engine())


def test_qualified_docker_binding_rejects_source_drift(monkeypatch) -> None:
    monkeypatch.setattr(
        "plural_cognition.collective.qualified_docker._qualification_source_sha256",
        lambda: "0" * 64,
    )
    with pytest.raises(QualifiedDockerError, match="source drifted"):
        QUALIFIED_DOCKER.configuration()


def test_qualified_docker_binding_rejects_engine_security_surface_drift() -> None:
    baseline = _qualified_engine()
    changed = DockerEngineIdentity(
        client_version=baseline.client_version,
        client_api_version=baseline.client_api_version,
        client_git_commit=baseline.client_git_commit,
        server_version=baseline.server_version,
        server_api_version=baseline.server_api_version,
        server_git_commit=baseline.server_git_commit,
        platform_name=baseline.platform_name,
        os_type=baseline.os_type,
        architecture=baseline.architecture,
        kernel_version=baseline.kernel_version,
        operating_system=baseline.operating_system,
        cgroup_version=baseline.cgroup_version,
        cgroup_driver=baseline.cgroup_driver,
        docker_root_dir=baseline.docker_root_dir,
        security_options=("name=cgroupns",),
        ncpu=baseline.ncpu,
        memory_bytes=baseline.memory_bytes,
    )
    with pytest.raises(QualifiedDockerError, match="fingerprint drifted"):
        QUALIFIED_DOCKER.assert_engine(changed)


def test_calibration_material_is_bound_and_gold_patch_restores_clean_tree(tmp_path) -> None:
    store = FileContentStore(tmp_path / "store")
    material = build_calibration_material(
        store=store,
        work_root=tmp_path / "build",
        software_revision=REVISION,
    )

    assert material.visible_task.task.task_id == CALIBRATION_TASK_ID
    assert material.visible_task.split is TaskSplit.CALIBRATION
    assert material.generation_record.mutation_kind is MutationKind.BOUNDARY
    assert material.generation_record.binds(material.visible_task)
    assert material.evaluation_plan.task == material.visible_task.task
    assert len(material.evaluation_plan.cases) == 4
    assert material.evaluation_plan.evaluator.pass_threshold == 1.0
    assert material.generation_record.clean_repository_sha256 != material.generation_record.buggy_repository_sha256

    visible = material.visible_task.canonical_payload()
    rendered = str(visible)
    assert material.generation_record.protected_expectations_sha256 not in rendered
    assert material.generation_record.gold_patch_sha256 not in rendered

    buggy = load_repository_snapshot(
        material.generation_record.buggy_repository_sha256,
        store,
    )
    repaired_root = tmp_path / "repaired"
    materialize_repository_snapshot(buggy, repaired_root, store)
    apply_unified_diff(
        repaired_root,
        store.get_bytes(material.gold_submission.patch_sha256),
    )
    repaired = snapshot_directory(repaired_root, store)
    assert repaired.manifest_sha256 == material.generation_record.clean_repository_sha256


def test_calibration_threshold_case_is_the_hidden_boundary_failure(tmp_path) -> None:
    store = FileContentStore(tmp_path / "store")
    material = build_calibration_material(
        store=store,
        work_root=tmp_path / "build",
        software_revision=REVISION,
    )
    threshold = next(
        case for case in material.evaluation_plan.cases if case.case_id == "case-02-threshold"
    )
    assert store.get_bytes(threshold.runtime_input_sha256) == b'{"premium":true,"subtotal":50}\n'
    assert store.get_bytes(threshold.expected_output_sha256) == b'{"total":52}\n'
