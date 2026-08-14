"""Raw-capability calibration with a resilient frozen-runtime provenance probe.

This wrapper preserves the v1 calibration protocol and evaluator semantics.  Its
only change is target-runtime observability: llama.cpp version/device probes are
allowed two bounded attempts so a transient Windows process-startup stall does
not get misclassified as a model/calibration failure.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Sequence

from . import local_raw_calibration as v1
from .local_model_load_preflight import RuntimeObservation
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2

RUNTIME_PROBE_TIMEOUT_SECONDS = 60
RUNTIME_PROBE_ATTEMPTS = 2
RUNTIME_PROBE_RETRY_DELAY_SECONDS = 2.0


def _run_probe(argv: list[str]) -> subprocess.CompletedProcess[str]:
    last_timeout: subprocess.TimeoutExpired | None = None
    for attempt in range(1, RUNTIME_PROBE_ATTEMPTS + 1):
        try:
            return subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=RUNTIME_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            last_timeout = exc
            print(
                f"runtime_probe_retry={attempt}/{RUNTIME_PROBE_ATTEMPTS} "
                f"command={Path(argv[0]).name} {argv[1]} reason=timeout",
                flush=True,
            )
            if attempt < RUNTIME_PROBE_ATTEMPTS:
                time.sleep(RUNTIME_PROBE_RETRY_DELAY_SECONDS)
    assert last_timeout is not None
    raise RuntimeError(
        f"runtime probe timed out after {RUNTIME_PROBE_ATTEMPTS} attempts: "
        f"{Path(argv[0]).name} {argv[1]}"
    ) from last_timeout


def _runtime_observation_resilient(cli: Path) -> RuntimeObservation:
    if not cli.is_file():
        raise RuntimeError(f"llama-cli is missing: {cli}")

    version = _run_probe([str(cli), "--version"])
    combined_version = (version.stdout + version.stderr).strip()
    if version.returncode != 0:
        raise RuntimeError(f"llama-cli --version failed: {combined_version}")
    runtime = LOCAL_MODEL_SOURCE_FREEZE_V2.runtime
    if (
        "version: 10361" not in combined_version
        or runtime.upstream_commit not in combined_version
    ):
        raise RuntimeError("llama-cli version does not match the frozen b10361 runtime")

    devices = _run_probe([str(cli), "--list-devices"])
    combined_devices = (devices.stdout + devices.stderr).strip()
    if devices.returncode != 0:
        raise RuntimeError(f"llama-cli --list-devices failed: {combined_devices}")
    if "CUDA0:" not in combined_devices:
        raise RuntimeError("frozen runtime did not expose CUDA0")
    return RuntimeObservation(combined_version, combined_devices)


def main(argv: Sequence[str] | None = None) -> int:
    # Process-local injection only.  Historical v1 source and evidence remain
    # unchanged; all model, parser, Docker, evaluator, and protocol behavior is
    # still implemented by the CI-qualified v1 calibration runner.
    v1._runtime_observation = _runtime_observation_resilient
    return v1.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
