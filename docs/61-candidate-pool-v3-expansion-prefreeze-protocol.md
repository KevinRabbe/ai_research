# Candidate-pool v3 expansion prefreeze protocol

## Status

The completed candidate-pool v3 development calibration is frozen at commit
`5433bc8d561ad025632e1af0b4658b8d37852fe9` with canonical outcome-freeze
SHA-256 `b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56`.

Exactly three candidates passed the unchanged calibration gate, while the required
downstream population size remains four. The project therefore needs one additional
eligible development candidate before any fresh v3 selection pack can be authored.

This document freezes the expansion method **before any new challenger identity is
chosen or tested**.

## Expansion design

The expansion protocol predeclares three new scouts. Their identities are not bound by
this protocol. After this protocol is green, the next development step may choose and
source-freeze exactly three new model artifacts using only pre-calibration metadata.

Every scout must be a new artifact identity. Previously measured candidate artifacts
may not be recycled as expansion candidates. All three scout IDs, source revisions,
artifact revisions, exact SHA-256 values, byte sizes and their fixed evaluation order
must be frozen together before any new model inference.

Allowed scouting evidence is limited to source provenance, licensing, llama.cpp
compatibility, plausible full-GPU fit under the frozen hardware, and general/code
instruction suitability that does not depend on the consumed v3 calibration tasks.
Candidate performance on those tasks, task-specific prompt tuning, post-calibration
substitution and selection evidence are forbidden scouting inputs.

## Source and load qualification

Each scout must have:

- an exact first-party source revision;
- an exact artifact revision;
- an exact artifact SHA-256;
- an exact byte size before load;
- first-party provenance binding for any community quantization.

Moving-revision URLs and artifact substitution after source freeze are forbidden.

Each frozen scout then receives exactly one formal **load-only** qualification attempt
under the existing v3 runtime/resource envelope. Full GPU offload is required, fit mode
remains off, and candidate-specific runtime tuning or automatic retries are forbidden.
A load failure is terminal for that frozen artifact.

The source/load outcome must itself be frozen before any expansion calibration
inference is authorized.

## Sequential calibration rule

Expansion calibration remains development-only and reuses the six already frozen v3
development calibration tasks. Those tasks may not influence scout selection or
candidate-specific prompt design.

The gate remains exactly:

- 6/6 parse-valid;
- at least 4/6 solved.

The load-qualified scouts are evaluated in their pre-frozen order. Each candidate/task
pair receives at most one model call, with the attempt marker written before inference.
Partial evidence blocks all new inference and completed results are reused verbatim.

At most three scouts may be calibrated, for an absolute upper bound of 18 candidate-task
calls. Evaluation stops immediately when the first scout passes the gate. Later scouts
are not calibrated once the population deficit is filled.

If a scout fails, no rerun or tuning is permitted; evaluation may continue only to the
next already frozen, load-qualified scout. If no frozen scout passes, the expansion
ends in a frozen negative outcome.

## Authorization boundary

Canonical expansion-protocol SHA-256:

`2ac18170b0dc5a1708f3974816dafdd28fa092f01d8170afc0e85d65dcbae4fc`

This protocol does **not** authorize any new model inference. Once the protocol commit
is green under full CI, it authorizes only the authoring of the three-scout source
freeze.

It does not authorize gate lowering, ad-hoc candidate replacement, v3 selection-pack
authoring, selection inference, or plural synthesis. Those remain blocked until a
later frozen expansion outcome establishes at least four eligible candidates.
