# Candidate-pool v3 calibration runner freeze

## Status

The repaired fresh v3 calibration pack and its deterministic baseline/gold qualification are frozen before any candidate calibration inference. The restart-safe calibration runner is now frozen separately so that model-call authorization cannot be inferred merely from the existence of executable code.

The runner source/test revision that passed the full repository test suite is:

- runner source revision: `0aec10cb4dc72c54dc933439c0e4e653edfcccd7`;
- runner source Git blob: `e4e03da726ecf0ce2694c49b69a3c32896dfbaa3`;
- runner test Git blob: `189b1b91fc25e662fa6ce7bc0cc37508b0f2e30b`;
- runner protocol SHA-256: `2e3984de232ddab4b9a96f8363a331b013ce1c68f9a1b91bc651f1312ad9b600`;
- runner-freeze canonical SHA-256: `6a2b815a3d2cd6b21c77f10bcd4725c05ba34a9a4605506940d85e72c5373cf9`.

The predecessor repaired qualification remains bound by qualification-freeze SHA-256 `b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593`.

## Exact development matrix

The freeze authorizes exactly four candidates:

1. `qwen3-8b-q8`;
2. `qwen2.5-coder-14b-q5km`;
3. `devstral-24b-q4km`;
4. `gpt-oss-20b-mxfp4`.

Each receives the same six fresh v3 calibration tasks, for 24 candidate/task pairs total. The calibration gate remains 6/6 parse-valid and at least 4/6 solved per candidate.

This is development calibration only. It is not selection evidence and cannot be used as fresh v3 selection evidence later.

## One-attempt evidence rule

For every candidate/task pair:

- the pair identity is deterministic and protocol-bound;
- an immutable attempt marker is written before inference;
- at most one model call is authorized;
- a completed `result.json` is validated and reused without inference;
- any pair directory without a completed `result.json` is partial evidence and blocks all new inference;
- timeout, non-zero model exit, parse failure and ordinary unsolved outcomes are terminal evidence rather than rerun permissions;
- automatic reruns and candidate-specific tuning are forbidden.

The first target execution uses `artifacts/capable-collective/c3`. Its first invocation must begin from a fresh root. Once any pair attempt is consumed, that root is evidence and must not be deleted or recreated to obtain another attempt.

## Pre-inference checks

Before a new model call, the runner verifies:

- the exact repaired `c3q-r1` repair record, pack and qualification by file and canonical hashes;
- the frozen v3 representation protocol;
- all four exact GGUF sizes and SHA-256 values;
- the frozen llama.cpp runtime archives and observed executable;
- the exact six repaired blueprints;
- regenerated solver-visible task SHA-256 and solver-prompt SHA-256 against the qualified pack;
- all existing pair states globally, rejecting any partial pair before new inference;
- the qualified Docker configuration used for protected grading.

The runtime budget remains the frozen v3/v2 budget: context 4096, predict 2048, CUDA0, all layers requested on GPU, fit off, split mode none, main GPU 0, f16 KV cache, mmap, offline, temperature 0, seed 1, 16 threads, 16 batch threads, batch 2048, microbatch 512 and flash attention auto.

## Authorization boundary

Before this freeze, v3 candidate calibration calls consumed: **0**.

After this freeze is itself green under full CI, the only newly authorized candidate inference is the fixed 24-pair development calibration matrix above, with one attempt per pair. No v3 selection pack may be authored from the calibration outcomes until the completed calibration suite and resulting eligible population are themselves frozen.
