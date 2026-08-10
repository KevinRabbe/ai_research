# Protected Sandbox Interface

## Status

This document freezes the evaluator execution boundary before any model-generated patch is executed.

The current implementation defines **contracts only**. It does not execute untrusted code and does not select a concrete container, VM, or sandbox technology.

## 1. Threat model

A capable coding model may intentionally or accidentally produce code that:

```text
reads unrelated host files
modifies files outside the task workspace
spawns excessive processes
consumes unbounded memory or CPU
opens network connections
inspects evaluator secrets
alters test infrastructure
persists beyond the evaluation
manipulates the score instead of repairing the task
```

Therefore a protected evaluator must treat every candidate patch and every resulting repository as untrusted.

## 2. Architectural boundary

The solver process never directly runs a submitted patch.

```text
solver
  ↓
immutable patch artifact
  ↓
protected evaluator
  ↓
SandboxRunner interface
  ↓
concrete isolated runtime (later)
```

The concrete runtime is intentionally replaceable.

The scientific contract is defined independently of Docker, a VM, an operating-system sandbox, or a remote execution service.

## 3. Frozen sandbox specification

A `ProtectedSandboxSpec` commits to:

```text
runner identity
runner configuration hash
environment image hash
network policy
argv command
environment variables
resource limits
```

The initial protected network policy is strictly:

```text
disabled
```

The command is represented as an argv vector rather than an interpolated shell command.

## 4. Resource limits

The common sandbox contract records ceilings for:

```text
wall time
CPU time
memory
writable bytes
process count
stdout bytes
stderr bytes
```

A concrete runner may enforce additional restrictions.

Those extra restrictions must be part of its configuration identity rather than remaining undocumented host behavior.

## 5. Protected request

A `SandboxRequest` binds:

```text
exact TaskIdentity
submission SHA-256
buggy repository snapshot SHA-256
patch SHA-256
hidden-test SHA-256
sandbox-spec SHA-256
```

The request belongs to the privileged evaluator domain because it contains the hidden-test identity.

It is never placed into a `MindRequest`.

## 6. Result

A `SandboxResult` binds:

```text
request SHA-256
exit code or timeout state
memory-limit state
stdout SHA-256
stderr SHA-256
resource ledger
```

Stdout and stderr bytes are stored separately through the content-addressed store.

This keeps arbitrarily large logs outside the result manifest while preserving exact evidence.

## 7. Required properties of a future concrete runner

A concrete `SandboxRunner` is not qualified until it demonstrates at minimum:

1. a fresh workspace for every evaluation;
2. no access to the solver process filesystem outside explicitly mounted immutable inputs;
3. no network access for Repository Surgery v0;
4. no inherited user credentials, API keys, Git credentials, or repository secrets;
5. enforceable CPU, memory, process, wall-time, writable-disk, and output ceilings;
6. deterministic environment-image identity;
7. explicit capture of stdout, stderr, exit status, and resource use;
8. complete workspace destruction after evaluation;
9. no ability for submitted code to modify the hidden evaluator or promotion records;
10. failure-closed behavior when the sandbox cannot enforce its declared policy.

## 8. Why there is no local executor yet

A normal subprocess, virtual environment, or temporary directory is useful for reproducibility but is **not** by itself a security boundary against untrusted model-generated code.

The repository therefore does not add a convenience host executor merely to make early benchmark runs easier.

The evaluator interface is qualified first. A concrete isolated implementation is selected only after its containment properties can be measured on the target machine.

## 9. Relation to capability attribution

Sandboxing is evaluator infrastructure, not a source of cognitive uplift.

Its resource use is recorded separately from:

```text
raw mind inference
plural synthesis
harness execution
verification reasoning
```

A slower or more restrictive sandbox must not be mistaken for a change in collective intelligence.

## 10. Current implementation

```text
src/plural_cognition/collective/sandbox.py
tests/test_collective_sandbox.py
```

The code currently provides:

```text
NetworkPolicy
SandboxLimits
ProtectedSandboxSpec
SandboxRequest
SandboxResult
SandboxRunner protocol
```

It contains no `subprocess` call and no concrete execution backend.

## 11. Next step

After this interface qualifies, the project can implement and test one concrete isolated runner appropriate to the target machine.

Only after that runner passes containment and deterministic-execution tests should Repository Surgery task generation proceed to actual execution-based calibration.
