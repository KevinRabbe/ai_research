"""V9 calibration: one bounded Gemma-only generation-budget adjustment.

V8 established a usable structured-edit protocol: every non-Gemma candidate was
parse-valid on all six calibration tasks, while Gemma produced an empty final
answer on all six tasks at the shared 2048-token generation budget. V9 changes
only Gemma's generated-token ceiling from 2048 to 4096. All other candidates,
prompt/structured-edit semantics, transport, context size, temperature, seed,
attempt count, evaluator isolation, and qualified-Docker execution remain V8.

This is calibration-only resource tuning. It is not a population-selection rule
and does not inspect or construct selection material.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from . import local_raw_calibration_v8 as v8

REPORT_SCHEMA_V8 = "plural-cognition-local-raw-capability-calibration-v8"
PROTOCOL_SCHEMA_V8 = "plural-cognition-local-raw-calibration-protocol-v8"
GEMMA_CANDIDATE_ID = "gemma4-12b-it-qat-q4"
DEFAULT_PREDICT_TOKENS = 2048
GEMMA_PREDICT_TOKENS = 4096
_BASE_V8_PROTOCOL_PAYLOAD = v8.calibration_protocol_payload_v7
_BASE_LOAD_COMMAND = v3._BASE_LOAD_COMMAND


def calibration_protocol_payload_v8() -> dict[str, object]:
    payload = dict(_BASE_V8_PROTOCOL_PAYLOAD())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V8,
            "resource_calibration_scope": "gemma-generation-budget-doubling-v1",
            "candidate_predict_token_overrides": {
                GEMMA_CANDIDATE_ID: GEMMA_PREDICT_TOKENS,
            },
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V8 = v1._sha256_json(calibration_protocol_payload_v8())


def _load_command_candidate_budget(
    *, cli: Path, model_path: Path, prompt: bytes
) -> tuple[str, ...]:
    command = list(_BASE_LOAD_COMMAND(cli=cli, model_path=model_path, prompt=prompt))
    if command.count("-n") != 1:
        raise RuntimeError("base calibration command must contain exactly one -n")
    index = command.index("-n")
    if index + 1 >= len(command):
        raise RuntimeError("base calibration command has no generation budget after -n")
    if command[index + 1] != str(DEFAULT_PREDICT_TOKENS):
        raise RuntimeError("base calibration generation budget drifted from 2048")
    if model_path.parent.name == GEMMA_CANDIDATE_ID:
        command[index + 1] = str(GEMMA_PREDICT_TOKENS)
    return tuple(command)


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)

    # V4/V3 eventually call v3._BASE_LOAD_COMMAND while constructing the exact
    # captured llama-cli invocation, so this single process-local injection is
    # the resource-only change. V8 continues to own prompt, structured edits,
    # transport, validation, Docker execution, and protected grading.
    v3._BASE_LOAD_COMMAND = _load_command_candidate_budget
    v8.REPORT_SCHEMA_V7 = REPORT_SCHEMA_V8
    v8.PROTOCOL_SCHEMA_V7 = PROTOCOL_SCHEMA_V8
    v8.calibration_protocol_payload_v7 = calibration_protocol_payload_v8
    v8.CALIBRATION_PROTOCOL_SHA256_V7 = CALIBRATION_PROTOCOL_SHA256_V8
    return v8.main(actual_argv)


if __name__ == "__main__":
    raise SystemExit(main())
