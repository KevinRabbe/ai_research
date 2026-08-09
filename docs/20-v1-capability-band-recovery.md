# V1 capability-band recovery protocol

## Status

This protocol is defined only after the first empirical screening completed under the original frozen three-scale matrix and returned:

```text
status=all-too-weak
selected_model=None
```

Observed mean exact accuracy on the frozen 512-example validation set was:

```text
PC-4M:   0.025390625
PC-10M:  0.0693359375
PC-18M:  0.1083984375
```

All three scales satisfied the parse-rate boundary. Semantic accuracy increased monotonically with model scale. The original result remains a negative result and must not be overwritten or reinterpreted as a selected model.

## Recovery principle

The recovery protocol changes exactly one scientific axis: **model capacity**.

It keeps fixed:

- data seed `20260806`;
- the exact reusable training and validation shards;
- sequence length `256`;
- target optimizer batch `32,768` padded tokens;
- token budget `10,000,000` per run, resolving to 306 complete optimizer steps and `10,027,008` effective padded tokens;
- optimizer and token-indexed schedule;
- initialization seeds `101` and `102` for screening;
- greedy 512-example scale evaluation;
- minimum parse rate `0.95` per seed;
- mean exact-accuracy capability band `0.20` through `0.70`;
- smallest-qualifying-scale selection;
- downstream population seeds `101`, `102`, `103`, and `104`.

It does not alter supervision, task difficulty, curriculum, evaluation rows, or the selection boundary.

## Recovery model family

The original fixed 64-dimensional attention-head geometry and four-times FFN expansion continue monotonically:

```text
PC-29M: 12 layers, d_model 448, 7 heads, 28,946,176 parameters
PC-44M: 14 layers, d_model 512, 8 heads, 44,093,440 parameters
PC-64M: 16 layers, d_model 576, 9 heads, 63,763,200 parameters
```

The screening protocol identifier is `v1.2`. This identifier refers to the capability-recovery screening matrix and does not change the historical negative result from the original `v1.1-screen` matrix.

## Qualification and measured preflight

The repository must be locally and remotely qualified at one exact commit before measured artifacts are created. The working tree must remain unchanged after the measured CUDA preflight.

On Windows with the project virtual environment:

```powershell
cd F:\advanced_airesearch\repo

git switch agent/plural-cognition-research-foundation
git pull --ff-only origin agent/plural-cognition-research-foundation

.\.venv\Scripts\python.exe -m pytest
git rev-parse HEAD
git status --short
```

Reuse the already content-addressed V1 dataset shards. Do not regenerate them unless their hashes differ from the preserved empirical V1 files.

Run the new-model-only measured preflight while the GPU is otherwise idle:

```powershell
New-Item -ItemType Directory -Force artifacts\v12\preflight | Out-Null

.\.venv\Scripts\plural-cognition-cuda-preflight.exe `
    --models pc-29m pc-44m pc-64m `
    --sequence-lengths 128 256 `
    --microbatches 16 32 64 128 256 `
    --precision auto `
    --warmup-steps 5 `
    --measured-steps 20 `
    --vram-limit-gb 13.5 `
    --seed 20260806 `
    --output artifacts\v12\preflight\cuda-preflight.json
```

## Resolve the six recovery runs

```powershell
New-Item -ItemType Directory -Force artifacts\v12\plans | Out-Null
New-Item -ItemType Directory -Force artifacts\v12\executions\screening | Out-Null

.\.venv\Scripts\plural-cognition-resolve-screening.exe `
    --protocol v1.2 `
    --preflight artifacts\v12\preflight\cuda-preflight.json `
    --initialization-seeds 101 102 `
    --data-seed 20260806 `
    --output artifacts\v12\plans\screening-plan.json

.\.venv\Scripts\plural-cognition-prepare-screening-executions.exe `
    --screening-plan artifacts\v12\plans\screening-plan.json `
    --training-manifests artifacts\datasets\train-000.manifest.json `
    --validation-manifests artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\v12\executions\screening
```

Expected execution names are:

```text
execution-pc29m-seed-101.json
execution-pc29m-seed-102.json
execution-pc44m-seed-101.json
execution-pc44m-seed-102.json
execution-pc64m-seed-101.json
execution-pc64m-seed-102.json
```

Run the normal dry-run validation for every execution before training.

## Training and greedy evaluation

Each run remains exactly 306 complete optimizer steps. Training writes the same fail-closed checkpoints and machine-readable progress artifacts, with a compact in-place terminal percentage bar.

Evaluate all six final checkpoints greedily on the same frozen validation shard. Do not supply a sampling seed during scale selection.

## Frozen recovery selector

```powershell
.\.venv\Scripts\plural-cognition-select-scale.exe `
    --protocol v1.2 `
    --result PC-29M 101 artifacts\v12\evaluations\screening\pc29m-seed-101.json `
    --result PC-29M 102 artifacts\v12\evaluations\screening\pc29m-seed-102.json `
    --result PC-44M 101 artifacts\v12\evaluations\screening\pc44m-seed-101.json `
    --result PC-44M 102 artifacts\v12\evaluations\screening\pc44m-seed-102.json `
    --result PC-64M 101 artifacts\v12\evaluations\screening\pc64m-seed-101.json `
    --result PC-64M 102 artifacts\v12\evaluations\screening\pc64m-seed-102.json `
    --output artifacts\v12\plans\scale-selection.json
```

Interpretation is unchanged:

- `selected`: continue with the smallest qualifying scale;
- `all-too-weak`: stop and preserve another negative result; do not pick PC-64M post hoc;
- `task-too-easy`: stop; do not continue to population cognition under this task boundary;
- `no-stable-band-model`: stop and inspect seed instability rather than choosing post hoc.

## Gate to population cognition and Experiment 2

Only `status=selected` unlocks the rest of Experiment 1.

The selected scale reuses screening seeds 101 and 102 and adds seeds 103 and 104 under the identical measured geometry, data, optimizer, and token budget. The full different-weight population/control comparison must then complete under its existing frozen gates.

Experiment 2 may consume the selected seed-101 checkpoint only after this recovery selection has succeeded and the checkpoint's exact execution, preflight, dataset, code-commit, and binary identities have been preserved.

No claim of plural-cognition advantage, architectural self-improvement, AGI, ASI, or recursive improvement follows merely from entering the capability band.
