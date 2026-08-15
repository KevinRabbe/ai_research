# Candidate-pool v2 load qualification plan

## Scope

This plan authorizes exactly one formal load/generation attempt for each of the three source-frozen v2 challengers. It is development-only evidence and does not select a population.

Load-plan SHA-256:

`db6c3f0383e3509cd915b1500291e68fb380be93c138db132f4f0944d127d23a`

Bound source-freeze SHA-256:

`22aa8b34a6f27cc87e651099d8194acce00ee736161d00d9866f4463322b9f2d`

Bound source-freeze revision:

`03431c4b7b6ae51385afbd910030229c4792e3eb`

## Challengers

Exactly these three identities may be attempted:

- `gpt-oss-20b-mxfp4`
- `phi-4-reasoning-plus-14b-q5km`
- `devstral-small-2-24b-q4km`

No replacement candidate or alternate quantization may be substituted after a load outcome.

## Load probe

The probe deliberately reuses the already-qualified local model load semantics rather than inventing another task protocol. It uses llama.cpp b10361 on CUDA0, context 4096, a short 32-token generation sufficient to prove model load plus generation, full GPU layer offload, fit off, split mode none, main GPU 0, f16 K/V cache, mmap, offline execution, temperature 0, and seed 1.

The 32-token load probe is not the later Repository Surgery resource budget. Candidates that survive this hardware/runtime gate will still use the frozen 4096-context / 2048-predict task budget in the six-task calibration gate.

## No-repeat evidence semantics

A candidate evidence directory is created immediately before its expensive attempt and receives an `attempt.json` marker. A completed PASS or FAIL report is terminal for this v2 cycle and is reused without inference on later invocation. If an attempt marker exists without a final report, automatic rerun is forbidden; the partial state must be diagnosed instead.

Controlled candidate load failures such as llama.cpp rejecting the model, timeout, absent generated stdout, inability to prove GPU offload, or partial GPU offload are recorded as terminal `LOCAL_MODEL_LOAD_FAIL` outcomes. Infrastructure failures such as the resource monitor breaking abort the suite and are not silently reclassified as model incapability.

All three model files must pass their frozen SHA-256 check before the first expensive attempt is authorized. For the Phi artifact, whose indexed source page did not expose an exact byte count, the locally observed byte size is recorded in the formal report while the predeclared SHA-256 remains the content identity.

## Decision after completion

There is no repeated load testing for confidence. Each passing challenger becomes eligible for the six-task calibration gate; each failing challenger is removed from this v2 cycle. The three unchanged incumbents reuse their already-qualified load evidence. If the surviving candidate count cannot support a four-mind population after calibration, the v2 cycle closes without manufacturing replacements from the same observed outcomes.
