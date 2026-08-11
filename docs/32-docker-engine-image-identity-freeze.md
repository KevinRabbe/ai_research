# Docker Engine and OCI Image Identity Freeze

## Status

The target Windows machine has now passed the Docker **availability** gate, but Docker is still **not qualified** as the protected execution boundary.

Observed at repository revision:

```text
75a9fe72732a029bb6a16a5cdc3360dd65ae0dde
```

Target Docker state reported:

```text
Docker Desktop 4.86.0 (236216)
Docker client 29.7.2
Docker Engine 29.7.2
context desktop-linux
server linux/amd64
kernel 6.18.33.2-microsoft-standard-WSL2
cgroup v2
cgroup driver cgroupfs
builtin seccomp
cgroup namespace support
Docker root /var/lib/docker
```

The safe project preflight reported:

```text
docker: engine-available
windows-sandbox: unavailable
report_sha256=860e7f97e67b4d33fcc18132cbff5464beb535e9ad05d07c6eed8fd230c14ab4
```

This moves the project from backend installation to exact environment identity freeze.

## 1. Why a second identity artifact is required

`engine-available` proves only that the Docker CLI can reach a Linux Engine.

Protected execution must additionally bind the exact Engine and OCI image that are later subjected to containment tests. A mutable image tag such as:

```text
python:3.11.15-slim-bookworm
```

is therefore only a discovery handle. It is not an evaluation identity.

The frozen execution image must be represented by its registry digest:

```text
python@sha256:<64-hex-digest>
```

The image's local content-addressed image ID is recorded separately.

## 2. Non-starting identity probe

Implementation:

```text
src/plural_cognition/collective/docker_identity.py
tests/test_collective_docker_identity.py
```

The probe executes only:

```text
docker version --format ...
docker info --format ...
docker image inspect --format ...
```

It does **not** call:

```text
docker create
docker run
docker start
docker exec
```

and therefore does not execute repository or candidate code.

## 3. Frozen Engine identity

The Engine record binds:

```text
client version
client API version
client Git commit
server version
server API version
server Git commit
Docker platform name
OS type
architecture
kernel version
operating-system label
cgroup version
cgroup driver
Docker root directory
security options
CPU count
memory exposed to Docker
```

The canonical record receives its own SHA-256.

## 4. Frozen image identity

The image record binds:

```text
requested discovery reference
resolved repository digest reference
local image ID SHA-256
image OS
image architecture
image size
```

An image with no immutable `RepoDigests` entry is rejected by this qualification path.

The runner's later `environment_image_sha256` is the SHA-256 digest embedded in the frozen repository-digest reference.

## 5. Initial qualification image

Repository Surgery v0 is a Python-only task family. The initial qualification image should therefore remain deliberately small and contain no unnecessary agent, compiler, network, or Docker tooling.

The current discovery tag is:

```text
python:3.11.15-slim-bookworm
```

The tag is pulled only to discover and cache the exact platform image. The resulting repository digest, not the tag, becomes the frozen execution identity.

The image must be pulled for:

```text
linux/amd64
```

matching the target Docker Engine.

## 6. Target procedure

After updating the branch, the operator performs:

```powershell
docker pull --platform linux/amd64 python:3.11.15-slim-bookworm

$revision = git rev-parse HEAD

& '.\.venv\Scripts\python.exe' `
    -m plural_cognition.collective.docker_identity `
    --image 'python:3.11.15-slim-bookworm' `
    --software-revision $revision `
    --output 'artifacts\capable-collective\docker-qualification-identity.json'

Get-Content `
    -LiteralPath 'artifacts\capable-collective\docker-qualification-identity.json' `
    -Raw
```

The probe prints:

```text
engine_sha256=...
image_sha256=...
environment_image_sha256=...
report_sha256=...
pinned_image=python@sha256:...
```

Those values are recorded before the first containment test.

## 7. Qualification remains downstream

Successful identity freeze still does not qualify Docker.

The next sequence remains:

```text
engine available
      ✓
exact Engine identity
      ↓
exact OCI image digest
      ↓
bootstrap + concrete DockerSandboxRunner
      ↓
adversarial containment tests
      ↓
resource-limit tests
      ↓
forced-cleanup tests
      ↓
QUALIFIED or REJECTED
```

No protected Repository Surgery candidate may execute before that sequence succeeds.
