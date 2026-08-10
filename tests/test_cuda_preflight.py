import json

import pytest

from plural_cognition.cuda_preflight import (
    DEFAULT_MICROBATCHES,
    DEFAULT_MODELS,
    DEFAULT_SEQUENCE_LENGTHS,
    SweepCase,
    _parser,
    build_sweep_cases,
    main,
    run,
)


def test_default_sweep_is_ordered_and_complete() -> None:
    cases = build_sweep_cases(
        DEFAULT_MODELS,
        DEFAULT_SEQUENCE_LENGTHS,
        DEFAULT_MICROBATCHES,
    )

    assert len(cases) == 6 * 2 * 5
    assert cases[0] == SweepCase("pc-4m", 128, 16)
    assert cases[-1] == SweepCase("pc-64m", 256, 256)


def test_sweep_rejects_unknown_duplicate_and_invalid_values() -> None:
    with pytest.raises(ValueError):
        build_sweep_cases(("unknown",), (128,), (16,))
    with pytest.raises(ValueError):
        build_sweep_cases(("pc-4m", "pc-4m"), (128,), (16,))
    with pytest.raises(ValueError):
        build_sweep_cases(("pc-4m",), (128, 128), (16,))
    with pytest.raises(ValueError):
        build_sweep_cases(("pc-4m",), (128,), (0,))
    with pytest.raises(ValueError):
        build_sweep_cases(("pc-4m",), (257,), (1,))


def test_list_only_requires_no_cuda_and_returns_serializable_plan() -> None:
    args = _parser().parse_args(
        [
            "--models",
            "pc-10m",
            "--sequence-lengths",
            "128",
            "256",
            "--microbatches",
            "16",
            "32",
            "--list-only",
        ]
    )
    payload = run(args)

    assert payload["mode"] == "list_only"
    assert len(payload["cases"]) == 4
    json.dumps(payload)


def test_cli_list_only_prints_valid_json(capsys) -> None:
    exit_code = main(
        [
            "--models",
            "pc-4m",
            "--sequence-lengths",
            "128",
            "--microbatches",
            "16",
            "--list-only",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cases"] == [
        {
            "microbatch": 16,
            "model_name": "pc-4m",
            "sequence_length": 128,
        }
    ]


def test_cli_validation_fails_before_cuda() -> None:
    args = _parser().parse_args(
        [
            "--models",
            "pc-4m",
            "--sequence-lengths",
            "128",
            "--microbatches",
            "16",
            "--measured-steps",
            "0",
            "--list-only",
        ]
    )
    with pytest.raises(ValueError):
        run(args)
