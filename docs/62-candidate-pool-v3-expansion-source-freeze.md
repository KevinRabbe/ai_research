# Candidate-pool v3 expansion scout source freeze

## Status

The candidate-pool v3 expansion method was frozen before any new challenger identity was chosen or tested. Its final prefreeze protocol revision is `1f51f19083f3e0ab7cc4f85e9bb77ef91d40d385` and its canonical protocol SHA-256 is `2ac18170b0dc5a1708f3974816dafdd28fa092f01d8170afc0e85d65dcbae4fc`.

After that protocol passed full CI, exactly three new scout artifacts were chosen using only the permitted pre-calibration metadata: immutable first-party provenance, license compatibility, documented llama.cpp compatibility, plausible full-GPU fit under the frozen 16 GiB-class hardware envelope, and general/code instruction suitability without task-specific evaluation.

No new candidate model inference has occurred. No consumed v3 calibration output, per-task behavior, or candidate-specific prompt tuning was used to choose or order the scouts.

## Frozen scout order

The immutable evaluation order is:

1. `qwen3-14b-q5km`;
2. `ministral-3-14b-instruct-2512-q5km`;
3. `ministral-3-8b-instruct-2512-q5km`.

The order is metadata-only: among the source-qualified first-party artifacts that plausibly fit the frozen full-offload hardware budget, prefer the larger clean artifact first and keep the smaller artifact as a later backup. Once this freeze is green the order must not be changed in response to later load or calibration outcomes.

## Exact source and artifact identities

### 1. qwen3-14b-q5km

- developer: `Qwen`;
- first-party repository: `Qwen/Qwen3-14B-GGUF`;
- source revision: `c75e7b2d0234068f674a1bacf548ea32e27ccd29`;
- artifact revision: `c75e7b2d0234068f674a1bacf548ea32e27ccd29`;
- filename: `Qwen3-14B-Q5_K_M.gguf`;
- quantization: `Q5_K_M`;
- exact size: `10514569568` bytes;
- SHA-256: `e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31`;
- license: `apache-2.0`;
- first-party GGUF: yes;
- documented llama.cpp usage: yes.

### 2. ministral-3-14b-instruct-2512-q5km

- developer: `Mistral AI`;
- first-party repository: `mistralai/Ministral-3-14B-Instruct-2512-GGUF`;
- source revision: `fb49df4a3cde2c774da8def12437118a66c4f5cf`;
- artifact revision: `fb49df4a3cde2c774da8def12437118a66c4f5cf`;
- filename: `Ministral-3-14B-Instruct-2512-Q5_K_M.gguf`;
- quantization: `Q5_K_M`;
- exact size: `9621091904` bytes;
- SHA-256: `f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000`;
- license: `apache-2.0`;
- first-party GGUF: yes;
- documented llama.cpp usage: yes.

### 3. ministral-3-8b-instruct-2512-q5km

- developer: `Mistral AI`;
- first-party repository: `mistralai/Ministral-3-8B-Instruct-2512-GGUF`;
- source revision: `65457cc28fafb2210c8fb885a068b107e8d7fab3`;
- artifact revision: `65457cc28fafb2210c8fb885a068b107e8d7fab3`;
- filename: `Ministral-3-8B-Instruct-2512-Q5_K_M.gguf`;
- quantization: `Q5_K_M`;
- exact size: `6059268512` bytes;
- SHA-256: `7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35`;
- license: `apache-2.0`;
- first-party GGUF: yes;
- documented llama.cpp usage: yes.

All three artifacts are new identities for this project development cycle and were not previously measured by the candidate-pool experiments.

## Granite exclusion

`ibm-granite/granite-4.1-8b-GGUF` was considered during metadata-only scouting but was not admitted to this three-scout freeze. The available first-party metadata exposed its immutable artifact revision and SHA-256 but only a rounded displayed artifact size rather than the exact byte count required by the already-frozen expansion protocol.

This exclusion is therefore a provenance/identity-completeness decision, not a capability judgment. The exact-byte requirement is not weakened and no byte count is inferred or guessed post hoc.

## Scientific boundary

The source-freeze canonical SHA-256 is:

`7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03`

Before this freeze, new expansion-candidate model calls consumed: **0**.

This source freeze itself authorizes no model inference. Once the final source-freeze commit is green under full CI, the only newly authorized repository work is authoring a deterministic load-qualification runner for the three exact frozen artifacts.

The following remain unauthorized until separately frozen later phases:

- downloading/substituting a different scout artifact after observing load outcomes;
- changing the scout order;
- adding an extra scout;
- formal load inference before a load-runner authorization freeze;
- expansion calibration runner authoring or inference;
- candidate-specific runtime or prompt tuning;
- calibration reruns;
- gate lowering;
- v3 selection-pack authoring;
- v3 selection inference;
- plural synthesis.

The next valid phase is therefore: **author, test, and freeze a one-attempt, load-only expansion qualification runner; then run it locally only after that authorization freeze is green.**
