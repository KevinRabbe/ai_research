# Local Raw Calibration Output Channel v3

## Status

Calibration transport correction only. No selection/confirmation material is used, no candidate is selected, and no final operational configuration is frozen by this change.

## Preserved observation that motivated v3

The first completed Qwen3 boundary smoke at software revision `340b57746a2f58a7656e45acfeffc5aa7fbbe621` successfully loaded and ran the frozen model at `37/37` GPU layers, but the v1 parser received the entire interactive `llama-cli` process stdout stream. That stream contained the CLI banner, prompt echo, reasoning display, timing text, and the displayed assistant response. Consequently the strict response parser returned `model output contains unsupported markdown fencing` before candidate patch validation or protected evaluation.

That observation is preserved as output-channel-confounded evidence rather than a model capability score.

## Pinned-runtime basis

The frozen llama.cpp runtime is b10361 at upstream commit `14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840`.

At that exact source revision, `llama-cli` supports `--output-file` and `--simple-io`. Its CLI implementation writes a deterministic single-turn transcript to the output file. For each turn it writes the user message and then an `Assistant:` section. If server-side reasoning content exists, it is enclosed in `[Start thinking]` / `[End thinking]` markers before the assistant content.

V3 uses this runtime-defined output channel instead of treating UI stdout as candidate content.

## V3 transport contract

The generation, model, task, sampling, resource, full-offload, strict patch, Docker, and protected evaluator semantics remain those of the CI-qualified calibration runner. V3 changes only the answer transport identity:

```text
assistant_output_channel = llama-cli-output-file-single-turn-v1
process_stdout_role = diagnostic-only
reasoning_role = preserved-diagnostic-not-answer
simple_io = true
```

The protocol receives a new content-addressed identity.

For every model/task call V3 preserves:

1. the exact `llama-cli --output-file` transcript;
2. the process stdout UI stream as a diagnostic sidecar;
3. extracted reasoning as a diagnostic sidecar when present;
4. the exact assistant-content bytes as the candidate answer;
5. the existing stderr/load evidence;
6. a SHA-256 manifest over output-channel sidecars.

Only item 4 is passed to the existing strict unified-diff parser. V3 does not repair, synthesize, or normalize a candidate patch. If the assistant content contains a malformed/no-op diff, the same strict qualified-Docker grammar rejects it and that rejection becomes a genuine raw-model output observation.

## Scientific interpretation

The earlier Qwen3 smoke already suggests an important distinction: its visible reasoning diagnosed the boundary condition correctly, while its displayed final diff appears malformed and may omit the actual replacement. V3 must not correct that discrepancy. The purpose of the new transport is only to establish what the model's assistant answer actually was, free of CLI UI contamination.

After V3 passes CI, the next target action is a fresh Qwen3 boundary smoke under a new artifact root. If the isolated assistant answer is valid, it is evaluated through the qualified Docker path. If it is structurally invalid, the invalid answer is recorded directly without Docker execution.
