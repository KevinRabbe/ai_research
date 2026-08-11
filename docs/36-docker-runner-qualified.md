# Docker Protected Runner — Qualified Target Binding

## Status

The Repository Surgery v0 Docker runner is **QUALIFIED** for the exact target-machine binding recorded here.

This is a narrow promotion claim. It does not assert that Docker is universally secure, that other machines are qualified, or that arbitrary runner/image/source changes inherit qualification.

Protected execution must fail closed if the bound runner source hash or stable Engine qualification fingerprint drifts.

## Final v10 qualification

The final hardened target-machine run executed at runner-source revision:

```text
8d201c685ecf73917a073093bb057a2178f59d6f
```

It produced:

```text
status=QUALIFIED
qualification_exit=0
report_sha256=2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04
engine_observation_sha256=d5443f020fcc2417fca4966c80e14152d29a5ca52e44b0ad7bd78506391cbc52
engine_qualification_sha256=8155c7193395faaa6096032249b179926381f069343589f5c40e2ac3f4c14000
image_identity_sha256=eb83cb008705c1b4d744f8c3cd44839e0660bc8565d4b7895f6ba12146d7fc75
immutable_image=sha256:b6b32c4c224d190ff281853aafe6e6d57d0361a32dc7ba11076af6e18892b139
qualification_source_sha256=1a361fee3ba74ba1b85d7d249ced89b624d9d58a907f95bde34d7f24730782e3
runner_configuration_sha256=92c30ff08bff86cac4a584d69d2845a5d7f2b6baf1446d2fe2299aa15d1f39a0
```

The stable Engine fingerprint is the promotion identity. The exact Engine observation remains preserved as evidence but may vary in capacity-only fields that are deliberately excluded from the structural/security fingerprint.

## Adversarial matrix

All thirteen project-authored probes passed:

```text
result-capture-and-policy        PASS
isolation-surface                PASS
network-denial                   PASS
fresh-workspace-a                PASS
fresh-workspace-b                PASS
wall-time-ceiling                PASS
stdout-ceiling                   PASS
stderr-ceiling                   PASS
memory-oom-ceiling               PASS
process-count-ceiling            PASS
writable-space-ceiling           PASS
cpu-bandwidth-ceiling            PASS
bootstrap-parent-interference    PASS
```

The final applied-policy audit also explicitly verified:

```text
workspace tmpfs writable         true
workspace tmpfs mode=0700        true
workspace tmpfs uid/gid=65534    true
bounded tmpfs size               true
noexec                           true
nosuid                           true
```

The parent-interference probe deliberately issued `SIGKILL` to namespace PID 1 from candidate code. The syscall returned success, but the trusted bootstrap survived, completed candidate-result capture, and returned the validated result envelope. An actual bootstrap/container death remains a fail-closed runner error.

## Cleanup

Every qualification probe verified zero staging residue and zero stale candidate containers. The final target command also returned no entries for:

```text
docker ps -a --filter name=pc-
```

## Executable promotion binding

`src/plural_cognition/collective/qualified_docker.py` records the immutable promotion tuple.

Protected callers obtain their `DockerRunnerConfiguration` through that binding. Before returning it, the binding requires:

```text
current qualification-source SHA == v10 qualified source SHA
current runner-configuration SHA  == v10 qualified configuration SHA
live stable Engine fingerprint     == v10 qualified Engine fingerprint
```

The live Engine check uses Docker version/info/image-inspect diagnostics only and does not start a container.

The underlying `docker_runner.py` is intentionally left unchanged after v10 so the exact containment implementation that passed qualification remains the implementation used by downstream protected execution.

## Promotion decision

The protected Docker infrastructure gate is cleared for the bound tuple above.

The next research dependency is no longer sandbox qualification. It is controlled Repository Surgery calibration:

```text
project-authored deterministic task
        ↓
qualified Docker runner
        ↓
protected runtime observations
        ↓
privileged black-box grading
        ↓
validate buggy baseline fails and gold repair passes
        ↓
expand calibration task set
        ↓
freeze selection set
        ↓
capable-model bakeoff
```

There remains no host-subprocess, Python-venv-only, or temporary-directory-only fallback security boundary.
