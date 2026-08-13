# Local Raw Calibration Runtime Probe v2

## Scope

This is an infrastructure-only wrapper around the existing raw-capability calibration runner. It does **not** change the model prompt, context length, generation limit, temperature, seed, GPU placement, patch parser, qualified Docker execution path, privileged evaluator, task material, or scoring semantics.

The target-machine smoke at revision `fdeb25002e580716a89003a9e762911e3e8fea8e` terminated before any model inference because `llama-cli --version` exceeded the inherited fixed 30-second provenance-probe timeout. No calibration artifact root had been created and no model capability result was produced.

## Change

`local_raw_calibration_v2.py` preserves the frozen runtime identity checks but gives `--version` and `--list-devices` two bounded attempts, each with a 60-second timeout and a 2-second delay between attempts. Python's `subprocess.run(..., timeout=...)` terminates the timed-out child before the retry.

If both attempts time out, the wrapper raises a `RuntimeError`; the existing calibration CLI reports `LOCAL_RAW_CALIBRATION_FAIL` cleanly. Version drift, nonzero exit status, or absence of `CUDA0` still fail closed.

## Scientific boundary

A runtime-probe retry is not a model retry. The raw-mind protocol still permits exactly one model-generation attempt per candidate/task. This change only prevents a transient executable-startup stall in the pre-inference provenance check from being misclassified as model capability evidence.
