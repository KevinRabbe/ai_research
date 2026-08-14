# Sandbox Runner Preflight

## Status

This preflight determines which protected-execution backends are available on the exact target machine **without starting a sandbox, container, or untrusted process**.

Availability is not qualification.

A backend must still satisfy the protected sandbox contract before Repository Surgery executes model-generated patches.

## 1. Installed command

```text
plural-cognition-sandbox-preflight
```

Equivalent module invocation:

```powershell
.\.venv\Scripts\python.exe -m plural_cognition.collective.sandbox_preflight `
  --output artifacts\capable-collective\sandbox-preflight.json
```

The command is safe to run while no benchmark is active because it performs only executable discovery and vendor-supported information/help commands.

It does not launch:

```text
a Docker container
a Windows Sandbox session
candidate code
protected tests
```

## 2. Docker probe

The preflight checks:

```text
is the docker CLI on PATH?
can docker version reach the Engine?
can docker info return system information?
```

When the Engine is reachable, the report records selected information such as:

```text
client/server version
OS type
operating system
architecture
kernel version
cgroup driver
security options
Docker root directory
```

The commands are based on Docker's supported JSON formatting:

- https://docs.docker.com/reference/cli/docker/version/
- https://docs.docker.com/reference/cli/docker/system/info/

No container is created by the preflight.

A later Docker runner may use controls such as:

```text
--network none
--read-only
--pids-limit
--memory
--cpus
--cap-drop
--security-opt no-new-privileges
--rm
```

but those controls are part of the **future concrete-runner qualification**, not this availability probe.

Relevant Docker references:

- https://docs.docker.com/reference/cli/docker/container/run
- https://docs.docker.com/reference/cli/docker/container/create/
- https://docs.docker.com/engine/containers/run/

## 3. Windows Sandbox probe

On Windows, the preflight checks whether the `wsb` command is available and executes only:

```text
wsb --help
```

The help output is hashed and inspected for the documented automation command tokens:

```text
start
exec
share
```

The preflight does **not** invoke those commands.

Microsoft documents the Windows Sandbox CLI beginning with Windows 11 version 24H2, including `start`, `exec`, `share`, and `stop` operations:

- https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-cli

If the CLI is absent, the automated Windows Sandbox runner is considered unavailable for the current protocol even if some older/manual Windows Sandbox installation exists.

## 4. Status values

A backend probe may return:

```text
not-applicable
unavailable
cli-available
engine-available
error
```

Interpretation:

### `not-applicable`

The backend does not apply to the current host platform.

### `unavailable`

The required CLI executable was not found.

### `cli-available`

The CLI exists, but the preflight has not established a usable execution engine.

For Docker this can mean the CLI exists while the daemon is unreachable.

For Windows Sandbox this is the maximum status of the non-starting preflight: the CLI is automatable, but no sandbox has been launched to test containment.

### `engine-available`

Currently used only when Docker CLI and Engine introspection both succeed.

This still does not mean the Docker configuration has passed the project's security contract.

### `error`

A supposedly available backend failed its safe help/introspection command.

## 5. Machine-readable report

The report binds:

```text
schema
project software revision
platform system/release/version
machine architecture
ordered backend probes
```

It is canonical JSON and receives its own SHA-256 identity.

The exact report should be preserved as an artifact before selecting a concrete runner.

## 6. Decision rule after preflight

Do not select a concrete runner merely by preference.

Use this sequence:

```text
safe availability preflight
        ↓
identify candidate backends
        ↓
implement one candidate adapter
        ↓
containment / resource / reproducibility tests
        ↓
qualify or reject
```

If multiple backends are available, prefer the one that can most cleanly satisfy:

```text
no network
no host secrets
fresh workspace
immutable inputs
protected expectations absent
resource ceilings
process ceilings
bounded output
deterministic environment identity
complete cleanup
```

The decision must be recorded rather than inferred from the backend name.

## 7. No fallback to ordinary subprocess

If no isolated backend qualifies, Repository Surgery execution pauses.

The project must not silently fall back to:

```text
subprocess on the host
Python venv only
temporary directory only
```

Those mechanisms may provide reproducibility but do not satisfy the declared containment boundary for untrusted model-generated code.

## 8. Next target-machine action

After this code is CI-qualified, run the preflight once on the target Windows machine and preserve the resulting JSON artifact.

That empirical report determines which concrete runner should be implemented next.
