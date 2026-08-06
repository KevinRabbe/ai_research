# SI-V1 Frozen-Weight Self-Improvement Execution Procedure

## 1. Purpose

This document defines the exact operational sequence for the first architectural self-improvement experiment.

The experiment is independent of the plural-cognition claim. It reuses one frozen Boolean-world checkpoint, but it does not require a positive plural-population result.

The causal sequence is:

```text
train one frozen checkpoint
→ generate immutable candidate paths without target access
→ freeze discovery, development, hidden, and shift pools
→ freeze genome, budgets, controls, and thresholds
→ search on discovery/development only
→ write an immutable finalist manifest
→ open hidden/shift targets for those finalists only
→ repeat for three independent task/path seeds
→ apply the multi-run qualification gate
```

## 2. Exact-code requirement

CUDA preflight, checkpoint training, and target-free candidate generation must use the same Git commit.

The SI branch is stacked on the complete plural-cognition harness, so the recommended execution checkout is:

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

The working tree must be clean.

Do not reuse a checkpoint whose execution manifest binds a different Git commit. The command rejects that combination.

## 3. Frozen checkpoint

Use the automatically selected model scale from Version 1 screening.

The predeclared checkpoint is:

```text
selected model scale
initialization seed 101
final 10-million-token screening checkpoint
```

This choice is fixed before SI candidate-pool results.

Required paths are represented below as:

```text
<EXECUTION>  selected seed-101 execution manifest
<PREFLIGHT>  measured CUDA preflight JSON
<CHECKPOINT> selected seed-101 final checkpoint
```

The checkpoint is identical across all SI replications. Replications vary task seeds and candidate-sampling seeds.

## 4. Frozen run identities

Run 1:

```text
task base seed:       20260821
shift base seed:      30260821
candidate seeds:      401 402 403 404 405 406 407 408
```

Run 2:

```text
task base seed:       20260822
shift base seed:      30260822
candidate seeds:      501 502 503 504 505 506 507 508
```

Run 3:

```text
task base seed:       20260823
shift base seed:      30260823
candidate seeds:      601 602 603 604 605 606 607 608
```

Do not replace a failed run with a new seed after inspecting its result.

## 5. Task partitions per run

Each run contains:

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

This is deeper, denser, and more conditional than the standard training distribution.

## 6. Build one run’s task shards

The following example is Run 1. Replace only the documented run seeds and root directory for Runs 2 and 3.

```powershell
$Run = "r1"
$TaskSeed = 20260821
$ShiftSeed = 30260821
$Root = "artifacts\si\$Run"

New-Item -ItemType Directory -Force "$Root\tasks" | Out-Null

plural-cognition-si-build-tasks `
    --split validation `
    --profile standard `
    --start-index 0 `
    --example-count 256 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\discovery.jsonl" `
    --manifest "$Root\tasks\discovery.manifest.json"

plural-cognition-si-build-tasks `
    --split validation `
    --profile standard `
    --start-index 256 `
    --example-count 256 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\development.jsonl" `
    --manifest "$Root\tasks\development.manifest.json"

plural-cognition-si-build-tasks `
    --split test `
    --profile standard `
    --start-index 0 `
    --example-count 512 `
    --base-seed $TaskSeed `
    --output "$Root\tasks\hidden.jsonl" `
    --manifest "$Root\tasks\hidden.manifest.json"

plural-cognition-si-build-tasks `
    --split test `
    --profile shift-v1 `
    --start-index 0 `
    --example-count 512 `
    --base-seed $ShiftSeed `
    --output "$Root\tasks\shift.jsonl" `
    --manifest "$Root\tasks\shift.manifest.json"
```

Targets exist in these supervised shard files for later scoring, but target-free generation decodes only the public prefix before the answer boundary.

## 7. Dry-run target-free generation

Validate every split before allocating CUDA state.

```powershell
$Seeds = 401,402,403,404,405,406,407,408

plural-cognition-si-generate-pool `
    --execution <EXECUTION> `
    --preflight <PREFLIGHT> `
    --checkpoint <CHECKPOINT> `
    --task-shard "$Root\tasks\discovery.jsonl" "$Root\tasks\discovery.manifest.json" `
    --sampling-seeds $Seeds `
    --temperature 1.0 `
    --top-k 8 `
    --max-new-tokens 64 `
    --artifact-dir "$Root\generation\discovery" `
    --pool-output "$Root\pools\discovery.json" `
    --dry-run
```

Repeat the dry run for development, hidden, and shift.

The dry run verifies:

- execution manifest;
- task data and manifest contents;
- sorted and contiguous shard ranges;
- checkpoint path existence;
- unique ordered sampling seeds.

It does not load the model.

