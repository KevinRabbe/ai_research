"""Content-addressed source freeze for candidate-pool v2 challengers.

This freeze is created before any v2 challenger load inference. It binds the three
predeclared challenger identities to immutable first-party source snapshots and
immutable GGUF artifacts. Community GGUFs are accepted only with an explicit
first-party provenance binding and an exact artifact SHA-256.

The freeze is development-only. It does not qualify model capability, select a
population, or create fresh selection/generalization evidence.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CANDIDATE_POOL_V2_SOURCE_FREEZE_SCHEMA = (
    "plural-cognition-candidate-pool-v2-source-freeze-v1"
)
QUALIFICATION_PROTOCOL_SHA256 = (
    "f3886fa683aeb5ab3343dc6c388da4b58ebc63f2911be01602fa2fdc2ddaa4b6"
)
QUALIFICATION_PROTOCOL_REVISION = "3306eb09e88a8e731419412b69cb48664cc3aece"
EXPECTED_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256 = (
    "22aa8b34a6f27cc87e651099d8194acce00ee736161d00d9866f4463322b9f2d"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_source_freeze_payload() -> dict[str, Any]:
    return {
        "schema": CANDIDATE_POOL_V2_SOURCE_FREEZE_SCHEMA,
        "scientific_status": (
            "candidate-development-v2-source-qualified-pre-inference-not-selection-evidence"
        ),
        "qualification_protocol_sha256": QUALIFICATION_PROTOCOL_SHA256,
        "qualification_protocol_revision": QUALIFICATION_PROTOCOL_REVISION,
        "source_qualification_completed_before_challenger_inference": True,
        "challengers": [
            {
                "candidate_id": "gpt-oss-20b-mxfp4",
                "developer": "OpenAI",
                "license": "apache-2.0",
                "first_party_repo": "openai/gpt-oss-20b",
                "artifact_linked_source_revision": (
                    "6cee5e81ee83917806bbde320786a8fb61efebee"
                ),
                "observed_current_source_revision": (
                    "6cee5e81ee83917806bbde320786a8fb61efebee"
                ),
                "artifact_repo": "ggml-org/gpt-oss-20b-GGUF",
                "artifact_revision": "b97cbb20d1995efd41dce8c4dd1ddf86e8db375b",
                "filename": "gpt-oss-20b-MXFP4.gguf",
                "quantization": "native-mxfp4",
                "artifact_sha256": (
                    "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901"
                ),
                "artifact_size_bytes": 12109566624,
                "download_url": (
                    "https://huggingface.co/ggml-org/gpt-oss-20b-GGUF/resolve/"
                    "b97cbb20d1995efd41dce8c4dd1ddf86e8db375b/"
                    "gpt-oss-20b-MXFP4.gguf?download=true"
                ),
                "lineage_evidence": {
                    "artifact_src_sha_matches_first_party_revision": True,
                    "quantizer_release": None,
                    "note": (
                        "current ggml-org uppercase MXFP4 artifact supersedes the "
                        "deleted historical lowercase artifact before any v2 load "
                        "outcome was observed"
                    ),
                },
                "provenance_caveats": [],
            },
            {
                "candidate_id": "phi-4-reasoning-plus-14b-q5km",
                "developer": "Microsoft",
                "license": "mit",
                "first_party_repo": "microsoft/Phi-4-reasoning-plus",
                "artifact_linked_source_revision": (
                    "609962c42f66296434ad0a4f3a99ac99381205c6"
                ),
                "observed_current_source_revision": (
                    "69baf8528e1bcf05f475034d9e5dd32875ed125f"
                ),
                "artifact_repo": "bartowski/microsoft_Phi-4-reasoning-plus-GGUF",
                "artifact_revision": "7724f4a631c905f40112df7104ec590dc3bf290a",
                "filename": "microsoft_Phi-4-reasoning-plus-Q5_K_M.gguf",
                "quantization": "Q5_K_M",
                "artifact_sha256": (
                    "7d4dd651787f16365d6ceed9bcc42fe76e47204dedf9ac3539a749e1c3f3b6f7"
                ),
                "artifact_size_bytes": None,
                "download_url": (
                    "https://huggingface.co/bartowski/"
                    "microsoft_Phi-4-reasoning-plus-GGUF/resolve/"
                    "7724f4a631c905f40112df7104ec590dc3bf290a/"
                    "microsoft_Phi-4-reasoning-plus-Q5_K_M.gguf?download=true"
                ),
                "lineage_evidence": {
                    "artifact_src_sha_matches_first_party_revision": False,
                    "quantizer_release": "llama.cpp-b5228",
                    "note": (
                        "artifact repository names the first-party source but does "
                        "not publish an immutable source SHA; the source revision is "
                        "frozen to the last first-party snapshot predating the May 1 "
                        "2025 artifact upload"
                    ),
                },
                "provenance_caveats": [
                    (
                        "current first-party main contains later tokenizer/configuration "
                        "changes; this candidate is the exact May 2025 GGUF artifact "
                        "lineage, not a reconstruction from current main"
                    ),
                    (
                        "exact byte size was not exposed by the indexed artifact page; "
                        "SHA-256 and immutable artifact revision are the primary content "
                        "identity and byte size will be recorded from the target file "
                        "before load"
                    ),
                ],
            },
            {
                "candidate_id": "devstral-small-2-24b-q4km",
                "developer": "Mistral AI",
                "license": "apache-2.0",
                "first_party_repo": "mistralai/Devstral-Small-2-24B-Instruct-2512",
                "artifact_linked_source_revision": (
                    "839af38e4e97acc43ff9ca61dff0ef6efc1cf407"
                ),
                "observed_current_source_revision": (
                    "c599e8e56f3f9110e97f0dc0450ce248e3334d84"
                ),
                "artifact_repo": (
                    "bartowski/mistralai_Devstral-Small-2-24B-Instruct-2512-GGUF"
                ),
                "artifact_revision": "2926c4f9c89e15bdebd5c8f458acd9609e778631",
                "filename": (
                    "mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf"
                ),
                "quantization": "Q4_K_M",
                "artifact_sha256": (
                    "bfd11c8679c6b81eb43763505465d7dcfa72e460ab1c220ecc235a3efadd7f7f"
                ),
                "artifact_size_bytes": 14334438272,
                "download_url": (
                    "https://huggingface.co/bartowski/"
                    "mistralai_Devstral-Small-2-24B-Instruct-2512-GGUF/resolve/"
                    "2926c4f9c89e15bdebd5c8f458acd9609e778631/"
                    "mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf"
                    "?download=true"
                ),
                "lineage_evidence": {
                    "artifact_src_sha_matches_first_party_revision": False,
                    "quantizer_release": "llama.cpp-b7335",
                    "note": (
                        "artifact was uploaded on the same release date as the "
                        "first-party initial super-squashed snapshot; that exact source "
                        "snapshot is frozen"
                    ),
                },
                "provenance_caveats": [
                    (
                        "current first-party main contains later THINK-token changes; "
                        "this candidate preserves the exact December 2025 artifact lineage"
                    ),
                    (
                        "artifact publisher warns mistral-vibe/tool-calling integration "
                        "was incomplete; v2 qualification uses direct Repository Surgery "
                        "prompts without tool calling"
                    ),
                ],
            },
        ],
        "qualification_rule": {
            "challenger_count": 3,
            "exact_first_party_revision_bound": True,
            "exact_artifact_revision_bound": True,
            "exact_artifact_sha256_bound": True,
            "moving_revision_urls_forbidden": True,
            "artifact_substitution_after_load_outcome": False,
            "load_inference_performed": False,
            "selection_evidence": False,
        },
    }


FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_source_freeze_payload())
).hexdigest()

if (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
    != EXPECTED_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
):
    raise AssertionError("candidate-pool v2 source freeze identity drifted")
