from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective.artifacts import TaskIdentity
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.docker_candidate import (
    DOCKER_RUNNER_ID,
    DockerRunnerConfiguration,
    build_docker_command_plan,
    prepare_docker_input_bundle,
)
from plural_cognition.collective.repository import snapshot_directory
from plural_cognition.collective.sandbox import (
    NetworkPolicy,
    ProtectedSandboxSpec,
    SandboxLimits,
    SandboxRequest,
)


IMAGE = "b" * 64


def _limits() -> SandboxLimits:
    return SandboxLimits(
        wall_time_ms=30_000,
        cpu_time_ms=20_000,
        memory_bytes=512_000_000,
        writable_bytes=64_000_000,
        process_count=16,
        stdout_bytes=1_000_000,
        stderr_bytes=1_000_000,
    )


def _configuration() -> DockerRunnerConfiguration:
    return DockerRunnerConfiguration(
        image_reference=f"example.invalid/plural-cognition@sha256:{IMAGE}"
    )


def _spec(configuration: DockerRunnerConfiguration) -> ProtectedSandboxSpec:
    return ProtectedSandboxSpec(
        runner_id=DOCKER_RUNNER_ID,
        runner_configuration_sha256=configuration.sha256,
        environment_image_sha256=configuration.environment_image_sha256,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=("python", "-m", "pytest", "-q"),
        environment=(
            ("PYTHONDONTWRITEBYTECODE", "1"),
            ("PYTHONHASHSEED", "0"),
        ),
        limits=_limits(),
    )


def _bundle(tmp_path: Path):
    store = FileContentStore(tmp_path / "store")
    repository_root = tmp_path / "repository-source"
    repository_root.mkdir()
    (repository_root / "module.py").write_bytes(b"VALUE = 1\n")
    repository = snapshot_directory(repository_root, store)
    submission_sha = store.put_bytes(b'{"submission":"visible"}')
    patch_sha = store.put_bytes(
        b"diff --git a/module.py b/module.py\n"
        b"--- a/module.py\n"
        b"+++ b/module.py\n"
        b"@@ -1 +1 @@\n"
        b"-VALUE = 1\n"
        b"+VALUE = 2\n"
    )
    runtime_sha = store.put_bytes(b'{"x":1}\n')
    configuration = _configuration()
    spec = _spec(configuration)
    request = SandboxRequest(
        task=TaskIdentity("rs-001", "repository-surgery-v0", "a" * 64),
        submission_sha256=submission_sha,
        buggy_repository_sha256=repository.manifest_sha256,
        patch_sha256=patch_sha,
        runtime_input_sha256=runtime_sha,
        sandbox_spec_sha256=spec.sha256,
    )
    bundle = prepare_docker_input_bundle(
        request=request,
        spec=spec,
        store=store,
        destination=tmp_path / "bundle",
    )
    return store, configuration, spec, request, bundle


def test_docker_configuration_requires_immutable_image_reference() -> None:
    with pytest.raises(ValueError, match="immutable"):
        DockerRunnerConfiguration(image_reference="python:3.11")


def test_docker_configuration_accepts_local_immutable_image_id() -> None:
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    assert configuration.environment_image_sha256 == IMAGE
    assert configuration.image_reference == f"sha256:{IMAGE}"


def test_docker_input_bundle_contains_only_candidate_execution_material(
    tmp_path: Path,
) -> None:
    _, _, _, request, bundle = _bundle(tmp_path)
    assert bundle.root.is_absolute()
    assert (bundle.root / "repository" / "module.py").read_bytes() == b"VALUE = 1\n"
    assert (bundle.root / "candidate.patch").read_bytes()
    assert (bundle.root / "runtime-input.bin").read_bytes() == b'{"x":1}\n'
    manifest = (bundle.root / "bundle-manifest.json").read_text(encoding="ascii")
    assert request.runtime_input_sha256 in manifest
    assert "expectation" not in manifest
    assert "protected_expectations" not in (
        bundle.root / "request.json"
    ).read_text(encoding="ascii")


