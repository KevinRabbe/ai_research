# V1 Execution and Analysis Procedure

## Purpose

This document defines the exact operational path from the qualified repository to the first empirical plural-cognition result.

The GPU-independent software is prepared in advance. When the RTX 4060 Ti becomes available, the remaining sequence is:

```text
measure GPU
→ resolve six screening runs
→ train and evaluate three scales × two seeds
→ select the smallest qualified scale
→ add two seeds to form four different-weight members
→ evaluate the different-weight population
→ evaluate four sampled paths from one checkpoint
→ compare the two conditions with paired statistics
```

No manual model-size choice, microbatch choice, task subset, checkpoint scoring rule, or result threshold should be changed after results are visible.

## 1. Install and qualify the repository

```powershell
cd F:\ai_research

git fetch origin
git switch -C agent/plural-cognition-research-foundation `
    origin/agent/plural-cognition-research-foundation

python -m pip install -e ".[dev,train]"
pytest
```

Record:

```powershell
git rev-parse HEAD
git status --short
python --version
python -c "import torch; print(torch.__version__)"
```

The working tree must be clean before the measured CUDA preflight.

## 2. Build the reusable datasets on CPU

The 10-million-token screening budget resolves to 306 complete optimizer steps:

```text
306 steps
× 32,768 padded tokens per step
= 10,027,008 effective padded tokens

306 steps
× 128 examples per step
= 39,168 training examples
```

Build one shared training shard and one frozen validation shard:

```powershell
New-Item -ItemType Directory -Force artifacts\datasets | Out-Null

plural-cognition-build-dataset `
    --split train `
    --start-index 0 `
    --example-count 39168 `
    --data-seed 20260806 `
    --catalog-size 128 `
    --output artifacts\datasets\train-000.jsonl `
    --manifest artifacts\datasets\train-000.manifest.json

plural-cognition-build-dataset `
    --split validation `
    --start-index 0 `
    --example-count 512 `
    --data-seed 20260806 `
    --catalog-size 128 `
    --output artifacts\datasets\validation-000.jsonl `
    --manifest artifacts\datasets\validation-000.manifest.json
```

All model scales and seeds use these exact content-addressed files.

Do not regenerate a different dataset for another model or seed.

## 3. Run the measured CUDA preflight

Run this only when the RTX 4060 Ti is otherwise idle.

```powershell
New-Item -ItemType Directory -Force artifacts\preflight | Out-Null

plural-cognition-cuda-preflight `
    --models pc-4m pc-10m pc-18m `
    --sequence-lengths 128 256 `
    --microbatches 16 32 64 128 256 `
    --precision auto `
    --warmup-steps 5 `
    --measured-steps 20 `
    --vram-limit-gb 13.5 `
    --seed 20260806 `
    --output artifacts\preflight\cuda-preflight.json
```

The preflight output binds:

- exact Git commit;
- GPU name;
- PyTorch and CUDA environment;
- selected precision;
- measured throughput;
- peak VRAM;
- OOM and resource-limit failures.

## 4. Resolve the six-run screening plan

```powershell
New-Item -ItemType Directory -Force artifacts\plans | Out-Null

plural-cognition-resolve-screening `
    --preflight artifacts\preflight\cuda-preflight.json `
    --initialization-seeds 101 102 `
    --data-seed 20260806 `
    --output artifacts\plans\screening-plan.json
```

For each model, the resolver chooses the fastest measured 256-token microbatch that:

- completed successfully;
- remained within the 13.5 GB allocated-VRAM ceiling;
- does not exceed 32,768 tokens per microbatch;
- divides the matched 32,768-token optimizer batch exactly.

Create all six dataset-bound execution manifests:

```powershell
plural-cognition-prepare-screening-executions `
    --screening-plan artifacts\plans\screening-plan.json `
    --training-manifests artifacts\datasets\train-000.manifest.json `
    --validation-manifests artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\executions\screening
