# Local Operational Configuration Contract

## Status

Preparatory contract only. **No final candidate operational configuration is frozen by this document.**

The model-source identities and target runtime are already frozen, and local load qualification is being completed one candidate at a time. The next scientific step is calibration of the raw capable-model condition. Calibration is explicitly allowed to change prompt/resource settings, so the final operational freeze must not be instantiated before calibration evidence exists.

## Purpose

`src/plural_cognition/collective/local_operational_config.py` provides the fail-closed identity contract that will bind each viable local candidate to the exact settings used in the selection bakeoff.

A final candidate operational identity binds:

```text
candidate ID
model-source freeze SHA-256
candidate source SHA-256
runtime SHA-256
raw llama.cpp execution protocol
prompt protocol SHA-256
output contract SHA-256
resource budget SHA-256
```

The resulting configuration SHA-256 becomes the `MindIdentity.configuration_sha256` for the candidate.

## Raw-mind invariants

The initial raw candidate condition remains deliberately weaker than the later capable harness. The contract rejects configurations that permit:

```text
more than one primary attempt
cross-mind communication
protected evaluator access
mutable memory carried between tasks
plural synthesis
online execution
```

The execution protocol also records the operational knobs that can affect comparability and resource use, including context/prediction limits, GPU placement, KV-cache type, mmap mode, temperature, seed, log verbosity, CPU threads, batch and microbatch sizes, and flash-attention selection.

## Calibration boundary

This source change does **not** choose the final values of those knobs.

The sequencing is:

1. finish the frozen local load-qualification gate;
2. run raw-capability calibration only on calibration material;
3. use calibration evidence to choose one predeclared operational configuration per viable candidate;
4. instantiate `LocalOperationalConfigFreeze` and bind the calibration-evidence SHA-256;
5. freeze the untouched selection task pack;
6. run the actual candidate bakeoff without retuning candidate operational settings from selection outcomes.

This preserves the existing rule that calibration may improve protocol correctness or task difficulty while selection and confirmation remain protected from post-hoc tuning.

## Fail-closed bindings

`LocalCandidateOperationalConfig.validate_against()` rejects drift in the model-source freeze, exact candidate source identity, or runtime identity.

`LocalOperationalConfigFreeze` additionally rejects duplicate candidate identities and requires an exact calibration-evidence digest before a final operational freeze can exist.

No `LOCAL_OPERATIONAL_CONFIG_FREEZE_V1` constant is intentionally defined yet. Adding such a constant is a later empirical transition and must cite the completed calibration evidence that justified its values.