def test_docker_command_plan_is_fail_closed_and_resource_bounded(
    tmp_path: Path,
) -> None:
    _, configuration, spec, _, bundle = _bundle(tmp_path)
    plan = build_docker_command_plan(
        spec=spec,
        configuration=configuration,
        input_bundle_directory=bundle.root,
        container_name="pc-rs-001",
    )
    argv = plan.create_argv

    assert argv[:2] == ("docker", "create")
    assert ("--pull", "never") == tuple(
        argv[argv.index("--pull") : argv.index("--pull") + 2]
    )
    assert ("--network", "none") == tuple(
        argv[argv.index("--network") : argv.index("--network") + 2]
    )
    assert ("--ipc", "none") == tuple(
        argv[argv.index("--ipc") : argv.index("--ipc") + 2]
    )
    assert "--read-only" in argv
    assert ("--cap-drop", "ALL") == tuple(
        argv[argv.index("--cap-drop") : argv.index("--cap-drop") + 2]
    )
    assert "no-new-privileges=true" in argv
    assert ("--pids-limit", "16") == tuple(
        argv[argv.index("--pids-limit") : argv.index("--pids-limit") + 2]
    )
    assert ("--memory", "512000000b") == tuple(
        argv[argv.index("--memory") : argv.index("--memory") + 2]
    )
    assert ("--memory-swap", "512000000b") == tuple(
        argv[argv.index("--memory-swap") : argv.index("--memory-swap") + 2]
    )
    assert ("--cpus", "0.666667") == tuple(
        argv[argv.index("--cpus") : argv.index("--cpus") + 2]
    )
    mount = argv[argv.index("--mount") + 1]
    assert "readonly" in mount
    assert "bind-propagation=rprivate" in mount
    assert "bind-recursive=readonly" in mount
    tmpfs = argv[argv.index("--tmpfs") + 1]
    assert tmpfs.startswith(configuration.workspace_target + ":")
    for token in (
        "rw",
        "noexec",
        "nosuid",
        "size=64000000",
        "mode=0700",
        f"uid={configuration.candidate_uid}",
        f"gid={configuration.candidate_gid}",
    ):
        assert token in tmpfs
    assert configuration.image_reference in argv
    assert plan.start_argv == ("docker", "start", "--attach", "pc-rs-001")
    assert plan.remove_argv == ("docker", "rm", "--force", "pc-rs-001")


def test_docker_command_plan_accepts_local_image_id(tmp_path: Path) -> None:
    _, _, _, _, bundle = _bundle(tmp_path)
    configuration = DockerRunnerConfiguration(image_reference=f"sha256:{IMAGE}")
    spec = _spec(configuration)
    plan = build_docker_command_plan(
        spec=spec,
        configuration=configuration,
        input_bundle_directory=bundle.root,
        container_name="pc-local-image",
    )
    assert f"sha256:{IMAGE}" in plan.create_argv
    assert plan.create_argv[plan.create_argv.index("--pull") + 1] == "never"


def test_docker_plan_rejects_spec_bound_to_different_configuration(
    tmp_path: Path,
) -> None:
    _, _, spec, _, bundle = _bundle(tmp_path)
    different = DockerRunnerConfiguration(
        image_reference=f"example.invalid/other@sha256:{IMAGE}"
    )
    with pytest.raises(ValueError, match="configuration"):
        build_docker_command_plan(
            spec=spec,
            configuration=different,
            input_bundle_directory=bundle.root,
            container_name="pc-rs-001",
        )


def test_docker_plan_rejects_incomplete_bundle(tmp_path: Path) -> None:
    configuration = _configuration()
    spec = _spec(configuration)
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    with pytest.raises(ValueError, match="incomplete"):
        build_docker_command_plan(
            spec=spec,
            configuration=configuration,
            input_bundle_directory=incomplete,
            container_name="pc-rs-001",
        )
