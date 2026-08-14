# Qualified Selection Pack Freeze V1

## Status

The untouched Repository Surgery selection pack has now passed target qualification before any candidate-model selection inference.

The exact source revision that generated and qualified the pack is:

```text
5b1c3724ba98f401b2367a1f8fa8bc10764fee0f
```

The frozen target evidence is:

```text
selection_pack_sha256=
0530c682bbd4b4e7153142cba8350990ff3e2fad578cd765a4a2d9d8207d331d

qualification_report_sha256=
c8f98e2f9458d86c29f0323f0873faad5c9c6fdb2ed2e0839e20fc5c59aa28dd

operational_config_freeze_sha256=
448f72a61f320017138b5222cfed4673d001478e17bb7bc21185e04e8874066f

qualified_docker_report_sha256=
2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04

task_count=12
```

## Qualification result

All twelve project-authored buggy repositories remained observably defective. All twelve project-authored gold repairs reached exact accuracy `1.0` and evaluator valid rate `1.0` through the existing qualified Docker path.

The pack contains two tasks in each of the six frozen defect families:

```text
api-contract
boundary
error-handling
local-logic
multi-file-behavior
state-management
```

The V8 prompt transport compatibility preflight also passed on the target machine: the raw V8 builder retains its expected terminal LF and the V4 literal transport removes exactly that LF before runtime delivery.

## Freeze rule

From this point onward the selection pack is immutable experimental material.

Do not change, in response to selection outcomes:

- task repositories or issue prompts;
- public or protected cases;
- protected evaluator configuration;
- candidate identities;
- V8 structured-edit prompt/output semantics;
- final operational resource settings.

The frozen source module is not rewritten after qualification. `repository_surgery_selection_freeze_v1.py` records the target pack/report digests and validates their binding to the already-frozen operational configuration and qualified Docker identity.

## Scientific boundary

This freeze is not a candidate result and does not choose the final four minds. No candidate-model selection inference was run during pack qualification.

The next empirical action is the five-candidate raw-mind selection bakeoff on this exact twelve-task pack. Candidate outcomes may be used only by the already-frozen deterministic population-selection rule.
