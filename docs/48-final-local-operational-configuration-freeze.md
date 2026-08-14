# Final Local Operational Configuration Freeze

## Status

Calibration is closed. This document freezes the raw local candidate operational configuration that must be used when the untouched selection split is constructed and evaluated.

No candidate is removed or promoted by calibration. All five source-frozen candidates remain in the population presented to the later deterministic bakeoff.

## Calibration evidence bound by the freeze

The completed V8 structured-edit calibration matrix is the primary usability/capability evidence:

```text
software_revision=d0fdb8b65b25a439ac296fd711cd7927a48d323e
report_sha256=83a8f4fb40195118d6eb2194bbf193cdd9af79793eec3cd53395aa6c20d4d437
protocol_sha256=c4eb980a4cf882f6621837a5cc205a143722459915358f8d8997d3c11ba79f82
candidate_count=5
task_count=6
result_count=30
parsed=24/30
solved=20/30
```

The bounded V9 Gemma-only resource probe tested one final calibration hypothesis: whether doubling only Gemma's generation ceiling from 2048 to 4096 would make it operationally able to return a structured answer. It did not:

```text
software_revision=b19f387b6a4e30ec128064c26a741cd2b14e9f41
report_sha256=32dc48fe87c082e6e11f1fdad2fc4dd9d6f8bc56672f6e5f87f5aab68dd03b19
protocol_sha256=f0a90df09b8d86b61fd8c14f1625fdfaae71b5dea7cb68b5ed7d92601db0c74c
candidate_count=1
task_count=6
result_count=6
parsed=0/6
solved=0/6
```

The 4096-token Gemma override is therefore rejected. The final resource ceiling returns to the shared V8 value of 2048 generated tokens for every candidate. No further calibration-driven rescue tuning is permitted.

## Exact final raw protocol

The preserved V8 stderr observations established the effective default runtime knobs used by every candidate:

```text
context_tokens=4096
predict_tokens=2048
cpu_threads=16
cpu_threads_batch=16
batch_tokens=2048
microbatch_tokens=512
flash_attention_mode=auto
device=CUDA0
gpu_layers=all
fit=off
split_mode=none
main_gpu=0
cache_type_k=f16
cache_type_v=f16
load_mode=mmap
offline=true
temperature=0.0
seed=1
log_verbosity=4
single_turn=true
max_attempts=1
```

`flash_attention_mode=auto` intentionally records the requested llama.cpp mode rather than rewriting it into per-model booleans after observing runtime fallback. With the frozen runtime and hardware, auto enabled Flash Attention for Qwen3, Qwen2.5-Coder, Gemma, and Devstral, while pinned llama.cpp reported that DeepSeek's layer/device support forced Flash Attention off. The operational input remains `auto` for all five.

The transport remains the V6/V8 transport: single-turn conversation mode, `--simple-io`, output-file assistant capture, literal `--no-escape` prompt transport, no terminal prompt LF, and reasoning preserved only as diagnostic material.

## Output protocol

The final candidate serialization contract is V8 structured edits:

```text
candidate_output=exact-replace-json-v1
interpreter=deterministic-canonical-unified-diff-v1
structured_edit_max_count=32
path_scope=solver-visible-existing-files-only-v1
old_match=exactly-once-current-file-state-v1
edit_application=listed-order-v1
candidate_output_repair=false
patch_validation=qualified-docker-unified-diff-grammar-v1
```

The raw model JSON remains the candidate-authored output. The harness does not repair malformed candidate content. A structurally valid candidate edit is deterministically materialized into a canonical unified diff and only that patch is executed through the qualified Docker evaluator.

## Population and scientific boundary

The final operational freeze preserves these five candidate IDs, in frozen order:

```text
qwen3-8b-q8
qwen2.5-coder-14b-q5km
gemma4-12b-it-qat-q4
devstral-24b-q4km
deepseek-coder-v2-lite-q5km
```

Calibration performance is not used to drop Gemma or choose the final four. The later selection split remains untouched and does the actual candidate bakeoff under a predeclared deterministic selection rule.

This freeze does establish that capable-model-generated Repository Surgery repairs have been executed and graded under qualified Docker on calibration material. It does not establish plural uplift, select the final four, implement mature synthesis, or permit candidate access to protected evaluation state.

## Next dependency

After this freeze is CI-qualified and content-addressed, construct and freeze the untouched selection task pack. From that point onward, do not change candidate identities, prompt/output protocol, resource settings, task definitions, or evaluation rules in response to selection outcomes.
