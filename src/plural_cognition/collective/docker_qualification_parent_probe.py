"""Final project-authored bootstrap-parent interference probe.

The ordinary qualification matrix establishes containment and resource ceilings.
This probe separately tests that a candidate process cannot terminate the trusted
bootstrap parent inside the container PID namespace. The candidate deliberately
attempts SIGKILL against its parent (which must be namespace PID 1). Qualification
passes only if the trusted bootstrap survives long enough to return a normal,
validated SandboxResult. Linux may report either EPERM or syscall success for the
attempt; the security property is bootstrap survival, not a specific errno. If
PID 1 actually terminates, the runner cannot produce the trusted result and the
probe fails closed.
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
    # Reaching this verifier with a clean SandboxResult is itself host-observed
    # evidence that trusted PID 1 survived: DockerSandboxRunner accepts a result
    # only after the bootstrap returns its canonical, request-bound envelope.
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
    signal_errno = payload.get("signal_errno")
    if signal_errno not in (0, errno.EPERM):
        raise QualificationFailure(
            "candidate SIGKILL to bootstrap parent produced unexpected errno"
        )
    return {
        "target_pid": 1,
        "signal_number": 9,
        "signal_errno": signal_errno,
        "signal_syscall_returned_success": signal_errno == 0,
        "kernel_reported_eperm": signal_errno == errno.EPERM,
        "trusted_bootstrap_result_returned": True,
        "bootstrap_survived_parent_sigkill_attempt": True,
    }


def parent_interference_probe_definition() -> QualificationProbeDefinition:
    """Return the final bootstrap-parent SIGKILL survival probe."""

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
