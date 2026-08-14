# Local Capable-Model Load Preflight

## Purpose

This gate qualifies one frozen local model artifact at a time before any Repository Surgery model output is generated or executed.

It is a hardware/runtime observation only. A passing load does not qualify a model for the final bakeoff and does not expose selection tasks.

## Frozen first candidate

The first candidate is:

```text
candidate: qwen3-8b-q8
file: Qwen3-8B-Q8_0.gguf
bytes: 8709518112
SHA-256: 408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6
```

The source repository revision and runtime are inherited from `LOCAL_MODEL_SOURCE_FREEZE_V2`.

## Download rule

The preflight downloads only through the exact frozen Hugging Face repository revision. Moving references such as `main` are not allowed.

The transfer is resumable through a `.part` file. A completed artifact is accepted only after both byte length and SHA-256 match the frozen identity. Existing correct model files are reused; existing incorrect files fail closed.

## Runtime verification

Before model loading, the preflight re-hashes the two previously qualified llama.cpp runtime archives and verifies:

```text
llama.cpp version: 10361
upstream commit: 14e78ddef
device: CUDA0
```

The model invocation is frozen to:

```text
context tokens: 4096
predict tokens: 32
GPU layers: all
device: CUDA0
fit adjustment: off
split mode: none
main GPU: 0
K cache: f16
V cache: f16
load mode: mmap
network: offline
temperature: 0
seed: 1
single turn: true
```

The flags are supported by the exact pinned llama.cpp release.

## Pass rule

The preflight passes only if all of the following hold:

1. frozen runtime archive hashes still match;
2. `llama-cli` version and CUDA0 device identity are present;
3. the exact frozen model file is present and hash-valid;
4. generation exits zero within the timeout;
5. generated stdout is non-empty;
6. llama.cpp reports GPU layer offload;
7. the final offload log reports all loadable layers on the GPU;
8. the GPU-memory monitor remains operational.

The report records baseline and peak total GPU memory, Windows peak process working set when available, execution time, exact command, output/log hashes, model-source identity, runtime identity, and software revision.

## Evidence

A successful run emits:

```text
plural-cognition-local-model-load-preflight-v1
```

and writes:

```text
load-preflight.json
stdout.bin
stderr.bin
```

The stdout/stderr files preserve the exact generation and llama.cpp diagnostic stream. Their SHA-256 values are bound into the report.

## Scientific boundary

This load test uses a trivial sanity prompt. It is not a coding benchmark and its text must not be used to select models.

No protected Repository Surgery input or expectation is supplied. No model-generated patch is executed.

After load qualification of viable candidates, raw model difficulty may be measured on calibration material only. The selection task pack must remain untouched until it is frozen.
