# Local raw calibration prompt transport v4

## Purpose

V3 successfully separated llama.cpp's process UI from its `--output-file`
assistant transcript, but the first target run failed before candidate parsing with:

```text
status=LOCAL_RAW_CALIBRATION_FAIL
error=llama output transcript does not bind the supplied prompt
```

The preserved target transcript established that this was a prompt-transport
failure rather than a model-capability result.

## Target observation

The solver-visible Repository Surgery source contains this literal Python text:

```python
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
```

In the v3 target transcript, the two source bytes `\\` + `n` had become an actual
line break inside the quoted Python string.  The pinned llama.cpp CLI defaults to
escape processing for `-p`, so source-like sequences such as `\n`, `\r`, and
`\t` are not byte-preserving unless escape processing is disabled.

The pinned CLI implementation also removes one terminal LF from the argument
prompt before constructing the user message.  V1's prompt builder intentionally
included one final LF, so the old stored prompt SHA named one byte that the
runtime discarded.

## V4 correction

V4 makes two calibration-only transport changes:

1. remove exactly the builder's final LF before content-addressing and passing
   the prompt; and
2. pass `--no-escape` to the pinned llama.cpp CLI.

The result is a literal argv prompt whose stored SHA-256 identifies the same
user-message bytes presented to the model.  Embedded repository backslashes are
preserved rather than interpreted by the CLI.

V4 retains v3's `--simple-io` plus `--output-file` answer channel.  Reasoning is
preserved as diagnostic evidence but excluded from candidate answer parsing.
Process stdout remains diagnostic-only.

## Unchanged scientific boundary

V4 does not change:

- the six project-authored calibration tasks;
- calibration/selection split separation;
- one primary model call per task;
- temperature, seed, context, prediction budget, KV type, GPU offload, or timeout;
- the strict unified-diff output contract;
- host-side structural parsing rules;
- the qualified Docker execution boundary;
- privileged black-box grading;
- the prohibition on communication, protected-evaluator access, mutable memory,
  plural synthesis, or undeclared retries.

V1, V2, and V3 source and failed evidence remain preserved.  A V4 run is a fresh
calibration attempt with a new protocol identity and a fresh artifact root.  It
must not be compared as if the earlier transport-confounded `parsed=False`
observations were model scores.
