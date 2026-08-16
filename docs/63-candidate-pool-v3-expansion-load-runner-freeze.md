# Candidate-pool v3 expansion load-runner freeze

## Status

The three expansion scout identities are frozen by source-freeze revision `dea35b4c11d8de39b978bf3a4ba5f098cfab795b` and canonical source-freeze SHA-256 `7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03`.

A restart-safe load-only runner was then authored and passed the full repository test suite before any expansion model launch. The exact green runner identity is:

- runner source revision: `3a8a80d8fdc28d9de36f7ee248d07d952117f428`;
- runner source Git blob: `0241f1d38dc9db2a86cfd0cbf2dd9169deceb403`;
- runner test Git blob: `af1c88e272408376794444f0b45ce3f0ee650aaf`;
- runner protocol SHA-256: `6670ae531b31bd0548947bcc4ce0b8248204648f0bd3d280c68e1211bed340a4`;
- runner-freeze canonical SHA-256: `f64bb5a63dbe9e9141f44840d55b33420decaca71cc108c2842e8d43175ec763`.

No expansion-candidate model calls occurred before this freeze.

## Exact authorized scouts

The fixed order and exact artifacts are:

1. `qwen3-14b-q5km` — `Qwen3-14B-Q5_K_M.gguf`, `10514569568` bytes, SHA-256 `e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31`;
2. `ministral-3-14b-instruct-2512-q5km` — `Ministral-3-14B-Instruct-2512-Q5_K_M.gguf`, `9621091904` bytes, SHA-256 `f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000`;
3. `ministral-3-8b-instruct-2512-q5km` — `Ministral-3-8B-Instruct-2512-Q5_K_M.gguf`, `6059268512` bytes, SHA-256 `7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35`.

Artifact substitution, scout reordering, and adding an extra scout after observing load outcomes are forbidden.

## Load-only probe

The formal probe is deliberately not a capability test. It uses the frozen v3 runtime/resource envelope with context 4096, all GPU layers requested on `CUDA0`, fit off, split mode none, main GPU 0, f16 KV cache, mmap, offline mode, temperature 0, seed 1, 16 threads, 16 batch threads, batch 2048, microbatch 512, flash attention auto, and trace-level logging sufficient to expose the GPU-offload line.

The runner uses `-n 0` and the inert prompt `.`. Therefore the formal event is a model load/offload observation, not a Repository Surgery capability evaluation.

A PASS requires a clean process exit and trace evidence that every reported model layer was offloaded to GPU. Timeout, non-zero exit, missing offload evidence, partial offload, or resource-monitor failure becomes a terminal load FAIL for that exact frozen artifact.

## Evidence and restart rule

The first execution root is `artifacts/capable-collective/e3l` and must begin fresh.

For each scout:

- at most one model launch is authorized;
- `attempt.json` is written before launching llama.cpp;
- raw stdout/stderr are persisted before PASS/FAIL classification;
- completed `result.json` evidence is validated and reused without a new launch;
- any scout directory without a completed result is partial evidence and blocks all new model launches globally;
- failures do not authorize retries or runtime tuning.

Before the first launch, the runner verifies all three exact model files by byte size and SHA-256, verifies the frozen llama.cpp archives/runtime, and validates the exact source-freeze and runner-protocol identities.

## Authorization boundary

After this freeze itself is green under full CI, exactly three model calls are authorized: one load-only attempt for each frozen scout. Downloading the three exact revision-pinned artifacts is also authorized so those bytes can be verified locally.

The target roots are:

- model root: `artifacts/capable-collective/m2`;
- runtime root: `artifacts/capable-collective/inference-runtime/llama.cpp-b10361-win-cuda12.4`;
- load evidence root: `artifacts/capable-collective/e3l`.

No expansion calibration runner may be authored until the completed load suite and load-qualified scout set are frozen. Calibration inference, selection-pack authoring, selection inference, and plural synthesis remain unauthorized.