## 8. Generate the four immutable pools

Create directories:

```powershell
New-Item -ItemType Directory -Force "$Root\generation" | Out-Null
New-Item -ItemType Directory -Force "$Root\pools" | Out-Null
```

Discovery:

```powershell
plural-cognition-si-generate-pool `
    --execution <EXECUTION> `
    --preflight <PREFLIGHT> `
    --checkpoint <CHECKPOINT> `
    --task-shard "$Root\tasks\discovery.jsonl" "$Root\tasks\discovery.manifest.json" `
    --sampling-seeds $Seeds `
    --temperature 1.0 `
    --top-k 8 `
    --max-new-tokens 64 `
    --artifact-dir "$Root\generation\discovery" `
    --pool-output "$Root\pools\discovery.json"
```

Repeat with the corresponding task files and output directories for:

```text
development
hidden
shift
```

Each command:

1. verifies the complete task shard;
2. verifies exact commit, preflight hash, GPU, execution, and checkpoint;
3. loads the checkpoint once;
4. generates all eight paths;
5. writes one canonical target-free artifact per sampling seed;
6. writes one canonical content-addressed candidate pool.

The generation artifacts contain no target expression, hidden score, exact score, or semantic score.

## 9. Freeze the complete experiment

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

This freezes:

- all four candidate-pool hashes;
- task-shard hashes and counts;
- checkpoint and execution identities;
- all eight generation protocols;
- immutable parent;
- fixed verified-synthesis policy;
- genome-evaluation budget;
- archive capacity;
- per-task reasoning ceiling;
- bootstrap and shuffled-label seeds;
- minimum hidden gain.

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

The search command has no hidden or shift file arguments.

It runs:

- immutable parent replay;
- single-best lineage;
- quality-diverse archive;
- equal-budget random genome search;
- shuffled-label quality-diverse search.

Target-free packets are prepared once per task. Deterministic genome fitness is cached across normal strategies, but each strategy retains its full logical genome-evaluation count.

The command writes a separate physical finalist manifest. Hidden opening requires that exact file.

## 11. Open hidden and shift results

Only after the search command has completed and `finalists.json` exists:

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

The command rejects:

- changed experiment manifest;
- changed search phase;
- finalist file not matching the embedded finalist hash;
- changed hidden or shift pool;
- changed task-shard identity or contents;
- finalists not produced by the frozen searches.

The predeclared primary is the archive development champion. No new champion is selected after hidden scores appear.

## 12. Single-run gate

A run passes only when the archive champion:

1. gains at least 5 percentage points in hidden semantic accuracy over the immutable parent;
2. has a paired 95% bootstrap lower bound above zero;
3. improves the shift split;
4. beats the equal-budget random-search champion;
5. remains under the 1,024-operation per-task ceiling;
6. beats the shuffled-label champion.

The report also contains:

- all eight finalist evaluations;
- task-level outputs and scores;
- win/tie/loss counts;
- exact-accuracy gain;
- immediate archive-parent reversion when available;
- hidden and shift compute;
- canonical hashes.

## 13. Repeat Runs 2 and 3

Repeat Sections 6–12 exactly with:

```text
Run 2 root:             artifacts\si\r2
Task seed:              20260822
Shift seed:             30260822
Candidate seeds:        501–508

Run 3 root:             artifacts\si\r3
Task seed:              20260823
Shift seed:             30260823
Candidate seeds:        601–608
```

Keep all failed, invalid, and inconclusive artifacts.

## 14. Apply the three-run strong qualification

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

The strong gate requires:

- three distinct experiment hashes;
- independent four-split candidate-pool hash vectors;
- every single-run gate passing;
- mean hidden gain at least 5 percentage points;
- every run’s hidden interval lower bound above zero;
- run-level bootstrap lower bound above zero;
- pooled-task bootstrap lower bound above zero;
- positive shift gain in every run.

## 15. Interpretation boundary

A passing three-run artifact supports only:

> Under frozen neural weights, frozen proposal pools, fixed public tasks, fixed reasoning ceilings, and a hidden-evaluator firewall, the bounded evolutionary process repeatedly discovered an external reasoning-policy descendant that generalized better than its immutable parent and matched controls.

It does not establish:

- neural-weight self-improvement;
- unrestricted source-code self-modification;
- recursive open-ended improvement;
- autonomous deployment safety;
- AGI or ASI.

## 16. Artifact preservation

Preserve for every run:

```text
task JSONL files and manifests
eight generation artifacts per split
four candidate pools
experiment manifest
complete search phase
physical finalist manifest
hidden-opening result
all failures and command logs
```

Never overwrite a completed run. A rerun uses a new directory and remains linked to its exact hashes.
