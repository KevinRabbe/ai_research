"""V5 raw calibration: closed reasoning at EOF becomes an empty candidate answer."""
from __future__ import annotations
import sys
from typing import Sequence
from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from . import local_raw_calibration_v4 as v4

REPORT_SCHEMA_V4 = "plural-cognition-local-raw-capability-calibration-v4"
PROTOCOL_SCHEMA_V4 = "plural-cognition-local-raw-calibration-protocol-v4"
_BASE_V4_PROTOCOL_PAYLOAD = v4.calibration_protocol_payload_v3

def calibration_protocol_payload_v4() -> dict[str, object]:
    payload = dict(_BASE_V4_PROTOCOL_PAYLOAD())
    payload.update({"schema": PROTOCOL_SCHEMA_V4, "reasoning_eof_policy": "closed-reasoning-empty-answer-v1"})
    return payload

CALIBRATION_PROTOCOL_SHA256_V4 = v1._sha256_json(calibration_protocol_payload_v4())

def extract_assistant_content_v5(*, transcript: bytes, prompt: bytes) -> tuple[bytes, bytes | None]:
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
    body = text[len(prefix):]
    if not body.endswith("\n\n"):
        raise ValueError("llama output transcript lacks the expected assistant terminator")
    body = body[:-2]
    reasoning: bytes | None = None
    start = "[Start thinking]\n\n"
    end = "[End thinking]\n\n"
    eof_end = "[End thinking]"
    if body.startswith(start):
        remainder = body[len(start):]
        marker = remainder.find(end)
        if marker >= 0:
            reasoning = remainder[:marker].encode("utf-8")
            body = remainder[marker + len(end):]
        elif remainder.endswith(eof_end):
            reasoning = remainder[:-len(eof_end)].encode("utf-8")
            body = ""
        else:
            raise ValueError("llama output transcript has unterminated reasoning")
    return body.encode("utf-8"), reasoning

def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    v3.extract_assistant_content = extract_assistant_content_v5
    v4.REPORT_SCHEMA_V3 = REPORT_SCHEMA_V4
    v4.PROTOCOL_SCHEMA_V3 = PROTOCOL_SCHEMA_V4
    v4.calibration_protocol_payload_v3 = calibration_protocol_payload_v4
    v4.CALIBRATION_PROTOCOL_SHA256_V3 = CALIBRATION_PROTOCOL_SHA256_V4
    return v4.main(actual_argv)

if __name__ == "__main__":
    raise SystemExit(main())
