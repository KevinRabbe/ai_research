"""Raw-capability calibration with literal, content-addressed prompt transport.

Target v3 evidence showed that the pinned llama-cli's default escape processing
rewrote literal backslash escape sequences embedded in solver-visible source
files before inference.  The pinned CLI also removes one terminal newline from
``-p`` input before constructing the user message.

V4 preserves v3's isolated assistant-output channel and all v1 strict-patch,
qualified-Docker, evaluator, and resource semantics.  Its only additional
calibration changes are:

* remove the builder's single terminal LF before hashing/passing the prompt, so
  the content-addressed prompt bytes are exactly the user-message bytes seen by
  llama-cli; and
* pass ``--no-escape`` so source-code sequences such as ``"\\n"`` remain
  literal instead of being rewritten into newline characters.

Historical v1/v2/v3 source and failed target evidence remain unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from .repository_surgery_calibration_matrix import CalibrationBlueprint

REPORT_SCHEMA_V3 = "plural-cognition-local-raw-capability-calibration-v3"
PROTOCOL_SCHEMA_V3 = "plural-cognition-local-raw-calibration-protocol-v3"

_BASE_BUILD_SOLVER_PROMPT = v1.build_solver_prompt
_BASE_V1_PROTOCOL_PAYLOAD = v1.calibration_protocol_payload
_BASE_V3_LOAD_COMMAND_CAPTURE = v3._load_command_capture


def build_solver_prompt_literal(blueprint: CalibrationBlueprint) -> bytes:
    """Return the solver prompt bytes exactly as llama-cli will receive them.

    V1's builder intentionally terminates its textual prompt with one LF.  The
    pinned llama-cli removes one trailing LF from ``-p`` before constructing the
    user message.  Removing it here makes the stored prompt identity equal to the
    actual user-message bytes, rather than hashing a byte the runtime discards.
    """

    prompt = _BASE_BUILD_SOLVER_PROMPT(blueprint)
    if not prompt.endswith(b"\n"):
        raise RuntimeError("base calibration prompt no longer ends in the expected LF")
    return prompt[:-1]


def calibration_protocol_payload_v3() -> dict[str, object]:
    payload = dict(_BASE_V1_PROTOCOL_PAYLOAD())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V3,
            "assistant_output_channel": "llama-cli-output-file-single-turn-v1",
            "process_stdout_role": "diagnostic-only",
            "reasoning_role": "preserved-diagnostic-not-answer",
            "simple_io": True,
            "prompt_transport": "literal-argv-no-escape-v1",
            "escape_processing": False,
            "terminal_prompt_lf": False,
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V3 = v1._sha256_json(calibration_protocol_payload_v3())


def _load_command_literal_capture(
    *,
    cli: Path,
    model_path: Path,
    prompt: bytes,
) -> tuple[str, ...]:
    """Build the v3 capture command while disabling llama.cpp escape rewriting."""

    command = list(
        _BASE_V3_LOAD_COMMAND_CAPTURE(
            cli=cli,
            model_path=model_path,
            prompt=prompt,
        )
    )
    if "--escape" in command or "--no-escape" in command:
        raise RuntimeError("base calibration command unexpectedly controls escape processing")
    if command.count("-p") != 1:
        raise RuntimeError("calibration command must contain exactly one -p prompt")
    prompt_index = command.index("-p")
    command[prompt_index:prompt_index] = ["--no-escape"]
    return tuple(command)


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)

    # Process-local injections only.  V3 continues to own isolated answer
    # capture and V1 continues to own strict parsing, Docker execution, grading,
    # and report construction.  These bindings merely correct prompt transport
    # and give that corrected protocol a new immutable identity.
    v1.build_solver_prompt = build_solver_prompt_literal
    v3._load_command_capture = _load_command_literal_capture
    v3.REPORT_SCHEMA_V2 = REPORT_SCHEMA_V3
    v3.PROTOCOL_SCHEMA_V2 = PROTOCOL_SCHEMA_V3
    v3.calibration_protocol_payload_v2 = calibration_protocol_payload_v3
    v3.CALIBRATION_PROTOCOL_SHA256_V2 = CALIBRATION_PROTOCOL_SHA256_V3
    return v3.main(actual_argv)


if __name__ == "__main__":
    raise SystemExit(main())
