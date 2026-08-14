# Consumed-selection V4 development outcome freeze

This record freezes the completed V4 whole-file development experiment over the already-consumed V1 Repository Surgery selection material. It is development evidence only and cannot support a new selection or generalization claim.

## Bound evidence

- V4 software revision: `671e5f41c171f3e2be2a6a06f9ae7e17394e43df`
- V4 development protocol SHA-256: `79a137d27b83ad0faa529878f440e6da142f00cc6588048316e063fa7fd0b616`
- frozen V1 selection report SHA-256: `cfb56dd84564db7de09be590c93107cf7d2c7e76f8971eabbe41a2f8926826fd`
- targeted V4 report SHA-256: `9d6aa926135b0392bc7d19b9dc018249d0555d581f49c5776fb0cba81268f8be`
- targeted V4 output manifest SHA-256: `42179e1598287a7b0676a2ab566281983d25b25e05f5f4b48e13115d2d94d93c`
- remainder V4 report SHA-256: `bf9653f7ff9c78f88a9a759498ac76b85b3db902e6bdc2bc6f7200b493986f2f`
- remainder V4 output manifest SHA-256: `94ef8646d67e8b7ef9a03c7c27e7dc22927a942d39ef44c56545c5d8af1a233a`
- content-addressed outcome freeze SHA-256: `93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a`

The targeted report contains 12 observations. The remainder report contains the disjoint other 36 observations. Together they bind exactly 48 unique candidate-task pairs over four candidates and all twelve consumed tasks.

## Result

The comparable four-candidate V1 baseline was 43/48 parse-valid and 42/48 solved. V4 improved the combined matrix to 47/48 parse-valid and 45/48 solved.

Per candidate:

- `qwen3-8b-q8`: V1 9/12 parsed, 9/12 solved; V4 12/12 parsed, 11/12 solved.
- `qwen2.5-coder-14b-q5km`: V1 11/12 parsed, 11/12 solved; V4 12/12 parsed, 12/12 solved.
- `devstral-24b-q4km`: V1 11/12 parsed, 11/12 solved; V4 12/12 parsed, 12/12 solved.
- `deepseek-coder-v2-lite-q5km`: V1 12/12 parsed, 11/12 solved; V4 11/12 parsed, 10/12 solved.

The predeclared continuation rule required all four candidates to be 12/12 parse-valid, each candidate to meet or exceed its V1 solved count, and at least 42/48 solves overall. V4 therefore **rejects** despite improving aggregate parse validity and solves, because DeepSeek regressed to 11/12 parse-valid and 10/12 solved.

## Frozen failure/partial observations

Three combined observations were not solved:

1. DeepSeek on `repository-surgery-selection-error-handling-0002`: parse-valid, evaluator-valid, exact accuracy 0.5. This is a semantic repair failure, not an output-serialization failure.
2. Qwen3 on `repository-surgery-selection-multi-file-0001`: parse-valid but evaluator-valid rate 0.0. The candidate inserted a SEARCH/REPLACE-style divider and duplicate function body into the complete replacement content for `fees.py`, producing invalid program behavior.
3. DeepSeek on `repository-surgery-selection-multi-file-0001`: parse-invalid because it returned an unchanged full-file block for `app.py` rather than changing the defective `fees.py`; the deterministic V4 interpreter rejected the unchanged block.

These observations show that whole-file replacement removed most of the V1 serialization/anchor failures but did not satisfy the frozen per-candidate non-regression gate. No parser loosening or reinterpretation is permitted after this result.

## Scientific consequence

V4 is preserved as negative development evidence under its predeclared continuation rule. The consumed V1 task split may continue to be used for diagnostic/development work, but it must never be reused as fresh selection evidence. Any future candidate protocol that survives development must be frozen before a newly authored untouched selection pack is created and run exactly once.
