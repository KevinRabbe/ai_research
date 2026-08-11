from __future__ import annotations

import pytest

from plural_cognition.collective.docker_candidate import DockerRunnerConfiguration
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
        engine_sha256=DIGEST,
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


def test_qualification_report_is_qualified_only_when_every_probe_passes() -> None:
    assert _report(_record("a", True), _record("b", True)).status == QUALIFIED
    assert _report(_record("a", True), _record("b", False)).status == REJECTED


def test_applied_docker_policy_audit_accepts_frozen_controls() -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    case_limits = limits()
    audit = {
        "user": "65534:65534",
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
                f"rw,noexec,nosuid,size={case_limits.writable_bytes}"
            )
        },
    }

    checks = verify_create_audit(
        audit,
        configuration=configuration,
        limits=case_limits,
    )

    assert checks
    assert all(checks.values())


def test_applied_docker_policy_audit_rejects_network_or_extra_bind() -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    case_limits = limits()
    audit = {
        "user": "65534:65534",
        "network_mode": "bridge",
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
        "security_opt": ["no-new-privileges=true"],
        "devices": [],
        "device_requests": [],
        "port_bindings": {},
        "mounts": [
            {"type": "bind", "destination": "/pc-input", "rw": False},
            {"type": "bind", "destination": "/host", "rw": False},
        ],
        "tmpfs": {
            "/pc-work": f"noexec,nosuid,size={case_limits.writable_bytes}"
        },
    }

    with pytest.raises(QualificationFailure, match="network_none"):
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
