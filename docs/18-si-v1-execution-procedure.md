# SI-V1 Frozen-Weight Self-Improvement Execution Procedure

## 1. Purpose

This document defines the exact operational sequence for the first architectural self-improvement experiment.

The experiment is independent of the plural-cognition claim. It reuses one frozen Boolean-world checkpoint, but it does not require a positive plural-population result.

```text
reuse one exact frozen checkpoint
→ generate immutable candidate paths without target access
→ freeze discovery, development, hidden, and shift pools
→ freeze genome, budgets, controls, and thresholds
→ search on discovery/development only
→ write an immutable finalist manifest
→ open hidden/shift targets for those finalists only
→ repeat for three independent task/path seeds
→ apply the multi-run qualification gate
```

## 2. Two exact code identities

Checkpoint training and SI candidate generation are separate reproducibility boundaries.

### Frozen checkpoint identity

The checkpoint remains bound to its original:

- training Git commit;
- CUDA preflight hash;
- execution manifest;
- model configuration;
- optimizer state;
- dataset-shard hashes;
- checkpoint binary SHA-256.

The SI tooling does not weaken or rewrite that binding.

### SI generation identity

Candidate generation runs from the qualified SI branch. Every target-free generation artifact records:

```text
generation_git_commit
execution_sha256
checkpoint_sha256
task-shard manifest hashes
generation protocol
generated token IDs
```

All paths in one candidate pool must use the same SI generation commit. This allows the exact selected V1 checkpoint to be reused without retraining it merely because the external reasoning experiment was implemented later.

Prepare the SI checkout:

```powershell
cd F:\ai_research

git fetch origin
git switch -C agent/frozen-weight-self-improvement-foundation `
    origin/agent/frozen-weight-self-improvement-foundation

python -m pip install -e ".[dev,train]"
pytest

git rev-parse HEAD
git status --short
```

The SI working tree must be clean before candidate generation.

## 3. Frozen checkpoint

Use the automatically selected model scale from Version 1 screening.

The predeclared checkpoint is:

```text
selected model scale
initialization seed 101
final 10-million-token screening checkpoint
```

Required paths:

```text
<EXECUTION>  selected seed-101 execution manifest
<PREFLIGHT>  preflight JSON bound by that execution
<CHECKPOINT> selected seed-101 final checkpoint
```

The same checkpoint is used in all SI replications. Replications vary task seeds and sampling seeds only.

## 4. Frozen run identities

```text
Run 1
  task base seed:  20260821
  shift base seed: 30260821
  candidate seeds: 401 402 403 404 405 406 407 408

Run 2
  task base seed:  20260822
  shift base seed: 30260822
  candidate seeds: 501 502 503 504 505 506 507 508

Run 3
  task base seed:  20260823
  shift base seed: 30260823
  candidate seeds: 601 602 603 604 605 606 607 608
```

Do not replace a failed run with a new seed after inspecting its result.

## 5. Task partitions per run

```text
discovery:   256 standard validation tasks, indices 0–255
development: 256 standard validation tasks, indices 256–511
hidden:      512 standard test tasks, indices 0–511
shift:       512 shift-v1 test tasks, indices 0–511
```

`shift-v1` uses:

```text
variables:              6
atoms:                  5–6
maximum depth:          5
negation probability:   0.35
ITE probability:        0.35
maximum causal tokens:  256
```

## 6. Build one run’s task shards

Run 1 example:

```powershell
$Run = "r1"
$TaskSeed = 20260821
$ShiftSeed = 30260821
$Root = "artifacts\si\$Run"

New-Item -ItemType Directory -Force "$Root\tasks" | Out-Null

plural-cognition-si-build-tasks `
    --split validation --profile standard `
    --start-index 0 --example-count 256 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\discovery.jsonl" `
    --manifest "$Root\tasks\discovery.manifest.json"

plural-cognition-si-build-tasks `
    --split validation --profile standard `
    --start-index 256 --example-count 256 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\development.jsonl" `
    --manifest "$Root\tasks\development.manifest.json"

plural-cognition-si-build-tasks `
    --split test --profile standard `
    --start-index 0 --example-count 512 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\hidden.jsonl" `
    --manifest "$Root\tasks\hidden.manifest.json"

plural-cognition-si-build-tasks `
    --split test --profile shift-v1 `
    --start-index 0 --example-count 512 `
    --base-seed $ShiftSeed `
    --output "$Root\tasks\shift.jsonl" `
    --manifest "$Root\tasks\shift.manifest.json"
```

The supervised shard retains targets for later scoring. Target-free generation decodes only the public prefix before the answer boundary.

## 7. Dry-run candidate generation

```powershell
$Seeds = 401,402,403,404,405,406,407,408

plural-cognition-si-generate-pool `
    --execution <EXECUTION> `
    --preflight <PREFLIGHT> `
    --checkpoint <CHECKPOINT> `
    --task-shard "$Root\tasks\discovery.jsonl" "$Root\tasks\discovery.manifest.json" `
    --sampling-seeds $Seeds `
    --temperature 1.0 --top-k 8 --max-new-tokens 64 `
    --artifact-dir "$Root\generation\discovery" `
    --pool-output "$Root\pools\discovery.json" `
    --dry-run
```

Repeat for development, hidden, and shift.

The dry run verifies task contents, shard identities, checkpoint existence, ordered unique sampling seeds, and the current SI Git commit without loading CUDA state.

## 8. Generate immutable pools

```powershell
New-Item -ItemType Directory -Force "$Root\generation" | Out-Null
New-Item -ItemType Directory -Force "$Root\pools" | Out-Null

