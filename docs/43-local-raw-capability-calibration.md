# Local Raw Capability Calibration

## Status

Implementation prepared for the first capable-model calibration run. This gate uses **calibration material only**. It does not create, inspect, or execute the selection or confirmation task packs, and it does not instantiate the final operational configuration freeze.

## Purpose

`src/plural_cognition/collective/local_raw_calibration.py` measures the five already load-qualified frozen local candidates on the existing six-defect Repository Surgery calibration matrix.

The purpose is diagnostic:

```text
verify that the raw prompt/output protocol is usable
measure model difficulty on calibration material
measure parse validity and protected exact accuracy
measure target-machine inference resource use
identify protocol/resource settings that need adjustment before freeze
```

Calibration outcomes may change the eventual operational configuration. They cannot select the four-mind population or qualify plural uplift.

## Initial calibration probe

The provisional probe uses the already-qualified frozen runtime/model identities and preserves the load-preflight hardware condition:

```text
context tokens: 4096
maximum generated tokens: 2048
GPU layers: all
device: CUDA0
fit: off
split mode: none
main GPU: 0
KV cache: f16/f16
mmap: enabled
offline: true
temperature: 0
seed: 1
conversation mode: enabled
single turn: true
log verbosity: 4
maximum primary attempts: 1
```

These are **calibration settings**, not final bakeoff settings.

## Solver-visible boundary

For each calibration task the local model receives only:

```text
issue prompt
buggy repository files
public examples
```

The prompt builder does not include:

```text
clean repository files
gold patch
protected runtime inputs
protected expectations
mutation-generation metadata
```

Raw output is preserved content-addressably before any parsing or grading.

## Output contract

The first calibration parser accepts either:

```text
a raw unified diff
or
one single ```diff fenced block containing only a unified diff
```

It rejects prose before the patch, unsupported/multiple markdown fences, missing unified-diff hunks, NUL bytes, excessive patch size, absolute paths, Windows paths, and path traversal. Parsing failure is preserved as a calibration failure for that candidate/task; it is not silently repaired by another model call.

## Execution safety

Model-generated code is never executed on the ordinary host.

A successfully parsed patch is wrapped as a `RepositorySurgerySubmission` and evaluated only through the already-qualified Docker runner and the privileged black-box evaluator used by the project-authored calibration matrix. Invalid model output is not executed.

Infrastructure or qualified-runner failures abort the run rather than being counted as model failures.

## Evidence

The runner writes a fresh artifact root containing a content store, calibration task build material, runtime observation, raw model outputs through their content hashes, immutable raw `StageArtifact` identities, evaluation records for parsed patches, and a canonical `raw-calibration.json` report.

The report records per candidate/task:

```text
raw output identity
raw artifact identity
parse validity/mode/error
patch identity when valid
evaluation identity when executed
protected exact accuracy
protected evaluator valid rate
solved/not solved
elapsed inference time
peak GPU usage
peak process RSS
full-offload layer count
```

Candidate summaries report parse-valid count, solved count, mean exact accuracy, and peak resource observations.

## Scientific sequencing

After the calibration evidence exists:

1. inspect whether parsing, task difficulty, and resource ceilings are appropriate;
2. make any calibration-justified protocol changes before selection exists;
3. instantiate the final per-candidate `LocalOperationalConfigFreeze` bound to the accepted calibration evidence;
4. freeze the untouched selection task pack;
5. run the actual candidate-model bakeoff without retuning from selection outcomes.
