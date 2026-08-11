from __future__ import annotations

import pytest

from plural_cognition.collective.docker_candidate import DockerRunnerConfiguration
from plural_cognition.collective.docker_engine_fingerprint import (
    qualification_engine_sha256,
)
from plural_cognition.collective.docker_identity import DockerEngineIdentity
from plural_cognition.collective.docker_qualification import _qualification_source_sha256
from plural_cognition.collective.docker_qualification_exec import (
    canonical_probe_json,
    expected_nano_cpus,
    limits,
    verify_create_audit,
)
from plural_cognition.collective.docker_qualification_model import (
    QUALIFIED,
    REJECTED,
    DockerQualificationReport,
    QualificationFailure,
    QualificationProbeRecord,
)
from plural_cognition.collective.docker_qualification_probes import (
    qualification_probe_definitions,
)


IMAGE = "a" * 64
DIGEST = "b" * 64
REVISION = "c" * 40


def _record(name: str, passed: bool) -> QualificationProbeRecord:
    return QualificationProbeRecord(
        name=name,
        passed=passed,
        request_sha256="d" * 64,
        sandbox_result=None,
        evidence={},
        error=None if passed else "failed",
    )


def _report(*records: QualificationProbeRecord) -> DockerQualificationReport:
    return DockerQualificationReport(
        software_revision=REVISION,
        engine_observation_sha256=DIGEST,
        engine_qualification_sha256=DIGEST,
        image_identity_sha256=DIGEST,
        immutable_image=f"sha256:{IMAGE}",
        runner_configuration_sha256=DIGEST,
        sandbox_contract_sha256=DIGEST,
        qualification_source_sha256=DIGEST,
        bootstrap_core_sha256=DIGEST,
        bootstrap_guard_sha256=DIGEST,
        dockerfile_sha256=DIGEST,
        probes=tuple(records),
    )


def _engine(*, ncpu: int = 24, memory_bytes: int = 16_634_265_600) -> DockerEngineIdentity:
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
        ncpu=ncpu,
        memory_bytes=memory_bytes,
    )


def _frozen_audit(
    configuration: DockerRunnerConfiguration,
    case_limits,
) -> dict[str, object]:
    return {
        "user": f"{configuration.candidate_uid}:{configuration.candidate_gid}",
        "network_mode": "none",
        "ipc_mode": "none",
        "pid_mode": "",
        "cgroupns_mode": "private",
        "privileged": False,
        "readonly_rootfs": True,
        "pids_limit": case_limits.process_count,
        "memory": case_limits.memory_bytes,
        "memory_swap": case_limits.memory_bytes,
        "nano_cpus": expected_nano_cpus(case_limits),
        "restart_policy": "no",
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "devices": [],
        "device_requests": [],
        "port_bindings": {},
        "mounts": [
            {"type": "bind", "destination": "/pc-input", "rw": False},
            {"type": "tmpfs", "destination": "/pc-work", "rw": True},
        ],
        "tmpfs": {
            "/pc-work": (
                f"rw,noexec,nosuid,size={case_limits.writable_bytes},"
                f"mode=0700,uid={configuration.candidate_uid},"
                f"gid={configuration.candidate_gid}"
            )
        },
    }


def test_qualification_report_is_qualified_only_when_every_probe_passes() -> None:
    assert _report(_record("a", True), _record("b", True)).status == QUALIFIED
    assert _report(_record("a", True), _record("b", False)).status == REJECTED


def test_engine_qualification_fingerprint_excludes_capacity_observation() -> None:
    baseline = _engine()
    capacity_drift = _engine(ncpu=20, memory_bytes=16_634_277_888)

    assert baseline.sha256 != capacity_drift.sha256
    assert qualification_engine_sha256(baseline) == qualification_engine_sha256(
        capacity_drift
    )


def test_engine_qualification_fingerprint_changes_on_security_surface() -> None:
    baseline = _engine()
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

    assert qualification_engine_sha256(baseline) != qualification_engine_sha256(
        changed
    )


def test_applied_docker_policy_audit_accepts_frozen_controls() -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    case_limits = limits()
    audit = _frozen_audit(configuration, case_limits)

    checks = verify_create_audit(
        audit,
        configuration=configuration,
        limits=case_limits,
    )

    assert checks
    assert all(checks.values())
    assert checks["workspace_tmpfs_writable"] is True
    assert checks["workspace_tmpfs_mode"] is True
    assert checks["workspace_tmpfs_owner"] is True


def test_applied_docker_policy_audit_rejects_network_or_extra_bind() -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    case_limits = limits()
    audit = _frozen_audit(configuration, case_limits)
    audit["network_mode"] = "bridge"
    audit["mounts"] = [
        {"type": "bind", "destination": "/pc-input", "rw": False},
        {"type": "bind", "destination": "/host", "rw": False},
    ]

    with pytest.raises(QualificationFailure, match="network_none"):
        verify_create_audit(
            audit,
            configuration=configuration,
            limits=case_limits,
        )


@pytest.mark.parametrize(
    ("tmpfs_value", "expected_check"),
    (
        (
            "rw,noexec,nosuid,size=8388608,uid=65534,gid=65534",
            "workspace_tmpfs_mode",
        ),
        (
            "rw,noexec,nosuid,size=8388608,mode=0700,gid=65534",
            "workspace_tmpfs_owner",
        ),
        (
            "rw,noexec,nosuid,size=8388608,mode=0700,uid=65534",
            "workspace_tmpfs_owner",
        ),
        (
            "ro,noexec,nosuid,size=8388608,mode=0700,uid=65534,gid=65534",
            "workspace_tmpfs_writable",
        ),
    ),
)
def test_applied_docker_policy_audit_rejects_workspace_identity_or_mode_drift(
    tmpfs_value: str,
    expected_check: str,
) -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    case_limits = limits()
    audit = _frozen_audit(configuration, case_limits)
    audit["tmpfs"] = {"/pc-work": tmpfs_value}

    with pytest.raises(QualificationFailure, match=expected_check):
        verify_create_audit(
            audit,
            configuration=configuration,
            limits=case_limits,
        )


def test_probe_json_must_be_one_canonical_line() -> None:
    assert canonical_probe_json(b'{"a":1}\n') == {"a": 1}
    with pytest.raises(QualificationFailure, match="canonical"):
        canonical_probe_json(b'{"a": 1}\n')
    with pytest.raises(QualificationFailure, match="one JSON line"):
        canonical_probe_json(b'{"a":1}\n\n')


def test_qualification_matrix_is_unique_and_covers_frozen_requirements() -> None:
    definitions = qualification_probe_definitions()
    names = [definition.name for definition in definitions]
    assert len(names) == len(set(names))
    assert {
        "result-capture-and-policy",
        "isolation-surface",
        "network-denial",
        "fresh-workspace-a",
        "fresh-workspace-b",
        "wall-time-ceiling",
        "stdout-ceiling",
        "stderr-ceiling",
        "memory-oom-ceiling",
        "process-count-ceiling",
        "writable-space-ceiling",
        "cpu-bandwidth-ceiling",
    } == set(names)


def test_qualification_source_bundle_is_content_addressed() -> None:
    digest = _qualification_source_sha256()
    assert len(digest) == 64
    int(digest, 16)
