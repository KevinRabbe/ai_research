"""V7 raw calibration: change only solver-visible unified-diff guidance.

V6 established a stable transport across all five frozen candidates, but the
single boundary calibration task produced zero parse-valid patches. V7 keeps
the V6 transport, strict parser, evaluator, seed, temperature, attempt count,
and 2048-token generation budget unchanged. The only experimental variable is
the solver-visible output guidance: require a minimal diff, explicit old/new
change lines, exact hunk counts, and omit unnecessary diff metadata.
"""
from __future__ import annotations

import json
import sys
from typing import Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from . import local_raw_calibration_v4 as v4
from . import local_raw_calibration_v6 as v6
from .repository_surgery_calibration_matrix import CalibrationBlueprint

REPORT_SCHEMA_V6 = "plural-cognition-local-raw-capability-calibration-v6"
PROTOCOL_SCHEMA_V6 = "plural-cognition-local-raw-calibration-protocol-v6"
_BASE_V6_PROTOCOL_PAYLOAD = v6.calibration_protocol_payload_v5


def calibration_protocol_payload_v6() -> dict[str, object]:
    payload = dict(_BASE_V6_PROTOCOL_PAYLOAD())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V6,
            "solver_prompt_contract": "minimal-unified-diff-guidance-v2",
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V6 = v1._sha256_json(calibration_protocol_payload_v6())


def build_solver_prompt_v7(blueprint: CalibrationBlueprint) -> bytes:
    """Build the V7 calibration prompt without protected or gold material."""

    files: list[str] = []
    for path, data in blueprint.buggy_files:
        text = data.decode("utf-8")
        files.append(f"===== FILE: {path} =====\n{text}===== END FILE =====")
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return exactly one unified diff that can "
        "be applied from the repository root. Do not return explanation or markdown "
        "unless you use one single ```diff fenced block containing only the patch.\n\n"
        "PATCH FORMAT REQUIREMENTS:\n"
        "- Return the smallest patch that fixes the issue. Do not change unrelated lines.\n"
        "- Every changed source line must appear as one '-' old line followed by one '+' replacement line. "
        "Do not show a corrected line only as unchanged context.\n"
        "- Every @@ hunk header count must exactly match its hunk body: old count = context plus removed lines; "
        "new count = context plus added lines.\n"
        "- Use repository-relative file paths. Do not invent index hashes, timestamps, or other diff metadata.\n"
        "- Inside a hunk, every line must begin with exactly one of ' ', '+', or '-'. "
        "Do not place an unprefixed blank line inside a hunk.\n\n"
        "FORMAT EXAMPLE ONLY (unrelated to the task): if demo.txt line 2 changes from blue to green, "
        "the minimal patch is:\n"
        "```diff\n"
        "--- a/demo.txt\n"
        "+++ b/demo.txt\n"
        "@@ -2,1 +2,1 @@\n"
        "-blue\n"
        "+green\n"
        "```\n"
        "Do not copy the example content. Solve the actual issue below.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)

    # V4 owns terminal-LF normalization. Point its frozen base-prompt hook at
    # the V7 builder so V4 removes exactly one final LF from the new prompt,
    # rather than silently restoring the historical V1 prompt.
    v4._BASE_BUILD_SOLVER_PROMPT = build_solver_prompt_v7
    v3.extract_assistant_content = v6.extract_assistant_content_v6
    v4.REPORT_SCHEMA_V3 = REPORT_SCHEMA_V6
    v4.PROTOCOL_SCHEMA_V3 = PROTOCOL_SCHEMA_V6
    v4.calibration_protocol_payload_v3 = calibration_protocol_payload_v6
    v4.CALIBRATION_PROTOCOL_SHA256_V3 = CALIBRATION_PROTOCOL_SHA256_V6
    return v4.main(actual_argv)


if __name__ == "__main__":
    raise SystemExit(main())
