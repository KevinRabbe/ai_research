"""Final project-authored bootstrap-parent interference probe.

The ordinary qualification matrix establishes containment and resource ceilings.
This probe separately tests that a candidate process cannot signal-kill the trusted
bootstrap parent inside the container PID namespace. The target-machine pass
criterion is deliberately strict: the kernel must deny SIGKILL with EPERM. If the
signal reaches the bootstrap, the normal runner fails closed and qualification is
rejected for investigation rather than accepting an ambiguous result.
"""

from __future__ import annotations

import errno
from typing import Any

from .docker_qualification_exec import canonical_probe_json, limits
from .docker_qualification_model import QualificationFailure
from .docker_qualification_probes import QualificationProbeDefinition
from .sandbox import SandboxResult


_PARENT_INTERFERENCE_SCRIPT = r'''
import json,os
target_pid=os.getppid()
signal_number=9
signal_errno=0
try:
    os.kill(target_pid,signal_number)
except OSError as exc:
    signal_errno=int(exc.errno or -1)
print(json.dumps({"target_pid":target_pid,"signal_number":signal_number,"signal_errno":signal_errno},sort_keys=True,separators=(",",":")))
'''.strip()


def _parent_interference_verifier(
    result: SandboxResult,
    stdout: bytes,
    stderr: bytes,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if result.exit_code != 0 or result.timed_out or result.memory_limit_exceeded or stderr:
        raise QualificationFailure(
            "bootstrap-parent interference probe did not complete cleanly"
        )
    payload = canonical_probe_json(stdout)
    if payload.get("target_pid") != 1:
        raise QualificationFailure(
            "candidate bootstrap parent is not PID 1 in the container namespace"
        )
    if payload.get("signal_number") != 9:
        raise QualificationFailure("bootstrap-parent probe did not attempt SIGKILL")
    if payload.get("signal_errno") != errno.EPERM:
        raise QualificationFailure(
            "candidate SIGKILL to bootstrap parent was not denied with EPERM"
        )
    return {
        "target_pid": 1,
        "signal_number": 9,
        "signal_errno": errno.EPERM,
        "kernel_denied_parent_sigkill": True,
    }


def parent_interference_probe_definition() -> QualificationProbeDefinition:
    """Return the final strict bootstrap-parent SIGKILL denial probe."""

    return QualificationProbeDefinition(
        name="bootstrap-parent-interference",
        command_argv=(
            "/usr/local/bin/python3",
            "-c",
            _PARENT_INTERFERENCE_SCRIPT,
        ),
        limits=limits(),
        verifier=_parent_interference_verifier,
    )
