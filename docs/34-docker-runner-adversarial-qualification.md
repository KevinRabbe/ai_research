# Docker Runner Adversarial Qualification

## Status

This document defines the first target-machine execution phase for the protected Docker runner.

Unlike the earlier preflight, identity-freeze, command-plan, bootstrap, and mocked-runner layers, this phase **does start containers**. It executes only deterministic project-authored qualification probes. It does not execute model-generated patches and does not expose protected expectations, grader state, scores, or promotion state to the container.

A successful run qualifies only the exact tuple bound into its immutable report:

```text
Repository Surgery v0 scope
+ Docker Engine fingerprint
+ immutable local runner image ID
+ Docker runner configuration hash
+ sandbox-contract hash
+ qualification-source hash
+ Dockerfile hash
+ bootstrap guard hash
+ frozen bootstrap core hash
+ software revision
```

It is not a general claim that Docker or Docker Desktop is secure for arbitrary workloads or machines.

## Frozen target identities before qualification

The target machine previously produced:

```text
engine_sha256=
d5443f020fcc2417fca4966c80e14152d29a5ca52e44b0ad7bd78506391cbc52
```

The OOM-aware v2 protected-runner image was then built and frozen as:

```text
immutable_image=
sha256:b6b32c4c224d190ff281853aafe6e6d57d0361a32dc7ba11076af6e18892b139

bootstrap_core_sha256=
7e24fd1cbe8294e0a1be90f33b18e2b6aa3f5d79fbb907aed7949d8253c10b86

bootstrap_guard_sha256=
c97645c9f45f466bcf755e71b29297fa20aec2904a574cb64c61cca7633669d8

dockerfile_sha256=
6cb051db0e2a697fe0f41689d5dce9b9bd4bdaa702d0bafa5c5a9b426809a1e8
```

The qualification CLI fails before starting probes if the current Engine fingerprint no longer matches the frozen Engine identity.

## Qualification matrix

The matrix contains twelve executions:

1. `result-capture-and-policy`
   - verifies exit code, stdout, stderr, resource capture;
   - audits Docker's applied create-time policy before candidate execution.

2. `isolation-surface`
   - requires non-root UID/GID;
   - zero effective capabilities;
   - `NoNewPrivs=1`;
   - root filesystem write failure;
   - immutable input write failure;
   - exact candidate-visible input allow-list;
   - no Docker socket;
   - no mounted runtime secrets;
   - no common inherited credential environment names;
   - no root Docker/Git/SSH credential material.

3. `network-denial`
   - requires the container to expose only loopback;
   - requires an external IPv4 connection attempt to fail.

4-5. `fresh-workspace-a` / `fresh-workspace-b`
   - each execution checks that a previous workspace marker is absent before creating one;
   - every run must also leave no container or staging residue.

6. `wall-time-ceiling`
   - deliberately exceeds the wall-time limit;
   - requires an explicit timeout result and cleanup.

7. `stdout-ceiling`
   - deliberately exceeds stdout capacity;
   - requires exactly bounded captured output and non-success termination classification.

8. `stderr-ceiling`
   - same for stderr.

9. `memory-oom-ceiling`
   - deliberately exceeds the cgroup memory ceiling;
   - requires explicit cgroup-v2 `oom_kill` evidence propagated through the trusted bootstrap and `SandboxResult`.

10. `process-count-ceiling`
    - deliberately attempts to exceed the PID cgroup ceiling;
    - requires `EAGAIN` and a positive `pids.events:max` delta.

11. `writable-space-ceiling`
    - deliberately fills the bounded `/pc-work` tmpfs;
    - requires `ENOSPC` before exceeding the declared writable-byte ceiling.

12. `cpu-bandwidth-ceiling`
    - requests exactly 0.25 CPU through the frozen CPU/wall-time ratio;
    - verifies Docker's applied `NanoCpus` setting and empirically checks that CPU usage remains substantially below an unthrottled two-second busy loop.

## Applied-policy audit

For every created container, the qualification executor performs a trusted host-side `docker inspect` before start and records only sanitized policy fields. The report rejects a container unless the applied configuration includes:

```text
network=none
ipc=none
not privileged
read-only root filesystem
non-host PID/cgroup namespaces
exact non-root user
all capabilities dropped
no-new-privileges
exact PID limit
exact memory and no-extra-swap limit
exact CPU quota
restart disabled
no devices/device requests
no published ports
exactly one host bind: /pc-input, read-only
bounded noexec/nosuid /pc-work tmpfs
no unexpected mounts
```

Host bind source paths are deliberately not copied into the report.

## Cleanup rule

Every probe is followed by two independent cleanup checks:

```text
Docker container name-prefix query -> zero stale containers
runner staging root              -> zero entries
```

The concrete runner itself also performs unconditional `docker rm --force` in its `finally` path. A cleanup failure rejects qualification.

## Report semantics

The canonical report schema is:

```text
plural-cognition-docker-runner-qualification-v1
```

The report status is exactly:

```text
QUALIFIED
```

only when every recorded probe passes. One failed probe yields:

```text
REJECTED
```

The CLI returns exit code `0` only for `QUALIFIED`; `REJECTED` returns nonzero.

Candidate stdout/stderr evidence remains content-addressed in the qualification evidence store. The report contains their immutable SHA-256 references through each `SandboxResult` rather than embedding arbitrary output bytes.

## Target-machine command

After pulling the branch and passing the non-container unit/full test suites:

```powershell
$revision = git rev-parse HEAD
$image = 'sha256:b6b32c4c224d190ff281853aafe6e6d57d0361a32dc7ba11076af6e18892b139'
$engine = 'd5443f020fcc2417fca4966c80e14152d29a5ca52e44b0ad7bd78506391cbc52'

& $python -m plural_cognition.collective.docker_qualification `
    --image $image `
    --software-revision $revision `
    --expected-engine-sha256 $engine `
    --evidence-root 'artifacts\capable-collective\docker-qualification-v1-evidence' `
    --output 'artifacts\capable-collective\docker-qualification-v1.json'
```

The evidence-root path must be absent or empty. This is deliberate: reruns must not silently mix evidence from different qualification attempts.

## Promotion gate

Even a `QUALIFIED` report does not score a Repository Surgery task by itself. It only clears the isolated-execution infrastructure gate for the exact qualified Engine/image/configuration/revision tuple.

The next phase after qualification is controlled Repository Surgery calibration using deterministic project-authored task material. Capable-model-generated patches remain downstream of that calibration and protected evaluator review.