```

Expected files:

```text
execution-pc4m-seed-101.json
execution-pc4m-seed-102.json
execution-pc10m-seed-101.json
execution-pc10m-seed-102.json
execution-pc18m-seed-101.json
execution-pc18m-seed-102.json
```

## 5. Validate each execution without training

Example:

```powershell
plural-cognition-train `
    --execution artifacts\executions\screening\execution-pc10m-seed-101.json `
    --preflight artifacts\preflight\cuda-preflight.json `
    --training-shard `
        artifacts\datasets\train-000.jsonl `
        artifacts\datasets\train-000.manifest.json `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\runs\screening\pc10m-seed-101 `
    --dry-run
```

The dry run verifies the complete dataset contents and manifests without allocating a model or CUDA optimizer state.

Run the dry check for every execution before starting the first training run.

## 6. Train the six screening runs

Example:

```powershell
plural-cognition-train `
    --execution artifacts\executions\screening\execution-pc10m-seed-101.json `
    --preflight artifacts\preflight\cuda-preflight.json `
    --training-shard `
        artifacts\datasets\train-000.jsonl `
        artifacts\datasets\train-000.manifest.json `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\runs\screening\pc10m-seed-101
```

The command:

- rejects the wrong Git commit, preflight file, GPU, datasets, or model configuration;
- uses the resolved microbatch and exact gradient accumulation;
- writes atomic progress and checkpoint files;
- binds checkpoints to the complete execution manifest and dataset hashes;
- can resume only from a matching execution checkpoint.

Resume example:

```powershell
plural-cognition-train `
    --execution artifacts\executions\screening\execution-pc10m-seed-101.json `
    --preflight artifacts\preflight\cuda-preflight.json `
    --training-shard `
        artifacts\datasets\train-000.jsonl `
        artifacts\datasets\train-000.manifest.json `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\runs\screening\pc10m-seed-101 `
    --resume artifacts\runs\screening\pc10m-seed-101\checkpoint-current.pt
```

## 7. Evaluate each screening checkpoint greedily

Example:

```powershell
New-Item -ItemType Directory -Force artifacts\evaluations\screening | Out-Null

plural-cognition-evaluate `
    --execution artifacts\executions\screening\execution-pc10m-seed-101.json `
    --preflight artifacts\preflight\cuda-preflight.json `
    --checkpoint artifacts\runs\screening\pc10m-seed-101\checkpoint-final.pt `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --output artifacts\evaluations\screening\pc10m-seed-101.json
```

Do not supply `--sampling-seed` during model-scale evaluation. Scale selection requires greedy artifacts.

Evaluate all six runs.

## 8. Select the smallest qualified scale

```powershell
plural-cognition-select-scale `
    --result PC-4M 101 artifacts\evaluations\screening\pc4m-seed-101.json `
    --result PC-4M 102 artifacts\evaluations\screening\pc4m-seed-102.json `
    --result PC-10M 101 artifacts\evaluations\screening\pc10m-seed-101.json `
    --result PC-10M 102 artifacts\evaluations\screening\pc10m-seed-102.json `
    --result PC-18M 101 artifacts\evaluations\screening\pc18m-seed-101.json `
    --result PC-18M 102 artifacts\evaluations\screening\pc18m-seed-102.json `
    --output artifacts\plans\scale-selection.json
```

Frozen scale gate:

```text
minimum parse rate per seed: 95%
mean exact accuracy:          20%–70%
selection:                    smallest qualifying scale
```

If no scale qualifies, stop. Do not choose the closest model after seeing the results.

## 9. Create the four-member different-weight plan

The first population reuses selected-scale seeds 101 and 102 and adds seeds 103 and 104:

```powershell
plural-cognition-prepare-population-plan `
    --screening-plan artifacts\plans\screening-plan.json `
    --scale-selection artifacts\plans\scale-selection.json `
    --population-seeds 101 102 103 104 `
    --output artifacts\plans\population-plan.json

plural-cognition-prepare-screening-executions `
    --screening-plan artifacts\plans\population-plan.json `
    --training-manifests artifacts\datasets\train-000.manifest.json `
    --validation-manifests artifacts\datasets\validation-000.manifest.json `
    --output-dir artifacts\executions\population
```

Seeds 101 and 102 reuse their existing checkpoints and greedy evaluations. Only seeds 103 and 104 require new training.

Train and greedily evaluate seeds 103 and 104 using the same commands and shared datasets.

Use the fixed member mapping:

