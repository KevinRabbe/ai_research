from __future__ import annotations

from plural_cognition.collective.consumed_selection_development_v2 import DEVELOPMENT_PROTOCOL_SHA256_V2
from plural_cognition.collective.local_consumed_selection_development_v2_runner import (
    _development_configuration_sha256,
    _solver_prompt,
)
from plural_cognition.collective.local_operational_freeze_v1 import FINAL_CANDIDATE_IDS
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def test_development_runner_uses_exactly_one_terminal_lf_transport_strip() -> None:
    prompt = _solver_prompt(selection_blueprints()[0])
    assert b"EDIT relative/file.py START DELETE INSERT" in prompt
    assert not prompt.endswith(b"\n")


def test_development_configuration_identity_changes_with_protocol() -> None:
    identities = [_development_configuration_sha256(candidate_id) for candidate_id in FINAL_CANDIDATE_IDS]
    assert len(identities) == 5
    assert len(set(identities)) == 5
    assert all(len(value) == 64 for value in identities)
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V2) == 64
