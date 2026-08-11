from __future__ import annotations

from pathlib import Path

from plural_cognition.collective.docker_candidate import (
    DOCKER_RUNNER_ID,
    DockerRunnerConfiguration,
    build_docker_command_plan,
)
from plural_cognition.collective.sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
)


IMAGE = "a" * 64


def test_recursive_readonly_bind_declares_rprivate_propagation(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in (
        "bundle-manifest.json",
        "candidate.patch",
        "request.json",
        "runtime-input.bin",
        "sandbox-spec.json",
        "submission.json",
    ):
        (bundle / name).write_bytes(b"")
    (bundle / "repository").mkdir()

    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    limits = SandboxLimits(
        wall_time_ms=30_000,
        cpu_time_ms=20_000,
        memory_bytes=512_000_000,
        writable_bytes=64_000_000,
        process_count=16,
        stdout_bytes=1_000_000,
        stderr_bytes=1_000_000,
    )
    spec = ProtectedSandboxSpec(
        runner_id=DOCKER_RUNNER_ID,
        runner_configuration_sha256=configuration.sha256,
        environment_image_sha256=configuration.environment_image_sha256,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=("python", "-m", "pytest", "-q"),
        environment=(),
        limits=limits,
    )

    plan = build_docker_command_plan(
        spec=spec,
        configuration=configuration,
        input_bundle_directory=bundle,
        container_name="pc-mount-compat",
    )
    mount = plan.create_argv[plan.create_argv.index("--mount") + 1]

    assert "readonly" in mount
    assert "bind-propagation=rprivate" in mount
    assert "bind-recursive=readonly" in mount
