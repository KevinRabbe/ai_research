"""V6 raw calibration: preserve closed-at-EOF reasoning with one residual LF.

Target v5 evidence showed one additional pinned-llama transport shape: after the
outer two-LF transcript terminator is removed, a reasoning-only completion can
end in ``[End thinking]\n`` rather than exactly ``[End thinking]``.  V6 maps
only those two closed forms to an empty candidate answer.  Missing closure and
all other trailing bytes remain infrastructure failures.
"""
from __future__ import annotations

import sys
from typing import Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from . import local_raw_calibration_v4 as v4
from . import local_raw_calibration_v5 as v5

REPORT_SCHEMA_V5 = "plural-cognition-local-raw-capability-calibration-v5"
PROTOCOL_SCHEMA_V5 = "plural-cognition-local-raw-calibration-protocol-v5"
_BASE_V5_PROTOCOL_PAYLOAD = v5.calibration_protocol_payload_v4


def calibration_protocol_payload_v5() -> dict[str, object]:
    payload = dict(_BASE_V5_PROTOCOL_PAYLOAD())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V5,
            "reasoning_eof_policy": "closed-reasoning-empty-answer-residual-lf-v2",
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V5 = v1._sha256_json(calibration_protocol_payload_v5())


def extract_assistant_content_v6(
    *, transcript: bytes, prompt: bytes
) -> tuple[bytes, bytes | None]:
    if type(transcript) is not bytes or type(prompt) is not bytes:
        raise TypeError("transcript and prompt must be bytes")
    try:
        text = transcript.decode("utf-8")
        prompt_text = prompt.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("llama output transcript/prompt is not UTF-8") from exc

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    prefix = f"User:\n{prompt_text}\n\nAssistant:\n"
    if not text.startswith(prefix):
        raise ValueError("llama output transcript does not bind the supplied prompt")
    body = text[len(prefix) :]
    if not body.endswith("\n\n"):
        raise ValueError("llama output transcript lacks the expected assistant terminator")
    body = body[:-2]

    reasoning: bytes | None = None
    start = "[Start thinking]\n\n"
    end = "[End thinking]\n\n"
    eof_end = "[End thinking]"
    eof_end_one_lf = eof_end + "\n"
    if body.startswith(start):
        remainder = body[len(start) :]
        marker = remainder.find(end)
        if marker >= 0:
            reasoning = remainder[:marker].encode("utf-8")
            body = remainder[marker + len(end) :]
        elif remainder.endswith(eof_end):
            reasoning = remainder[: -len(eof_end)].encode("utf-8")
            body = ""
        elif remainder.endswith(eof_end_one_lf):
            reasoning = remainder[: -len(eof_end_one_lf)].encode("utf-8")
            body = ""
        else:
            raise ValueError("llama output transcript has unterminated reasoning")
    return body.encode("utf-8"), reasoning


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    v3.extract_assistant_content = extract_assistant_content_v6
    v4.REPORT_SCHEMA_V3 = REPORT_SCHEMA_V5
    v4.PROTOCOL_SCHEMA_V3 = PROTOCOL_SCHEMA_V5
    v4.calibration_protocol_payload_v3 = calibration_protocol_payload_v5
    v4.CALIBRATION_PROTOCOL_SHA256_V3 = CALIBRATION_PROTOCOL_SHA256_V5
    return v4.main(actual_argv)


if __name__ == "__main__":
    raise SystemExit(main())
