# Local Capable-Model Load Preflight v2

## Status

The first `qwen3-8b-q8` target run validated the frozen model artifact but failed the v1 pass gate because the verifier could not see llama.cpp's GPU-layer offload line at the default log verbosity.

A direct target diagnostic changed only one runtime argument:

```text
--log-verbosity 4
```

With that change, the exact same frozen model/runtime/context/offload configuration reported:

```text
diagnostic_exit=0
CUDA0: NVIDIA GeForce RTX 4060 Ti
load_tensors: offloading output layer to GPU
load_tensors: offloading 35 repeating layers to GPU
load_tensors: offloaded 37/37 layers to GPU
CPU_Mapped model buffer size = 630.59 MiB
CUDA0 model buffer size = 7669.77 MiB
CUDA0 KV buffer size = 576.00 MiB
CUDA0 compute buffer size = 100.01 MiB
llama_server: model loaded
```

The frozen model SHA-256 remained:

```text
408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6
```

This establishes that the v1 failure was an observability defect in the harness rather than evidence that the model failed to load or offload.

## Why v2 is separate

The v1 implementation remains unchanged so its failed target evidence keeps its original semantics.

`local_model_load_preflight_v2.py` reuses the v1 artifact verification, frozen-runtime verification, download/resume logic, CUDA memory monitor, Windows process-memory monitor, and offload parser. The protocol delta is explicit and minimal:

```text
v1: llama.cpp default log verbosity
v2: --log-verbosity 4
```

The v2 report schema is:

```text
plural-cognition-local-model-load-preflight-v2
```

and the report records `log_verbosity=4` in its protocol section.

## Frozen v2 invocation

All material inference settings remain unchanged from v1:

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
log verbosity: 4
```

## Pass rule

v2 passes only if:

1. the frozen llama.cpp runtime archives still match their qualified hashes;
2. runtime version `10361 / 14e78ddef` and `CUDA0` are present;
3. the exact frozen model file matches byte length and SHA-256;
4. generation exits zero within the timeout;
5. generated stdout is non-empty;
6. verbosity-4 diagnostics contain the GPU-layer offload proof;
7. the final offload proof reports every loadable layer on the GPU;
8. resource monitoring remains operational;
9. the model process exits and target GPU memory can be observed after exit.

Existing correct model files are re-hashed and reused. A formal v2 rerun must therefore not redownload the already verified Qwen3-8B Q8 artifact.

## Scientific boundary

The target diagnostic and formal v2 load gate are hardware/runtime qualification only. The sanity-generation text is not a model-quality score, no selection task is exposed, and no model-generated Repository Surgery patch is executed.
