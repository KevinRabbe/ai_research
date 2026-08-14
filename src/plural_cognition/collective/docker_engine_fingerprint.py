"""Stable Docker Engine fingerprint for protected-runner qualification.

Docker Desktop on WSL2 can report small changes in host-visible capacity fields
such as ``MemTotal`` even when the Engine, kernel, cgroup/security surface, and
runtime configuration are unchanged. Exact capacity observations remain in the
full ``DockerEngineIdentity`` artifact, but they are not suitable as a binary
containment-identity gate.

This module therefore hashes only the structural/security-relevant Engine fields
used to decide whether a previously frozen target is still the same qualification
surface. CPU and memory ceilings remain empirically tested by the adversarial
qualification matrix.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from typing import Any, Sequence

from .docker_identity import DockerEngineIdentity, probe_docker_qualification_identity

DOCKER_ENGINE_QUALIFICATION_FINGERPRINT_SCHEMA = (
    "plural-cognition-docker-engine-qualification-fingerprint-v1"
)


def qualification_engine_payload(engine: DockerEngineIdentity) -> dict[str, Any]:
    if not isinstance(engine, DockerEngineIdentity):
        raise TypeError("engine must be DockerEngineIdentity")
    return {
        "schema": DOCKER_ENGINE_QUALIFICATION_FINGERPRINT_SCHEMA,
        "client_version": engine.client_version,
        "client_api_version": engine.client_api_version,
        "client_git_commit": engine.client_git_commit,
        "server_version": engine.server_version,
        "server_api_version": engine.server_api_version,
        "server_git_commit": engine.server_git_commit,
        "platform_name": engine.platform_name,
        "os_type": engine.os_type,
        "architecture": engine.architecture,
        "kernel_version": engine.kernel_version,
        "operating_system": engine.operating_system,
        "cgroup_version": engine.cgroup_version,
        "cgroup_driver": engine.cgroup_driver,
        "docker_root_dir": engine.docker_root_dir,
        "security_options": list(engine.security_options),
    }


def qualification_engine_sha256(engine: DockerEngineIdentity) -> str:
    import json

    raw = json.dumps(
        qualification_engine_payload(engine),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return sha256(raw).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Docker without starting a container and print both the exact "
            "Engine observation hash and the stable qualification fingerprint."
        )
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = probe_docker_qualification_identity(
        image_reference=args.image,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print(f"engine_observation_sha256={report.engine.sha256}")
    print(
        "engine_qualification_sha256="
        f"{qualification_engine_sha256(report.engine)}"
    )
    print(f"engine_ncpu={report.engine.ncpu}")
    print(f"engine_memory_bytes={report.engine.memory_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
