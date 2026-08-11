# Protected Runner Bootstrap Image

## Status

This document freezes the first executable bootstrap and local qualification-image construction path for the Docker protected-runner candidate.

It is **not a containment qualification**. The bootstrap and Dockerfile may now be built into an immutable local image, but Repository Surgery candidate execution remains blocked until the resulting image and concrete runner pass the adversarial qualification matrix.

## 1. Frozen base identity

The exact target machine produced the following Docker identity at software revision `dc2053d9a8aa98cfea46c1100a2ec52a91964c97`:

```text
engine_sha256=d5443f020fcc2417fca4966c80e14152d29a5ca52e44b0ad7bd78506391cbc52
image_sha256=e342649066df3130e74875e977dc5c5d7fabd6f4df6485c5109af2fcac214137
environment_image_sha256=d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3
report_sha256=90796aad51d3cbc56dc2ca56493ff73a6ad9210619bfb1bba56ad49eb6b4f7e6
pinned_image=python@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3
```

The qualification Dockerfile therefore begins from that exact base repository digest rather than from a mutable Python tag.

## 2. Image recipe

The image recipe is:

```text
docker/protected-runner/Dockerfile
```

It contains no package-manager or network step. It copies exactly one stdlib-only bootstrap into the image and clears inherited entrypoint/command behavior.

The bootstrap source is:

```text
src/plural_cognition/collective/docker_bootstrap.py
```

The build should use the already-present digest-pinned base image and produce a local image tag only as a temporary human-readable handle. Qualification identity is the resulting immutable Docker image ID, not that tag.

## 3. Bootstrap execution domain

At container start, the bootstrap expects the candidate-visible input bundle at `/pc-input` and a fresh writable tmpfs at `/pc-work`.

The input bundle remains read-only and contains only:

```text
bundle-manifest.json
request.json
sandbox-spec.json
submission.json
repository/
candidate.patch
runtime-input.bin
```

Protected expectations, grader state, secret scores, promotion thresholds, and gold outputs are not accepted by the bootstrap.

The bootstrap:

```text
verify canonical request/spec/manifest bytes and SHA-256 bindings
verify submission / patch / runtime-input identities
recompute and verify the buggy repository snapshot identity
copy only regular repository files into the fresh workspace
apply the candidate patch in the workspace
recompute the patched repository identity
execute the frozen command_argv with runtime-input.bin as stdin
capture bounded stdout and stderr
read cgroup-v2 aggregate CPU usage and memory peak
emit one canonical JSON result envelope
```

The bootstrap does not contact the privileged grader.

## 4. Strict Repository Surgery v0 patch subset

The initial bootstrap intentionally accepts a narrower unified-diff subset than a general Git client.

Patchable files must be:

```text
UTF-8
LF line endings
regular files
trailing LF when non-empty
```

The bootstrap supports:

```text
modify file
create file
delete file
multiple files
multiple hunks
```

It rejects:

```text
absolute paths
parent traversal
backslash paths
colon-containing path components
rename patches
symlink traversal
binary patches
CRLF patch text
no-newline-at-EOF patch semantics
metadata-only mode changes
hunk coordinates or context that do not exactly match the source
multiple independent patches to the same path
```

This restriction is deliberate. Repository Surgery v0 generators must create benchmark repositories compatible with this frozen patch discipline rather than silently depending on host Git behavior.

## 5. Candidate execution protocol

The candidate command is taken only from the already-frozen `ProtectedSandboxSpec.command_argv` and is passed to `subprocess.Popen` as an argv vector with `shell=False`.

The candidate runs with:

```text
cwd = /pc-work/repository
stdin = /pc-work/runtime-input.bin
stdout = captured pipe
stderr = captured pipe
```

The bootstrap starts the candidate in a separate process group. On timeout or output-ceiling violation it kills that process group.

The surrounding Docker policy remains responsible for:

```text
network denial
read-only root filesystem
read-only input mount
capability drop
no-new-privileges
PID ceiling
memory ceiling
CPU bandwidth ceiling
writable tmpfs ceiling
non-root container identity
forced container cleanup
```

The bootstrap records aggregate cgroup-v2 `cpu.stat:usage_usec` delta and `memory.peak`. Those measurements still require empirical qualification on the exact target machine.

## 6. Result envelope

The bootstrap emits canonical JSON with schema:

```text
plural-cognition-docker-bootstrap-result-v1
```

A candidate result binds:

```text
request_sha256
patched_repository_sha256
exit_code
timed_out
stdout_limit_exceeded
stderr_limit_exceeded
stdout_base64
stderr_base64
wall_time_ms
cpu_time_ms
peak_memory_bytes
```

Bootstrap validation failures return `status=bootstrap-error` and exit code 125. The future host runner must treat malformed or absent envelopes as invalid execution, never as a successful candidate result.

## 7. Local image identity

A local Docker build normally has no registry `RepoDigests` entry. Requiring one would add a registry to the qualification trust path for no security benefit.

The local image therefore uses Docker's immutable content-addressed image ID:

```text
sha256:<image-id>
```

The non-starting identity probe is:

```text
python -m plural_cognition.collective.docker_local_image
```

It binds:

```text
software revision
requested local tag
immutable image ID
OS / architecture
image size
Dockerfile SHA-256
bootstrap SHA-256
```

No container is created or started by this probe.

## 8. Next gates

The next sequence is:

```text
build qualification image from exact base digest
        ↓
freeze local image ID + Dockerfile/bootstrap hashes
        ↓
allow DockerRunnerConfiguration to bind immutable local image IDs
        ↓
implement host-side DockerSandboxRunner envelope parsing / cleanup
        ↓
run only controlled adversarial qualification payloads
        ↓
verify filesystem/network/credential/process/memory/CPU/disk/output/time isolation
        ↓
QUALIFIED or REJECTED
        ↓
only if QUALIFIED: Repository Surgery candidate execution
```

No generated candidate patch is executed before that qualification decision.
