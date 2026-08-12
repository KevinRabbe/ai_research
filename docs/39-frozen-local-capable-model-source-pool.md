# Frozen Local Capable-Model Source Pool

## Status

The target-machine local inference runtime preflight passed, and the corrected five-candidate model-source freeze v2 passed without downloading model weights.

This document records the exact source identities that may enter the first local capable-model preflight. It does not claim model quality, model loadability, Repository Surgery performance, or plural uplift.

## Runtime binding

The first local inference backend is frozen to:

```text
llama.cpp release: b10361
upstream commit:   14e78ddef
platform:          Windows x64
accelerator:       CUDA 12.4

binary archive SHA-256:
115fc69566deb8d1191b4f79bc31f6e8ca7a6f7a951879008f20db796909c381

CUDA runtime archive SHA-256:
8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6
```

The target-machine device probe exposed:

```text
CUDA0: NVIDIA GeForce RTX 4060 Ti
16379 MiB total
15233 MiB free during runtime qualification
```

## Empirical source-freeze evidence

The first metadata freeze was deliberately rejected because the chosen TensorBlock DeepSeek repository did not contain the predeclared Q5_K_M artifact.

Rejected v1 manifest:

```text
7ca2c1aa898fcc657a2f3456680602449426d4d241d8d0e63f14ae391d7a06e1
```

The corrected v2 target-machine manifest passed:

```text
observed manifest SHA-256:
8e4a269bf966684769c0278b76d8fbf408c338d5ecb8d945d0760c03a05b7393

candidate count:
5
```

The deterministic in-repository canonical representation has identity:

```text
e8b22970d505ed0ffb8ea07a122c63d497db89454745083d9e69fa6950942248
```

The observed PowerShell manifest hash and the canonical repository hash intentionally serve different roles. The former preserves exact target-machine evidence; the latter gives the Python research harness a platform-independent content identity.

## Frozen candidate artifacts

```text
qwen3-8b-q8
  quant repo: Qwen/Qwen3-8B-GGUF
  quant revision: 7c41481f57cb95916b40956ab2f0b139b296d974
  source repo: Qwen/Qwen3-8B
  source revision: b968826d9c46dd6066d109eabc6255188de91218
  file: Qwen3-8B-Q8_0.gguf
  bytes: 8709518112
  SHA-256: 408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6
  provenance: first-party

qwen2.5-coder-14b-q5km
  quant repo: Qwen/Qwen2.5-Coder-14B-Instruct-GGUF
  quant revision: d0a692ef765eefbf2fabb130b3cb2e8917e3d225
  source repo: Qwen/Qwen2.5-Coder-14B-Instruct
  source revision: aedcc2d42b622764e023cf882b6652e646b95671
  file: qwen2.5-coder-14b-instruct-q5_k_m.gguf
  bytes: 10508873152
  SHA-256: 98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775
  provenance: first-party

gemma4-12b-it-qat-q4
  quant repo: google/gemma-4-12B-it-qat-q4_0-gguf
  quant revision: 29d097773436b69ff9feafd636ab4cf873786537
  source repo: google/gemma-4-12B
  source revision: 023679ed352de9bb66cc873c9009ce3482585c08
  file: gemma-4-12b-it-qat-q4_0.gguf
  bytes: 6975879296
  SHA-256: 93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b
  provenance: first-party

devstral-24b-q4km
  quant repo: mistralai/Devstral-Small-2505_gguf
  quant revision: def988cdf156b21442504f149ec0296ddbbe1e07
  source repo: mistralai/Devstral-Small-2505
  source revision: c2a9d81a2989af566682b4cecc828c84556076c5
  file: devstralQ4_K_M.gguf
  bytes: 14333908960
  SHA-256: 4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b
  provenance: first-party

deepseek-coder-v2-lite-q5km
  quant repo: bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF
  quant revision: 8f248fa2072348f77a8bc37754e470de1f61866e
  source repo: deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
  source revision: e434a23f91ba5b4923cf6c9d9a238eb4a08e3a11
  file: DeepSeek-Coder-V2-Lite-Instruct-Q5_K_M.gguf
  bytes: 11851313920
  SHA-256: 3de21719a8ffb4f6acc4b636d4ca38d882e0d0aa9a5d417106f985e0e0a4a735
  provenance: community quantization of the first-party DeepSeek source model
```

## Fail-closed download rule

All weight downloads used by the experiment must:

1. resolve through the frozen quantization repository revision, never `main` or another moving reference;
2. download the exact frozen filename;
3. verify the complete downloaded file SHA-256 before any model load;
4. reject any size/hash/revision mismatch;
5. preserve community-quantization provenance rather than presenting it as first-party;
6. never substitute another quantization or model revision after seeing benchmark results.

`src/plural_cognition/collective/local_models.py` reconstructs these identities and emits revision-pinned download URLs.

## Next empirical gate

Do not download the entire pool.

The next gate is one-model-at-a-time load qualification, beginning with `qwen3-8b-q8`:

```text
download exact revision-pinned artifact
→ verify 8,709,518,112 bytes and SHA-256
→ load with the frozen llama.cpp runtime
→ prove CUDA offload and bounded context fit
→ record peak VRAM / host RAM / startup / generation behavior
→ unload and verify clean process exit
```

Only after a candidate passes this load gate may it proceed toward calibration-only raw model difficulty measurement. The untouched selection set remains unfrozen and must not be exposed during calibration or hardware tuning.
