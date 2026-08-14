# Docker Protected-Runner Candidate

## Status

This document records the first concrete candidate adapter selected after the target-machine preflight.

It is **not a qualification claim** and it does **not** execute model-generated code yet.

The exact target-machine report at software revision `c61dd592f7e4c1993256f8656d8248298c400685` reported:

```text
docker: unavailable
windows-sandbox: unavailable
report_sha256=bf2cba61f05eb93a7686a2e68bf56d714b7ec63472b1e23853eee6b68a9de110
```

Therefore Repository Surgery execution remains paused. There is still no fallback to an ordinary host subprocess.

## 1. Why Docker is the first installation/qualification candidate

The protected sandbox contract requires explicit ceilings and isolation for:

```text
network
host filesystem access
process count
memory
CPU
writable storage
stdout / stderr
privilege
fresh workspace
environment identity
cleanup
```

Docker exposes native controls that map directly onto many of those requirements:

```text
--network none
--ipc none
--read-only
--cap-drop ALL
--security-opt no-new-privileges=true
--pids-limit
--memory
--memory-swap
--cpus
--pull never
read-only bind mounts
size-bounded tmpfs workspaces
```

Windows Sandbox remains a legitimate future backend, especially because it provides hypervisor-backed isolation, but its native configuration surface does not directly expose the complete process/CPU/writable-storage ceiling set frozen by `ProtectedSandboxSpec`. Selecting Docker here is therefore based on contract fit, not a claim that Docker is already present or secure enough.

Primary vendor references used for this candidate design:

- https://docs.docker.com/reference/cli/docker/container/run/
- https://docs.docker.com/engine/containers/run/
- https://docs.docker.com/engine/storage/bind-mounts/
- https://docs.docker.com/engine/storage/tmpfs/
- https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file

## 2. New candidate adapter

Implementation:

```text
src/plural_cognition/collective/docker_candidate.py
tests/test_collective_docker_candidate.py
```

The module deliberately contains **no `subprocess.run`, `Popen`, or Docker execution call**.

It adds three pieces.

### 2.1 Digest-pinned runner configuration

`DockerRunnerConfiguration` binds:

```text
runner id
OCI image reference pinned by @sha256:<digest>
platform
candidate UID / GID
input mount target
writable workspace target
bootstrap argv
```

Its SHA-256 must exactly equal `ProtectedSandboxSpec.runner_configuration_sha256`.

The image digest embedded in the image reference must exactly equal `ProtectedSandboxSpec.environment_image_sha256`.

Tags alone are rejected.

### 2.2 Candidate-visible input bundle

`prepare_docker_input_bundle(...)` materializes only the material required in the candidate execution domain:

```text
bundle-manifest.json
request.json
sandbox-spec.json
submission.json
repository/
candidate.patch
runtime-input.bin
```

The bundle contains the protected runtime input because the candidate must operate on it.

It does **not** accept or materialize:

```text
protected expectation
gold output
gold patch
grader configuration
promotion threshold
promotion decision
```

The repository snapshot and every content artifact are loaded through the existing SHA-256 content store.

### 2.3 Non-executing Docker command plan

`build_docker_command_plan(...)` produces deterministic argv vectors for later:

```text
docker create
docker start --attach
docker inspect
docker rm --force
```

The `docker create` plan currently requires:

```text
--pull never
--network none
--ipc none
--read-only
--cap-drop ALL
--security-opt no-new-privileges=true
--pids-limit <declared ceiling>
--memory <declared ceiling>
--memory-swap <same memory ceiling>
--memory-swappiness 0
--cpus <CPU/wall-time bandwidth ratio>
--restart no
--user <non-root uid:gid>
read-only recursively read-only candidate-input bind mount
size-bounded noexec/nosuid tmpfs workspace
```

The image is always referenced by digest.

The candidate command is not interpolated into a shell command. The future bootstrap reads the frozen request/spec files and executes the already-declared `command_argv` as an argv vector.

## 3. What this slice proves

It proves only software-level invariants:

```text
no protected expectation enters the Docker input bundle
runner configuration is content addressed
image identity is digest pinned
sandbox spec must bind the exact runner configuration and image
the generated Docker plan requests fail-closed isolation/resource flags
no container is started by unit tests
```

It does not prove that a particular Docker Engine actually honors those controls.

## 4. Remaining qualification gates

A real `DockerSandboxRunner` must not be introduced as qualified until the exact target machine passes adversarial tests for at least:

1. Docker CLI and Engine availability;
2. Linux-container mode and digest-pinned image availability with `--pull never`;
3. read-only recursive input mount enforcement;
4. inability to access unrelated host files;
5. no Docker socket or host credential exposure;
6. network denial, including DNS and local-network attempts;
7. process-count enforcement;
8. memory/OOM enforcement;
9. aggregate CPU-budget enforcement or a stronger replacement for the preliminary `--cpus` mapping;
10. bounded writable workspace with no alternate writable filesystem escape;
11. bounded stdout/stderr capture without host-memory amplification;
12. wall-time termination of the entire container process tree;
13. immutable environment-image identity;
14. deterministic patch application and runtime-input placement;
15. reliable exit/OOM/timeout/resource accounting;
16. complete forced cleanup after success, failure, timeout, or runner exception;
17. confirmation that candidate code never receives protected expectations or privileged grader state.

Any failed gate rejects the backend or forces a stricter implementation before benchmark execution.

## 5. Target-machine dependency

The next empirical dependency is now narrower:

```text
install / enable a supported Docker Desktop + Linux Engine on the target Windows host
        ↓
rerun plural-cognition-sandbox-preflight
        ↓
require docker == engine-available
        ↓
freeze exact engine + image identities
        ↓
add bootstrap and concrete runner
        ↓
execute adversarial containment/resource qualification
        ↓
only then execute Repository Surgery calibration tasks
```

Until `engine-available` is observed and the later adversarial qualification succeeds, the protected execution path remains blocked by design.