plural-cognition-si-generate-pool `
    --execution <EXECUTION> `
    --preflight <PREFLIGHT> `
    --checkpoint <CHECKPOINT> `
    --task-shard "$Root\tasks\discovery.jsonl" "$Root\tasks\discovery.manifest.json" `
    --sampling-seeds $Seeds `
    --temperature 1.0 --top-k 8 --max-new-tokens 64 `
    --artifact-dir "$Root\generation\discovery" `
    --pool-output "$Root\pools\discovery.json"
```

Repeat with the corresponding task file and output path for development, hidden, and shift.

Each command loads the checkpoint once and writes eight target-free path artifacts plus one content-addressed pool. The artifacts contain no target expression or accuracy score.

## 9. Freeze the experiment

```powershell
New-Item -ItemType Directory -Force "$Root\experiment" | Out-Null

plural-cognition-si-prepare `
    --discovery-pool "$Root\pools\discovery.json" `
    --development-pool "$Root\pools\development.json" `
    --hidden-pool "$Root\pools\hidden.json" `
    --shift-pool "$Root\pools\shift.json" `
    --generations 8 `
    --max-genome-evaluations 64 `
    --archive-capacity 24 `
    --random-seed 20260806 `
    --max-candidate-inputs 8 `
    --max-packet-extractions 8 `
    --max-reasoning-operations 1024 `
    --bootstrap-resamples 10000 `
    --bootstrap-seed 20260806 `
    --shuffled-label-seed 20260807 `
    --minimum-hidden-gain 0.05 `
    --output "$Root\experiment\manifest.json"
```

Do not edit the manifest after search starts.

## 10. Run discovery/development search on CPU

```powershell
New-Item -ItemType Directory -Force "$Root\search" | Out-Null

plural-cognition-si-search `
    --experiment "$Root\experiment\manifest.json" `
    --discovery-pool "$Root\pools\discovery.json" `
    --development-pool "$Root\pools\development.json" `
    --discovery-shard "$Root\tasks\discovery.jsonl" "$Root\tasks\discovery.manifest.json" `
    --development-shard "$Root\tasks\development.jsonl" "$Root\tasks\development.manifest.json" `
    --output "$Root\search\search-phase.json" `
    --finalists-output "$Root\search\finalists.json"
```

The command has no hidden or shift inputs. It runs the immutable parent, single-best lineage, quality-diverse archive, equal-budget random search, and shuffled-label archive, then freezes the eight finalist roles.

## 11. Open hidden and shift targets

Only after `finalists.json` exists:

```powershell
New-Item -ItemType Directory -Force "$Root\results" | Out-Null

plural-cognition-si-open-hidden `
    --experiment "$Root\experiment\manifest.json" `
    --search-phase "$Root\search\search-phase.json" `
    --finalists "$Root\search\finalists.json" `
    --hidden-pool "$Root\pools\hidden.json" `
    --shift-pool "$Root\pools\shift.json" `
    --hidden-shard "$Root\tasks\hidden.jsonl" "$Root\tasks\hidden.manifest.json" `
    --shift-shard "$Root\tasks\shift.jsonl" "$Root\tasks\shift.manifest.json" `
    --output "$Root\results\hidden-opening.json"
```

The physical finalist file must exactly match the finalist hash embedded in the search phase. The predeclared primary is the archive development champion; hidden results cannot select a replacement.

## 12. Single-run gate

The archive champion must:

1. gain at least 5 percentage points in hidden semantic accuracy;
2. have a paired 95% lower bound above zero;
3. improve the shift split;
4. beat equal-budget random search;
5. remain below 1,024 reasoning operations per task;
6. beat the shuffled-label champion.

## 13. Repeat Runs 2 and 3

```text
Run 2 root:      artifacts\si\r2
Task seed:       20260822
Shift seed:      30260822
Candidate seeds: 501–508

Run 3 root:      artifacts\si\r3
Task seed:       20260823
Shift seed:      30260823
Candidate seeds: 601–608
```

Preserve failed and inconclusive runs.

## 14. Apply the strong three-run gate

```powershell
plural-cognition-si-qualify `
    --run artifacts\si\r1\experiment\manifest.json artifacts\si\r1\results\hidden-opening.json `
    --run artifacts\si\r2\experiment\manifest.json artifacts\si\r2\results\hidden-opening.json `
    --run artifacts\si\r3\experiment\manifest.json artifacts\si\r3\results\hidden-opening.json `
    --minimum-runs 3 `
    --minimum-mean-gain 0.05 `
    --bootstrap-resamples 10000 `
    --bootstrap-seed 20260806 `
    --output artifacts\si\qualification.json
```

The strong gate requires distinct experiment and split-pool hashes, all single-run gates passing, positive individual hidden lower bounds, positive run-level and pooled-task lower bounds, and positive shift gain in every run.

## 15. Claim boundary

A passing result supports only bounded frozen-weight improvement of an external reasoning policy under exact candidate pools and resource ceilings. It does not establish unrestricted recursive self-improvement, neural-weight evolution, AGI, or ASI.

## 16. Preserve every artifact

For each run preserve:

```text
task JSONL files and manifests
eight generation artifacts per split
four candidate pools
experiment manifest
complete search phase
physical finalist manifest
hidden-opening report
command logs and failures
```

Never overwrite a completed run.
