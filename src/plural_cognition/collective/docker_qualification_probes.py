"""Deterministic project-authored probes for Docker runner qualification."""

from __future__ import annotations

import errno
from dataclasses import dataclass
from typing import Any

from .docker_qualification_exec import Verifier, canonical_probe_json, limits
from .docker_qualification_model import QualificationFailure
from .sandbox import SandboxLimits, SandboxResult

_REQUIRED_INPUT_ENTRIES = (
    "bundle-manifest.json",
    "candidate.patch",
    "repository",
    "request.json",
    "runtime-input.bin",
    "sandbox-spec.json",
    "submission.json",
)
_FORBIDDEN_ENVIRONMENT_NAMES = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AZURE_CLIENT_SECRET",
    "DOCKER_HOST",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY",
    "SSH_AUTH_SOCK",
)


@dataclass(frozen=True, slots=True)
class QualificationProbeDefinition:
    name: str
    command_argv: tuple[str, ...]
    limits: SandboxLimits
    verifier: Verifier


def _baseline_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 7 or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure("baseline exit/termination capture mismatch")
    if stdout != b"qualification-stdout\n" or stderr != b"qualification-stderr\n":
        raise QualificationFailure("baseline stdout/stderr capture mismatch")
    return {
        "exit_code": result.exit_code,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


_ISOLATION_SCRIPT = r'''
import json,os
from pathlib import Path

def write_errno(path):
    try:
        Path(path).write_bytes(b"x")
        return 0
    except OSError as exc:
        return int(exc.errno or -1)

status={}
for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
    if line.startswith("CapEff:"):
        status["cap_eff"]=line.split(":",1)[1].strip()
    elif line.startswith("NoNewPrivs:"):
        status["no_new_privs"]=int(line.split(":",1)[1].strip())
secrets=Path("/run/secrets")
payload={
    "uid":os.getuid(),
    "gid":os.getgid(),
    "cap_eff":status.get("cap_eff"),
    "no_new_privs":status.get("no_new_privs"),
    "root_write_errno":write_errno("/qualification-root-write"),
    "input_write_errno":write_errno("/pc-input/runtime-input.bin"),
    "input_entries":sorted(item.name for item in Path("/pc-input").iterdir()),
    "runtime_entries":sorted(item.name for item in Path("/opt/plural-cognition").iterdir()),
    "environment_names":sorted(os.environ),
    "docker_socket_exists":Path("/var/run/docker.sock").exists() or Path("/run/docker.sock").exists(),
    "secret_entries":sorted(item.name for item in secrets.iterdir()) if secrets.exists() else [],
    "root_docker_config_exists":Path("/root/.docker/config.json").exists(),
    "root_gitconfig_exists":Path("/root/.gitconfig").exists(),
    "root_ssh_exists":Path("/root/.ssh").exists(),
}
print(json.dumps(payload,sort_keys=True,separators=(",",":")))
'''.strip()


def _isolation_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("isolation-surface candidate did not complete cleanly")
    payload = canonical_probe_json(stdout)
    if payload.get("uid") != 65534 or payload.get("gid") != 65534:
        raise QualificationFailure("candidate did not run as nobody:nogroup identity")
    if payload.get("cap_eff") != "0000000000000000" or payload.get("no_new_privs") != 1:
        raise QualificationFailure(
            "candidate retained capabilities or lacks no-new-privileges"
        )
    if payload.get("root_write_errno") == 0 or payload.get("input_write_errno") == 0:
        raise QualificationFailure(
            "candidate could write rootfs or immutable input mount"
        )
    if payload.get("input_entries") != list(_REQUIRED_INPUT_ENTRIES):
        raise QualificationFailure(
            "candidate input surface differs from frozen allow-list"
        )
    if payload.get("runtime_entries") != ["bootstrap.py", "bootstrap_core.py"]:
        raise QualificationFailure(
            "candidate runtime contains unexpected project files"
        )
    env_names = payload.get("environment_names")
    if type(env_names) is not list:
        raise QualificationFailure("candidate environment-name evidence is malformed")
    leaked = sorted(set(env_names).intersection(_FORBIDDEN_ENVIRONMENT_NAMES))
    if leaked:
        raise QualificationFailure(
            "candidate inherited forbidden credential environment names"
        )
    if payload.get("docker_socket_exists"):
        raise QualificationFailure("candidate can see a Docker socket")
    if payload.get("secret_entries"):
        raise QualificationFailure("candidate can see mounted runtime secrets")
    if (
        payload.get("root_docker_config_exists")
        or payload.get("root_gitconfig_exists")
        or payload.get("root_ssh_exists")
    ):
        raise QualificationFailure(
            "candidate image exposes root credential/config material"
        )
    return {
        "uid": payload["uid"],
        "gid": payload["gid"],
        "cap_eff": payload["cap_eff"],
        "no_new_privs": payload["no_new_privs"],
        "root_write_errno": payload["root_write_errno"],
        "input_write_errno": payload["input_write_errno"],
        "input_entry_count": len(payload["input_entries"]),
        "forbidden_environment_name_count": len(leaked),
        "docker_socket_exists": False,
        "secret_entry_count": 0,
    }


_NETWORK_SCRIPT = r'''
import json,socket
from pathlib import Path
interfaces=sorted(item.name for item in Path("/sys/class/net").iterdir())
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.settimeout(1.0)
try:
    connect_errno=s.connect_ex(("1.1.1.1",53))
finally:
    s.close()
print(json.dumps({"interfaces":interfaces,"connect_errno":connect_errno},sort_keys=True,separators=(",",":")))
'''.strip()


def _network_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("network probe did not complete cleanly")
    payload = canonical_probe_json(stdout)
    if payload.get("interfaces") != ["lo"]:
        raise QualificationFailure(
            "network-none container exposes non-loopback interface"
        )
    connect_errno = payload.get("connect_errno")
    if type(connect_errno) is not int or connect_errno == 0:
        raise QualificationFailure("external IPv4 connect unexpectedly succeeded")
    return payload


_FRESH_SCRIPT = r'''
import json
from pathlib import Path
marker=Path("/pc-work/qualification-persistence-marker")
preexisting=marker.exists()
marker.write_bytes(b"marker")
print(json.dumps({"preexisting":preexisting},sort_keys=True,separators=(",",":")))
'''.strip()


def _fresh_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("fresh-workspace probe did not complete cleanly")
    payload = canonical_probe_json(stdout)
    if payload.get("preexisting") is not False:
        raise QualificationFailure("fresh workspace contained persistence marker")
    return payload


def _timeout_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not result.timed_out or result.exit_code is not None or result.memory_limit_exceeded:
        raise QualificationFailure(
            "wall-time ceiling did not produce timeout result"
        )
    return {"wall_time_ms": result.resources.wall_time_ms}


def _stdout_limit_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code is not None or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure(
            "stdout overflow termination classification mismatch"
        )
    if len(stdout) != 4096 or stderr:
        raise QualificationFailure(
            "stdout ceiling did not preserve exactly the declared bound"
        )
    return {"captured_stdout_bytes": len(stdout)}


def _stderr_limit_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code is not None or result.timed_out or result.memory_limit_exceeded:
        raise QualificationFailure(
            "stderr overflow termination classification mismatch"
        )
    if len(stderr) != 4096 or stdout:
        raise QualificationFailure(
            "stderr ceiling did not preserve exactly the declared bound"
        )
    return {"captured_stderr_bytes": len(stderr)}


_MEMORY_SCRIPT = "x=bytearray(1024*1024*1024);print(len(x))"


def _memory_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if not result.memory_limit_exceeded or result.timed_out:
        raise QualificationFailure(
            "memory pressure did not produce explicit OOM evidence"
        )
    if result.resources.peak_ram_bytes <= 0:
        raise QualificationFailure("memory probe lacks peak-memory accounting")
    return {
        "memory_limit_exceeded": True,
        "peak_ram_bytes": result.resources.peak_ram_bytes,
        "candidate_exit_code": result.exit_code,
    }


_PIDS_SCRIPT = r'''
import json,subprocess,sys
from pathlib import Path

def event_max():
    values={}
    for line in Path("/sys/fs/cgroup/pids.events").read_text(encoding="ascii").splitlines():
        key,value=line.split(maxsplit=1)
        values[key]=int(value)
    return values.get("max",0)

before=event_max()
children=[]
failure_errno=0
try:
    for _ in range(64):
        try:
            children.append(subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        except OSError as exc:
            failure_errno=int(exc.errno or -1)
            break
finally:
    after=event_max()
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=1)
print(json.dumps({"started":len(children),"failure_errno":failure_errno,"max_event_delta":after-before},sort_keys=True,separators=(",",":")))
'''.strip()


def _pids_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("PID probe did not complete cleanly")
    payload = canonical_probe_json(stdout)
    if payload.get("failure_errno") != errno.EAGAIN:
        raise QualificationFailure("PID exhaustion did not fail with EAGAIN")
    max_event_delta = payload.get("max_event_delta")
    if type(max_event_delta) is not int or max_event_delta < 1:
        raise QualificationFailure(
            "cgroup pids.events did not record limit enforcement"
        )
    started = payload.get("started")
    if type(started) is not int or started >= 64:
        raise QualificationFailure(
            "PID probe unexpectedly spawned all requested children"
        )
    return payload


_WRITABLE_SCRIPT = r'''
import json,os
path="/pc-work/qualification-fill.bin"
fd=os.open(path,os.O_CREAT|os.O_WRONLY,0o600)
written=0
failure_errno=0
chunk=b"x"*(1024*1024)
try:
    while written < 64*1024*1024:
        try:
            written += os.write(fd,chunk)
        except OSError as exc:
            failure_errno=int(exc.errno or -1)
            break
finally:
    os.close(fd)
print(json.dumps({"written":written,"failure_errno":failure_errno},sort_keys=True,separators=(",",":")))
'''.strip()


def _writable_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("writable-space probe did not complete cleanly")
    payload = canonical_probe_json(stdout)
    if payload.get("failure_errno") != errno.ENOSPC:
        raise QualificationFailure(
            "tmpfs writable-space exhaustion did not fail with ENOSPC"
        )
    written = payload.get("written")
    if type(written) is not int or written <= 0 or written > 8_388_608:
        raise QualificationFailure(
            "tmpfs wrote beyond declared writable-space ceiling"
        )
    return payload


_CPU_SCRIPT = r'''
import json,time
start=time.monotonic()
deadline=start+2.0
value=0
while time.monotonic()<deadline:
    value=(value*1664525+1013904223)&0xffffffff
elapsed_ms=int((time.monotonic()-start)*1000)
print(json.dumps({"elapsed_ms":elapsed_ms,"value":value},sort_keys=True,separators=(",",":")))
'''.strip()


def _cpu_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure("CPU-bandwidth probe did not complete cleanly")
    payload = canonical_probe_json(stdout)
    elapsed = payload.get("elapsed_ms")
    if type(elapsed) is not int or elapsed < 1_800:
        raise QualificationFailure(
            "CPU probe did not run for the intended wall interval"
        )
    if result.resources.cpu_time_ms >= 1_400:
        raise QualificationFailure(
            "observed CPU time is inconsistent with the 0.25 CPU bandwidth ceiling"
        )
    if audit.get("nano_cpus") != 250_000_000:
        raise QualificationFailure("Docker did not apply exact 0.25 NanoCpus limit")
    return {
        "candidate_elapsed_ms": elapsed,
        "observed_cpu_time_ms": result.resources.cpu_time_ms,
        "observed_wall_time_ms": result.resources.wall_time_ms,
        "nano_cpus": audit.get("nano_cpus"),
    }


def qualification_probe_definitions() -> tuple[QualificationProbeDefinition, ...]:
    python = "/usr/local/bin/python3"
    return (
        QualificationProbeDefinition(
            name="result-capture-and-policy",
            command_argv=(
                python,
                "-c",
                "import sys;sys.stdout.write('qualification-stdout\\n');sys.stderr.write('qualification-stderr\\n');raise SystemExit(7)",
            ),
            limits=limits(),
            verifier=_baseline_verifier,
        ),
        QualificationProbeDefinition(
            name="isolation-surface",
            command_argv=(python, "-c", _ISOLATION_SCRIPT),
            limits=limits(),
            verifier=_isolation_verifier,
        ),
        QualificationProbeDefinition(
            name="network-denial",
            command_argv=(python, "-c", _NETWORK_SCRIPT),
            limits=limits(),
            verifier=_network_verifier,
        ),
        QualificationProbeDefinition(
            name="fresh-workspace-a",
            command_argv=(python, "-c", _FRESH_SCRIPT),
            limits=limits(),
            verifier=_fresh_verifier,
        ),
        QualificationProbeDefinition(
            name="fresh-workspace-b",
            command_argv=(python, "-c", _FRESH_SCRIPT),
            limits=limits(),
            verifier=_fresh_verifier,
        ),
        QualificationProbeDefinition(
            name="wall-time-ceiling",
            command_argv=(python, "-c", "import time;time.sleep(10)"),
            limits=limits(wall=500, cpu=500),
            verifier=_timeout_verifier,
        ),
        QualificationProbeDefinition(
            name="stdout-ceiling",
            command_argv=(python, "-c", "import os;os.write(1,b'x'*8192)"),
            limits=limits(stdout=4096),
            verifier=_stdout_limit_verifier,
        ),
        QualificationProbeDefinition(
            name="stderr-ceiling",
            command_argv=(python, "-c", "import os;os.write(2,b'x'*8192)"),
            limits=limits(stderr=4096),
            verifier=_stderr_limit_verifier,
        ),
        QualificationProbeDefinition(
            name="memory-oom-ceiling",
            command_argv=(python, "-c", _MEMORY_SCRIPT),
            limits=limits(memory=134_217_728, wall=8_000, cpu=8_000),
            verifier=_memory_verifier,
        ),
        QualificationProbeDefinition(
            name="process-count-ceiling",
            command_argv=(python, "-c", _PIDS_SCRIPT),
            limits=limits(processes=8, wall=8_000, cpu=8_000),
            verifier=_pids_verifier,
        ),
        QualificationProbeDefinition(
            name="writable-space-ceiling",
            command_argv=(python, "-c", _WRITABLE_SCRIPT),
            limits=limits(writable=8_388_608, wall=8_000, cpu=8_000),
            verifier=_writable_verifier,
        ),
        QualificationProbeDefinition(
            name="cpu-bandwidth-ceiling",
            command_argv=(python, "-c", _CPU_SCRIPT),
            limits=limits(wall=4_000, cpu=1_000),
            verifier=_cpu_verifier,
        ),
    )
