from plural_cognition.collective.consumed_selection_development_v5_self_review import (
    DEVELOPMENT_PROTOCOL_SHA256_V5,
    TARGET_CANDIDATE_IDS_V5,
)
from plural_cognition.collective.local_consumed_selection_development_v5_self_review import (
    _development_configuration_sha256,
    _review_prompt,
)
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def test_v5_review_prompt_transport_removes_exactly_one_terminal_lf() -> None:
    blueprint = {item.task_id: item for item in selection_blueprints()}[
        "repository-surgery-selection-multi-file-0001"
    ]
    draft = b"FILE fees.py\n<<<<<<< CONTENT\nx\n>>>>>>> CONTENT"
    prompt = _review_prompt(blueprint, draft)
    assert not prompt.endswith(b"\n")
    assert b"SELF_REVIEW_STAGE:" in prompt
    assert draft in prompt


def test_v5_development_configuration_is_candidate_specific() -> None:
    identities = [_development_configuration_sha256(candidate_id) for candidate_id in TARGET_CANDIDATE_IDS_V5]
    assert len(set(identities)) == len(TARGET_CANDIDATE_IDS_V5)
    assert all(len(item) == 64 for item in identities)
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V5) == 64
