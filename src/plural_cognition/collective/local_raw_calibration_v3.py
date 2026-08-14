"""Raw-capability calibration with a clean, auditable llama-cli answer channel.

V1/V2 used process stdout as if it were the candidate answer.  In conversation
mode the pinned llama-cli writes its UI banner, prompt echo, reasoning display,
timings, and assistant display to process stdout, so a strict answer parser can
reject the UI transcript before it reaches the actual assistant content.

V3 preserves all generation, task, strict-patch, Docker, and evaluator semantics
from V1 plus the resilient runtime provenance probe from V2.  The only semantic
change is answer transport: the pinned llama-cli ``--output-file`` transcript is
captured, its single-turn ``Assistant:`` content is separated from optional
reasoning, and only that exact assistant content is passed to the existing strict
patch parser.  Process stdout remains preserved as diagnostic evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v2 as v2

REPORT_SCHEMA_V2 = "plural-cognition-local-raw-capability-calibration-v2"
PROTOCOL_SCHEMA_V2 = "plural-cognition-local-raw-calibration-protocol-v2"
OUTPUT_MANIFEST_SCHEMA = "plural-cognition-local-raw-output-channel-manifest-v1"

_BASE_LOAD_COMMAND = v1._load_command
_BASE_RUN_LOAD = v1._run_load
_ACTIVE_ARTIFACT_ROOT: Path | None = None


def calibration_protocol_payload_v2() -> dict[str, object]:
    payload = dict(v1.calibration_protocol_payload())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V2,
            "assistant_output_channel": "llama-cli-output-file-single-turn-v1",
            "process_stdout_role": "diagnostic-only",
            "reasoning_role": "preserved-diagnostic-not-answer",
            "simple_io": True,
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V2 = v1._sha256_json(calibration_protocol_payload_v2())


def _require_active_root() -> Path:
    if _ACTIVE_ARTIFACT_ROOT is None:
        raise RuntimeError("v3 calibration output root is not initialized")
    return _ACTIVE_ARTIFACT_ROOT


def _capture_path(*, model_path: Path, prompt: bytes) -> Path:
    candidate_id = model_path.parent.name
    prompt_digest = hashlib.sha256(prompt).hexdigest()
    return (
        _require_active_root()
        / "llama-output"
        / candidate_id
        / f"{prompt_digest}.transcript.txt"
    )


def _load_command_capture(
    *,
    cli: Path,
    model_path: Path,
    prompt: bytes,
) -> tuple[str, ...]:
    command = list(_BASE_LOAD_COMMAND(cli=cli, model_path=model_path, prompt=prompt))
    capture = _capture_path(model_path=model_path, prompt=prompt)
    capture.parent.mkdir(parents=True, exist_ok=True)
    if capture.exists():
        raise ValueError(f"llama output capture already exists: {capture}")
    try:
        prompt_index = command.index("-p")
    except ValueError as exc:
        raise RuntimeError("base calibration command lacks -p prompt") from exc
    command[prompt_index:prompt_index] = [
        "--simple-io",
        "--output-file",
        str(capture),
    ]
    return tuple(command)


def extract_assistant_content(
    *,
    transcript: bytes,
    prompt: bytes,
) -> tuple[bytes, bytes | None]:
    """Extract exactly one assistant content field from the pinned CLI transcript.

    This function performs transport parsing only.  It does not repair, rewrite,
    or otherwise normalize the model's semantic answer; the returned assistant
    bytes still have to pass V1's exact strict unified-diff grammar.
    """

    if type(transcript) is not bytes or type(prompt) is not bytes:
        raise TypeError("transcript and prompt must be bytes")
    try:
        text = transcript.decode("utf-8")
        prompt_text = prompt.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("llama output transcript/prompt is not UTF-8") from exc

    # std::ofstream is a text stream on Windows, so normalize transport newlines
    # before matching the exact single-turn structure emitted by pinned llama-cli.
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
    if body.startswith(start):
        remainder = body[len(start) :]
        marker = remainder.find(end)
        if marker < 0:
            raise ValueError("llama output transcript has unterminated reasoning")
        reasoning = remainder[:marker].encode("utf-8")
        body = remainder[marker + len(end) :]

    return body.encode("utf-8"), reasoning


def _flag_value(command: tuple[str, ...], flag: str) -> str:
    if command.count(flag) != 1:
        raise RuntimeError(f"calibration command must contain exactly one {flag}")
    index = command.index(flag)
    if index + 1 >= len(command):
        raise RuntimeError(f"calibration command has no value after {flag}")
    return command[index + 1]


def _run_load_capture(
    command: tuple[str, ...],
    *,
    timeout_seconds: int,
):
    capture = Path(_flag_value(command, "--output-file"))
    prompt = _flag_value(command, "-p").encode("utf-8")
    load, process_stdout, stderr = _BASE_RUN_LOAD(
        command,
        timeout_seconds=timeout_seconds,
    )
    if not capture.is_file():
        raise RuntimeError(f"llama output transcript is missing: {capture}")

    transcript = capture.read_bytes()
    assistant, reasoning = extract_assistant_content(
        transcript=transcript,
        prompt=prompt,
    )

    process_stdout_path = capture.with_suffix(".process-stdout.bin")
    assistant_path = capture.with_suffix(".assistant.txt")
    for path in (process_stdout_path, assistant_path):
        if path.exists():
            raise RuntimeError(f"diagnostic output path already exists: {path}")
    process_stdout_path.write_bytes(process_stdout)
    assistant_path.write_bytes(assistant)
    if reasoning is not None:
        reasoning_path = capture.with_suffix(".reasoning.txt")
        if reasoning_path.exists():
            raise RuntimeError(f"diagnostic reasoning path already exists: {reasoning_path}")
        reasoning_path.write_bytes(reasoning)

    # V1's downstream field named raw_output now receives the exact assistant
    # content, not process UI stdout.  V3 changes the report schema to make this
    # transport correction explicit, while preserving all strict patch semantics.
    return load, assistant, stderr


def _write_output_manifest(root: Path) -> None:
    output_root = root / "llama-output"
    entries: list[dict[str, object]] = []
    if output_root.is_dir():
        for path in sorted(output_root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    payload = {
        "schema": OUTPUT_MANIFEST_SCHEMA,
        "protocol_sha256": CALIBRATION_PROTOCOL_SHA256_V2,
        "entries": entries,
    }
    (root / "output-channel-manifest.json").write_bytes(v1._canonical_json_bytes(payload))


def _artifact_root_from_argv(argv: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--artifact-root", required=True, type=Path)
    args, _ = parser.parse_known_args(list(argv))
    return args.artifact_root


def main(argv: Sequence[str] | None = None) -> int:
    global _ACTIVE_ARTIFACT_ROOT

    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    _ACTIVE_ARTIFACT_ROOT = _artifact_root_from_argv(actual_argv)

    # Process-local injections preserve historical V1/V2 source and evidence.
    v1._runtime_observation = v2._runtime_observation_resilient
    v1._load_command = _load_command_capture
    v1._run_load = _run_load_capture
    v1.CALIBRATION_SCHEMA = REPORT_SCHEMA_V2
    v1.calibration_protocol_payload = calibration_protocol_payload_v2
    v1.CALIBRATION_PROTOCOL_SHA256 = CALIBRATION_PROTOCOL_SHA256_V2

    exit_code = v1.main(actual_argv)
    if exit_code == 0:
        _write_output_manifest(_ACTIVE_ARTIFACT_ROOT)
        print(f"output_channel_manifest={_ACTIVE_ARTIFACT_ROOT / 'output-channel-manifest.json'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