```text
M0 = initialization seed 101
M1 = initialization seed 102
M2 = initialization seed 103
M3 = initialization seed 104
```

## 10. Evaluate the different-weight population

```powershell
plural-cognition-evaluate-population `
    --member M0 artifacts\evaluations\population\selected-seed-101-greedy.json `
    --member M1 artifacts\evaluations\population\selected-seed-102-greedy.json `
    --member M2 artifacts\evaluations\population\selected-seed-103-greedy.json `
    --member M3 artifacts\evaluations\population\selected-seed-104-greedy.json `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --bootstrap-resamples 10000 `
    --bootstrap-seed 20260806 `
    --output artifacts\evaluations\population\different-weight.json
```

This artifact is classified as:

```text
different-checkpoint-greedy
```

It contains:

- every individual score;
- complete-selection and fragment-selection controls;
- verified and unverified synthesis ablations;
- exact coalition and Shapley attribution;
- graph hashes;
- novel synthesis and source necessity;
- aggregate bootstrap statistics;
- the internal population qualification decision.

## 11. Evaluate the same-checkpoint sampled control

Use the selected model's seed-101 checkpoint as the predeclared same-weight base.

Create four sampled evaluation artifacts with fixed base seeds:

```text
S0 = sampling seed 301
S1 = sampling seed 302
S2 = sampling seed 303
S3 = sampling seed 304
```

Example:

```powershell
plural-cognition-evaluate `
    --execution <SELECTED-SEED-101-EXECUTION.json> `
    --preflight artifacts\preflight\cuda-preflight.json `
    --checkpoint <SELECTED-SEED-101-CHECKPOINT-FINAL.pt> `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --sampling-seed 301 `
    --temperature 1.0 `
    --top-k 8 `
    --output artifacts\evaluations\population\same-weight-sample-301.json
```

Repeat for 302, 303, and 304 without changing temperature or top-k.

Combine the four paths:

```powershell
plural-cognition-evaluate-population `
    --member S0 artifacts\evaluations\population\same-weight-sample-301.json `
    --member S1 artifacts\evaluations\population\same-weight-sample-302.json `
    --member S2 artifacts\evaluations\population\same-weight-sample-303.json `
    --member S3 artifacts\evaluations\population\same-weight-sample-304.json `
    --validation-shard `
        artifacts\datasets\validation-000.jsonl `
        artifacts\datasets\validation-000.manifest.json `
    --bootstrap-resamples 10000 `
    --bootstrap-seed 20260806 `
    --output artifacts\evaluations\population\same-weight.json
```

This artifact must be classified as:

```text
same-checkpoint-sampled
```

If its analysis coverage is below 95%, the primary comparison is inconclusive rather than passed.

## 12. Apply the central paired condition gate

```powershell
plural-cognition-compare-conditions `
    --primary artifacts\evaluations\population\different-weight.json `
    --same-weight-control artifacts\evaluations\population\same-weight.json `
    --minimum-control-coverage 0.95 `
    --bootstrap-resamples 10000 `
    --bootstrap-seed 20260806 `
    --output artifacts\evaluations\population\condition-comparison.json
```

The final comparison requires:

1. the primary population is `different-checkpoint-greedy`;
2. the control is `same-checkpoint-sampled`;
3. both use the exact same validation rows;
4. the primary passes its internal synthesis gate;
5. the control has at least 95% analyzable tasks;
6. the paired different-weight synthesis-accuracy advantage has a 95% bootstrap lower bound above zero;
7. the paired different-weight synthesis-gain advantage has a 95% bootstrap lower bound above zero.

## 13. Interpretation boundary

A passing condition-comparison artifact supports only this claim:

> Under the frozen Boolean-world protocol, independently learned weights plus the same structured synthesis machinery produced a reproducible advantage over an equal four-path same-checkpoint sampling control.

It does not by itself establish:

- general intelligence;
- artificial superintelligence;
- recursive self-improvement;
- superiority on natural language or open-world tasks;
- that the current model architecture is the final architecture.

A failure remains informative. Preserve every manifest, checkpoint, evaluation, and rejected condition so the failure can be localized to learning, functional diversity, extraction, synthesis, verification, or the plural-cognition hypothesis itself.
