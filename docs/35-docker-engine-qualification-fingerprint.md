# Stable Docker Engine Qualification Fingerprint

## Why this exists

The first adversarial qualification attempt failed closed before creating a container because Docker Desktop on WSL2 reported a 12,288-byte change in `MemTotal` while every structural/security-relevant Engine field remained unchanged.

The exact Engine observation remains valuable evidence and continues to record `NCPU` and `MemTotal`. However, those capacity fields are not used as the binary identity gate for containment qualification because Docker Desktop/WSL2 can vary them without changing the Engine security surface.

## Two hashes

The project now distinguishes:

```text
engine_observation_sha256
```

This hashes the complete `DockerEngineIdentity`, including `ncpu` and `memory_bytes`.

```text
engine_qualification_sha256
```

This hashes the stable qualification surface:

- client/server version, API version, and Git commit;
- Docker Desktop platform identity;
- Linux OS/architecture/kernel identity;
- cgroup version and driver;
- Docker root directory;
- sorted Engine security options.

It deliberately excludes `ncpu` and `memory_bytes`.

## Why excluding capacity does not weaken the resource gate

The qualification matrix independently verifies the actual container resource controls on the target machine. It audits the applied Docker memory/PID/CPU settings before execution and empirically exercises memory OOM, PID exhaustion, writable tmpfs, CPU bandwidth, output, and wall-time limits.

Therefore:

```text
exact host capacity observation != containment identity
```

while:

```text
applied per-container resource controls + empirical limit probes = qualification evidence
```

A change in kernel, cgroup/security configuration, Engine/client versions, architecture, Docker root, or security options still changes the stable qualification fingerprint and fails closed before any qualification container starts.

## Current observed drift

The two non-starting observations differed only in:

```text
memory_bytes
16634265600 -> 16634277888
```

All stable qualification fields matched. Under the new fingerprint model those two observations therefore share the same `engine_qualification_sha256` while retaining distinct `engine_observation_sha256` values.

## Qualification report

The Docker runner qualification report schema is now:

```text
plural-cognition-docker-runner-qualification-v2
```

and binds both hashes so the exact observed capacity state remains auditable even though qualification uses the stable fingerprint as its pre-container gate.
