# Candidate-pool v2 qualification protocol

## Purpose

V1 population selection is permanently closed with `insufficient-eligible`. The consumed v1 split may guide development, but it cannot support a new selection/generalization claim. V4 materially improved output representation and V5 same-mind self-review failed its predeclared continuation gate. The next uncertainty is therefore candidate capability and population composition, not another serialization or review-loop variant.

This document predeclares a deliberately small v2 development cycle before any fresh v2 selection material exists.

Protocol SHA-256:

`f3886fa683aeb5ab3343dc6c388da4b58ebc63f2911be01602fa2fdc2ddaa4b6`

## Frozen predecessors

- research base revision: `405611be399bb6e5f8139bf898db91f771e15426`
- V1 selection-outcome freeze: `e579e01b0c1d710a4ca303896da84801ef27d9502b66782c88f384129fbe4eb5`
- V4 development-outcome freeze: `93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a`
- V5 self-review-outcome freeze: `738d1e633c767f09f5d11c46e71eb7e552adfe424b93b826f3834380af7af58d`

## What is retained

The exact llama.cpp b10361 runtime at `14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840`, the qualified CUDA0 RTX 4060 Ti target, and the 4096-context / 2048-predict resource envelope remain unchanged. V4's raw full-file replacement contract becomes the v2 candidate representation. No same-mind self-review, fuzzy matching, repair pass, or second attempt is added.

## Candidate set

Three unchanged incumbents are carried into development because they were the strongest usable v1/V4 candidates:

- `qwen3-8b-q8`
- `qwen2.5-coder-14b-q5km`
- `devstral-24b-q4km`

Two v1 candidates are retired from this v2 cycle:

- `gemma4-12b-it-qat-q4`: persistent empty-final-output pathology under the frozen resource budget;
- `deepseek-coder-v2-lite-q5km`: V4/V5 development repaired transport validity but left repeated semantic partial repairs.

Three challenger scouts are fixed before formal load outcomes are observed:

- `gpt-oss-20b-mxfp4` from `openai/gpt-oss-20b`, targeting native MXFP4;
- `phi-4-reasoning-plus-14b-q5km` from `microsoft/Phi-4-reasoning-plus`, targeting Q5_K_M;
- `devstral-small-2-24b-q4km` from `mistralai/Devstral-Small-2-24B-Instruct-2512`, targeting Q4_K_M.

These are scout identities, not yet a source freeze. Before any challenger inference, a separate source manifest must bind the exact first-party revision and exact runtime artifact SHA-256. A community quantization is permitted only when it is explicitly bound to the first-party source-model revision. If a scout cannot be source-qualified or fully offloaded, it fails this cycle; it is not replaced after observing its load outcome.

## Minimal qualification sequence

1. **Source qualification, zero inference.** Bind immutable first-party revision, exact inference artifact, quantization provenance, license, and runtime compatibility.
2. **Load qualification.** One formal load attempt per challenger. Full GPU offload is required. Unchanged incumbents may reuse their existing formal load evidence because their model/runtime identity is unchanged.
3. **Calibration gate.** Exactly six calibration-only Repository Surgery tasks per surviving candidate under the fixed V4 whole-file contract. Require 6/6 parse-valid and at least 4/6 solved. No candidate-specific prompt tuning and no rerun of a failed candidate.
4. **Operational freeze v2.** Freeze the exact identities and operational configurations of all candidates that passed calibration.
5. **Fresh selection pack v2.** Create twelve new untouched tasks only after the operational freeze. The consumed v1 material is prohibited from supporting the new selection claim.
6. **Selection v2.** Run exactly once with `min_valid_rate=0.95`, population size four, and no threshold lowering after the result.

This bounds the maximum new model inference before selection to three challenger load calls plus six calibration calls per candidate. If all six candidates reach calibration, that is 36 calibration calls. Selection then uses 12 calls per frozen candidate. No additional experiment is authorized merely to increase confidence when its result cannot change the next architectural decision.

## Stopping rule

> Do not run a test unless PASS versus FAIL can change the next decision.

This is the anti-overtesting rule for v2. Cheap deterministic CI tests, source hashes, and parser invariants remain exhaustive because they are inexpensive. Model inference is deliberately sparse and decision-driven.

## Scientific boundary

This protocol does not select a population, establish plural uplift, or create fresh generalization evidence. It only defines how candidate identities may become eligible for a later untouched v2 selection run. V1's negative selection result, V4's consumed-split development result, and V5's rejected self-review result remain permanent evidence and are not overwritten by this cycle.
