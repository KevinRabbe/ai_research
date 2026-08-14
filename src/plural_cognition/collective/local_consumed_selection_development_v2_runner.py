"""Corrected executable wrapper for consumed-selection V2 development.

The initial development runner referenced a convenience ``config()`` method that the
frozen operational configuration object intentionally does not expose. This wrapper
keeps the V2 protocol and execution path unchanged, derives the same development
configuration identity from the frozen ``configs`` tuple, and patches only that local
helper before delegating to the original runner.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from . import local_consumed_selection_development_v2 as base
from .consumed_selection_development_v2 import DEVELOPMENT_PROTOCOL_SHA256_V2
from .local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _final_candidate_config(candidate_id: str):
    matches = tuple(
        item
        for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs
        if item.candidate_id == candidate_id
    )
    if len(matches) != 1:
        raise KeyError(f"expected exactly one frozen candidate config: {candidate_id}")
    return matches[0]


def _development_configuration_sha256(candidate_id: str) -> str:
    final = _final_candidate_config(candidate_id)
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "final_candidate_configuration_sha256": final.sha256,
                "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V2,
            }
        )
    ).hexdigest()


# Deliberately patch one implementation defect only. The consumed-split protocol,
# prompts, parser/interpreter, resource settings, protected evaluator, and run loop
# remain those of ``local_consumed_selection_development_v2``.
base._development_configuration_sha256 = _development_configuration_sha256
_solver_prompt = base._solver_prompt
run_consumed_selection_development = base.run_consumed_selection_development


def main(argv: Sequence[str] | None = None) -> int:
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
