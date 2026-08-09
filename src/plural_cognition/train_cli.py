"""Fail-closed resumable CUDA training for one resolved screening execution."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import asdict
from hashlib import sha256
from itertools import islice
from pathlib import Path
from typing import Iterator, Sequence

import torch

from .boolean_world.codec import CausalExample
from .checkpoint_bundle import (
    load_execution_checkpoint,
    save_execution_checkpoint,
)
from .dataset_shard import DatasetShardManifest, read_dataset_shard
from .execution import ExecutionManifest
from .manifest_io import (
    read_dataset_shard_manifest,
    read_execution_manifest,
    write_canonical_json,
)
from .model import PluralDecoder
from .training import (
    OptimizerStepResult,
    TrainingState,
    build_optimizer,
    optimizer_step,
)


class TrainingCommandError(RuntimeError):
    pass


def _file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise TrainingCommandError("cannot determine current Git commit") from exc
    commit = completed.stdout.strip()
    if len(commit) != 40:
        raise TrainingCommandError("current Git commit is not a full SHA")
    return commit


def _read_bindings(
    values: Sequence[Sequence[str]],
) -> tuple[tuple[Path, DatasetShardManifest], ...]:
    bindings: list[tuple[Path, DatasetShardManifest]] = []
    for pair in values:
        if len(pair) != 2:
            raise TrainingCommandError("each shard binding requires DATA and MANIFEST")
        data_path, manifest_path = map(Path, pair)
        if not data_path.is_file():
            raise TrainingCommandError(f"dataset shard does not exist: {data_path}")
        bindings.append((data_path, read_dataset_shard_manifest(manifest_path)))
    return tuple(bindings)


def _validate_binding_manifests(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
    expected: tuple[DatasetShardManifest, ...],
    label: str,
) -> None:
    actual = tuple(manifest for _, manifest in bindings)
    if actual != expected:
        raise TrainingCommandError(
            f"{label} shard bindings do not match the execution manifest"
        )


def _verify_shard_contents(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
) -> None:
    for path, manifest in bindings:
        count = sum(1 for _ in read_dataset_shard(path, manifest))
        if count != manifest.example_count:
            raise AssertionError("verified shard count differs from manifest")


def _iter_examples(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
) -> Iterator[CausalExample]:
    for path, manifest in bindings:
        yield from read_dataset_shard(path, manifest)


def _skip(iterator: Iterator[CausalExample], count: int) -> None:
    skipped = sum(1 for _ in islice(iterator, count))
    if skipped != count:
        raise TrainingCommandError("resume state exceeds the available training data")


def _validate_environment(
    execution: ExecutionManifest,
    preflight: Path,
) -> torch.device:
    if _git_commit() != execution.run.git_commit:
        raise TrainingCommandError(
            "current Git commit differs from the commit measured by the CUDA preflight"
        )
    if _file_sha256(preflight) != execution.run.preflight_sha256:
        raise TrainingCommandError("CUDA preflight file hash differs from the run manifest")
    if not torch.cuda.is_available():
        raise TrainingCommandError("CUDA is unavailable; CPU training is intentionally rejected")
    device = torch.device("cuda")
    device_name = torch.cuda.get_device_properties(0).name
    if device_name != execution.run.device_name:
        raise TrainingCommandError(
            f"CUDA device differs from the measured device: {device_name!r}"
        )
    if execution.run.precision == "bf16" and not torch.cuda.is_bf16_supported():
        raise TrainingCommandError("resolved BF16 run is unsupported by the current CUDA device")
    return device


def _progress_payload(
    execution: ExecutionManifest,
    result: OptimizerStepResult | None,
    state: TrainingState,
    *,
    completed: bool,
    last_checkpoint: str | None,
) -> dict:
    return {
        "schema": "plural-cognition-training-progress-v1",
        "execution_sha256": execution.sha256,
        "run_sha256": execution.run.sha256,
        "run_id": execution.run.intent.run_id,
        "state": asdict(state),
        "optimizer_steps_total": execution.optimizer_steps,
        "effective_training_tokens": execution.effective_training_tokens,
        "completed": completed,
        "last_checkpoint": last_checkpoint,
        "last_step": None
        if result is None
        else {
            "mean_loss": result.mean_loss,
            "learning_rate": result.learning_rate,
            "gradient_norm": result.gradient_norm,
        },
    }


def _progress_bar(current: int, total: int, *, width: int = 30) -> str:
    """Return a fixed-width terminal progress bar for one training run."""

    if total < 1:
        raise ValueError("progress total must be positive")
    if width < 1:
        raise ValueError("progress width must be positive")
    bounded = min(max(current, 0), total)
    fraction = bounded / total
    filled = int(fraction * width)
    bar = "#" * filled + "-" * (width - filled)
    digits = len(str(total))
    return (
        f"[{bar}] {fraction * 100:6.2f}% "
        f"({bounded:>{digits}}/{total} steps)"
    )


def run_training(
    execution: ExecutionManifest,
    *,
    training_bindings: tuple[tuple[Path, DatasetShardManifest], ...],
    validation_bindings: tuple[tuple[Path, DatasetShardManifest], ...],
    preflight: Path,
    output_dir: Path,
    resume: Path | None = None,
    max_steps: int | None = None,
) -> TrainingState:
    """Validate all inputs, then train and checkpoint one exact execution."""

    if max_steps is not None and max_steps < 1:
        raise ValueError("max_steps must be positive when supplied")
    _validate_binding_manifests(
        training_bindings, execution.training_shards, "training"
    )
    _validate_binding_manifests(
        validation_bindings, execution.validation_shards, "validation"
    )
    # Verify complete files before allocating model or CUDA optimizer state.
    _verify_shard_contents(training_bindings)
    _verify_shard_contents(validation_bindings)
    device = _validate_environment(execution, preflight)

    output_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(execution.run.intent.initialization_seed)
    torch.cuda.manual_seed_all(execution.run.intent.initialization_seed)
    torch.set_float32_matmul_precision("high")
    model = PluralDecoder(execution.run.intent.model_config).to(device)
    optimizer = build_optimizer(model, execution.run.intent.optimizer)
    scaler = (
        torch.amp.GradScaler("cuda", enabled=True)
        if execution.run.precision == "fp16"
        else None
    )
    state = TrainingState()
    if resume is not None:
        state = load_execution_checkpoint(
            resume,
            model=model,
            optimizer=optimizer,
            execution=execution,
            scaler=scaler,
            map_location=device,
        )
    if state.optimizer_steps > execution.optimizer_steps:
        raise TrainingCommandError("checkpoint is beyond the execution step budget")

    iterator = _iter_examples(training_bindings)
    _skip(iterator, state.next_example_index)
    pending_checkpoints = [
        token
        for token in execution.run.intent.checkpoint_tokens
        if token > state.processed_tokens
    ]
    steps_this_invocation = 0
    last_result: OptimizerStepResult | None = None
    last_checkpoint: str | None = str(resume) if resume is not None else None

    while state.optimizer_steps < execution.optimizer_steps:
        if max_steps is not None and steps_this_invocation >= max_steps:
            break
        examples = tuple(islice(iterator, execution.examples_per_optimizer_step))
        if len(examples) != execution.examples_per_optimizer_step:
            raise TrainingCommandError("training shards ended before the execution budget")
        microbatch = execution.run.microbatch_examples
        microbatches = tuple(
            examples[index : index + microbatch]
            for index in range(0, len(examples), microbatch)
        )
        if len(microbatches) != execution.run.gradient_accumulation_steps:
            raise AssertionError("resolved accumulation geometry is inconsistent")
        previous_tokens = state.processed_tokens
        last_result = optimizer_step(
            model,
            optimizer,
            microbatches,
            intent=execution.run.intent,
            state=state,
            device=device,
            precision=execution.run.precision,
            scaler=scaler,
        )
        state = last_result.state
        steps_this_invocation += 1

        crossed = [
            token
            for token in pending_checkpoints
            if previous_tokens < token <= state.processed_tokens
        ]
        for token in crossed:
            checkpoint_path = output_dir / f"checkpoint-target-{token:012d}.pt"
            save_execution_checkpoint(
                checkpoint_path,
                model=model,
                optimizer=optimizer,
                execution=execution,
                state=state,
                scaler=scaler,
            )
            last_checkpoint = str(checkpoint_path)
            pending_checkpoints.remove(token)

        write_canonical_json(
            output_dir / "progress.json",
            _progress_payload(
                execution,
                last_result,
                state,
                completed=False,
                last_checkpoint=last_checkpoint,
            ),
        )
        print(
            "\r" + _progress_bar(state.optimizer_steps, execution.optimizer_steps),
            end="",
            flush=True,
        )

    if steps_this_invocation:
        print(flush=True)
    completed = state.optimizer_steps == execution.optimizer_steps
    terminal_name = "checkpoint-final.pt" if completed else "checkpoint-current.pt"
    terminal_path = output_dir / terminal_name
    save_execution_checkpoint(
        terminal_path,
        model=model,
        optimizer=optimizer,
        execution=execution,
        state=state,
        scaler=scaler,
    )
    last_checkpoint = str(terminal_path)
    write_canonical_json(
        output_dir / "progress.json",
        _progress_payload(
            execution,
            last_result,
            state,
            completed=completed,
            last_checkpoint=last_checkpoint,
        ),
    )
    return state


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train or resume one exact CUDA screening execution."
    )
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument(
        "--training-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument(
        "--validation-shard",
        nargs=2,
        action="append",
        metavar=("DATA", "MANIFEST"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--max-steps",
        type=int,
        help="Bound this invocation for an explicit smoke/resume test.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifests and shard contents without allocating a model or CUDA state.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        execution = read_execution_manifest(args.execution)
        training = _read_bindings(args.training_shard)
        validation = _read_bindings(args.validation_shard)
        _validate_binding_manifests(training, execution.training_shards, "training")
        _validate_binding_manifests(validation, execution.validation_shards, "validation")
        if args.dry_run:
            _verify_shard_contents(training)
            _verify_shard_contents(validation)
            print(
                f"validated execution={execution.sha256} "
                f"training_examples={execution.training_example_count} "
                f"validation_examples={execution.validation_example_count}"
            )
            return 0
        state = run_training(
            execution,
            training_bindings=training,
            validation_bindings=validation,
            preflight=args.preflight,
            output_dir=args.output_dir,
            resume=args.resume,
            max_steps=args.max_steps,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"state steps={state.optimizer_steps} tokens={state.processed_tokens} "
        f"next_example_index={state.next_example_index}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
