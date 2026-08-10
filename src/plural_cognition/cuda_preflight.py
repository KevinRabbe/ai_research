"""Target-machine CUDA throughput and memory preflight for V1.1.

This module measures real forward/backward/optimizer steps. It never substitutes a
CPU estimate for a CUDA result and writes a machine-readable, atomic JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import torch
from torch import Tensor

from .model import (
    MODEL_CONFIGS,
    DecoderConfig,
    PluralDecoder,
    causal_lm_loss,
)

MODEL_BY_NAME = {config.name.lower(): config for config in MODEL_CONFIGS}
DEFAULT_MODELS = tuple(config.name.lower() for config in MODEL_CONFIGS)
DEFAULT_SEQUENCE_LENGTHS = (128, 256)
DEFAULT_MICROBATCHES = (16, 32, 64, 128, 256)
REPORT_SCHEMA_VERSION = 1
GIB = 1024**3


@dataclass(frozen=True, slots=True)
class SweepCase:
    model_name: str
    sequence_length: int
    microbatch: int

    def __post_init__(self) -> None:
        if self.model_name not in MODEL_BY_NAME:
            raise ValueError(f"unknown model: {self.model_name}")
        if self.sequence_length < 2:
            raise ValueError("sequence_length must be at least 2")
        if self.sequence_length > MODEL_BY_NAME[self.model_name].max_seq_len:
            raise ValueError("sequence_length exceeds model context")
        if self.microbatch < 1:
            raise ValueError("microbatch must be positive")


@dataclass(frozen=True, slots=True)
class CaseResult:
    model_name: str
    parameters: int
    sequence_length: int
    microbatch: int
    precision: str
    status: str
    warmup_steps: int
    measured_steps: int
    elapsed_seconds: float | None
    milliseconds_per_step: float | None
    examples_per_second: float | None
    tokens_per_second: float | None
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None
    vram_limit_bytes: int
    within_vram_limit: bool | None
    loss: float | None
    error: str | None


def build_sweep_cases(
    model_names: Sequence[str],
    sequence_lengths: Sequence[int],
    microbatches: Sequence[int],
) -> tuple[SweepCase, ...]:
    """Build the exact ordered Cartesian sweep after strict validation."""

    normalized_models = tuple(name.lower() for name in model_names)
    if not normalized_models:
        raise ValueError("at least one model is required")
    if len(set(normalized_models)) != len(normalized_models):
        raise ValueError("model list must not contain duplicates")
    if not sequence_lengths or not microbatches:
        raise ValueError("sequence lengths and microbatches must not be empty")
    if len(set(sequence_lengths)) != len(sequence_lengths):
        raise ValueError("sequence lengths must not contain duplicates")
    if len(set(microbatches)) != len(microbatches):
        raise ValueError("microbatches must not contain duplicates")

    return tuple(
        SweepCase(model_name, sequence_length, microbatch)
        for model_name in normalized_models
        for sequence_length in sequence_lengths
        for microbatch in microbatches
    )


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    value = completed.stdout.strip()
    return value or "unknown"


def _resolve_precision(requested: str) -> tuple[str, torch.dtype, bool]:
    if requested == "auto":
        if torch.cuda.is_bf16_supported():
            return "bf16", torch.bfloat16, False
        return "fp16", torch.float16, True
    if requested == "bf16":
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("requested bf16, but this CUDA device does not support it")
        return "bf16", torch.bfloat16, False
    if requested == "fp16":
        return "fp16", torch.float16, True
    raise ValueError(f"unsupported precision: {requested}")


def _training_batch(
    config: DecoderConfig,
    microbatch: int,
    sequence_length: int,
    *,
    device: torch.device,
    seed: int,
) -> tuple[Tensor, Tensor]:
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    input_ids = torch.randint(
        0,
        config.vocab_size,
        (microbatch, sequence_length),
        dtype=torch.long,
        device=device,
        generator=generator,
    )
    label_mask = torch.zeros_like(input_ids, dtype=torch.bool)
    label_mask[:, sequence_length // 2 :] = True
    return input_ids, label_mask


def _optimizer_step(
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler,
    input_ids: Tensor,
    label_mask: Tensor,
    amp_dtype: torch.dtype,
) -> Tensor:
    optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=amp_dtype):
        logits = model(input_ids)
        loss = causal_lm_loss(logits, input_ids, label_mask)
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
    return loss.detach()


def _is_cuda_oom(exc: BaseException) -> bool:
    return isinstance(exc, torch.OutOfMemoryError) or (
        isinstance(exc, RuntimeError)
        and "out of memory" in str(exc).lower()
    )


def benchmark_case(
    case: SweepCase,
    *,
    precision_name: str,
    amp_dtype: torch.dtype,
    use_grad_scaler: bool,
    warmup_steps: int,
    measured_steps: int,
    vram_limit_bytes: int,
    seed: int,
) -> CaseResult:
    """Measure one isolated CUDA training configuration."""

    config = MODEL_BY_NAME[case.model_name]
    device = torch.device("cuda")
    model: PluralDecoder | None = None
    optimizer: torch.optim.Optimizer | None = None

    try:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.cuda.empty_cache()

        model = PluralDecoder(config).to(device=device)
        model.train()
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=1e-4,
            betas=(0.9, 0.95),
            weight_decay=0.1,
        )
        scaler = torch.amp.GradScaler(
            "cuda",
            enabled=use_grad_scaler,
        )
        input_ids, label_mask = _training_batch(
            config,
            case.microbatch,
            case.sequence_length,
            device=device,
            seed=seed ^ 0x5EED,
        )

        last_loss = torch.tensor(float("nan"), device=device)
        for _ in range(warmup_steps):
            last_loss = _optimizer_step(
                model,
                optimizer,
                scaler,
                input_ids,
                label_mask,
                amp_dtype,
            )

        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        for _ in range(measured_steps):
            last_loss = _optimizer_step(
                model,
                optimizer,
                scaler,
                input_ids,
                label_mask,
                amp_dtype,
            )
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started

        peak_allocated = torch.cuda.max_memory_allocated()
        peak_reserved = torch.cuda.max_memory_reserved()
        total_examples = case.microbatch * measured_steps
        total_tokens = total_examples * case.sequence_length
        within_limit = peak_allocated <= vram_limit_bytes

        return CaseResult(
            model_name=config.name,
            parameters=model.parameter_count(),
            sequence_length=case.sequence_length,
            microbatch=case.microbatch,
            precision=precision_name,
            status="ok" if within_limit else "vram_limit_exceeded",
            warmup_steps=warmup_steps,
            measured_steps=measured_steps,
            elapsed_seconds=elapsed,
            milliseconds_per_step=(elapsed / measured_steps) * 1000.0,
            examples_per_second=total_examples / elapsed,
            tokens_per_second=total_tokens / elapsed,
            peak_allocated_bytes=peak_allocated,
            peak_reserved_bytes=peak_reserved,
            vram_limit_bytes=vram_limit_bytes,
            within_vram_limit=within_limit,
            loss=float(last_loss.cpu()),
            error=None,
        )
    except BaseException as exc:
        if not _is_cuda_oom(exc):
            raise
        return CaseResult(
            model_name=config.name,
            parameters=config and (
                sum(parameter.numel() for parameter in model.parameters())
                if model is not None
                else 0
            ),
            sequence_length=case.sequence_length,
            microbatch=case.microbatch,
            precision=precision_name,
            status="oom",
            warmup_steps=warmup_steps,
            measured_steps=0,
            elapsed_seconds=None,
            milliseconds_per_step=None,
            examples_per_second=None,
            tokens_per_second=None,
            peak_allocated_bytes=None,
            peak_reserved_bytes=None,
            vram_limit_bytes=vram_limit_bytes,
            within_vram_limit=False,
            loss=None,
            error=str(exc),
        )
    finally:
        del optimizer
        del model
        torch.cuda.empty_cache()


def _hardware_metadata() -> dict[str, object]:
    properties = torch.cuda.get_device_properties(0)
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "gpu_name": properties.name,
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "total_vram_bytes": properties.total_memory,
        "bf16_supported": torch.cuda.is_bf16_supported(),
        "cuda_device_count": torch.cuda.device_count(),
    }


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure V1.1 decoder CUDA training throughput and peak memory. "
            "Results are measurements only; this command does not train a "
            "scientific checkpoint."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        choices=tuple(MODEL_BY_NAME),
    )
    parser.add_argument(
        "--sequence-lengths",
        nargs="+",
        type=int,
        default=DEFAULT_SEQUENCE_LENGTHS,
    )
    parser.add_argument(
        "--microbatches",
        nargs="+",
        type=int,
        default=DEFAULT_MICROBATCHES,
    )
    parser.add_argument(
        "--precision",
        choices=("auto", "bf16", "fp16"),
        default="auto",
    )
    parser.add_argument("--warmup-steps", type=int, default=5)
    parser.add_argument("--measured-steps", type=int, default=20)
    parser.add_argument("--vram-limit-gb", type=float, default=13.5)
    parser.add_argument("--seed", type=int, default=20260806)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/cuda-preflight.json"),
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="validate and print the sweep without requiring CUDA",
    )
    return parser


def _validate_cli(args: argparse.Namespace) -> None:
    if args.warmup_steps < 0:
        raise ValueError("warmup_steps must not be negative")
    if args.measured_steps < 1:
        raise ValueError("measured_steps must be positive")
    if args.vram_limit_gb <= 0:
        raise ValueError("vram_limit_gb must be positive")


def run(args: argparse.Namespace) -> dict[str, object]:
    _validate_cli(args)
    cases = build_sweep_cases(
        args.models,
        args.sequence_lengths,
        args.microbatches,
    )
    if args.list_only:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "mode": "list_only",
            "cases": [asdict(case) for case in cases],
        }

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. Run this command in the NVIDIA-enabled "
            "training environment; CPU estimates are intentionally rejected."
        )

    precision_name, amp_dtype, use_grad_scaler = _resolve_precision(
        args.precision
    )
    vram_limit_bytes = int(args.vram_limit_gb * GIB)
    results: list[CaseResult] = []
    blocked: set[tuple[str, int]] = set()

    for index, case in enumerate(cases):
        boundary = (case.model_name, case.sequence_length)
        if boundary in blocked:
            continue
        print(
            f"[{index + 1}/{len(cases)}] {case.model_name} "
            f"seq={case.sequence_length} batch={case.microbatch}",
            flush=True,
        )
        result = benchmark_case(
            case,
            precision_name=precision_name,
            amp_dtype=amp_dtype,
            use_grad_scaler=use_grad_scaler,
            warmup_steps=args.warmup_steps,
            measured_steps=args.measured_steps,
            vram_limit_bytes=vram_limit_bytes,
            seed=args.seed + index,
        )
        results.append(result)
        if result.status in ("oom", "vram_limit_exceeded"):
            blocked.add(boundary)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "cuda_training_preflight",
        "git_commit": _git_commit(),
        "precision": precision_name,
        "vram_limit_bytes": vram_limit_bytes,
        "hardware": _hardware_metadata(),
        "arguments": {
            "models": list(args.models),
            "sequence_lengths": list(args.sequence_lengths),
            "microbatches": list(args.microbatches),
            "warmup_steps": args.warmup_steps,
            "measured_steps": args.measured_steps,
            "seed": args.seed,
        },
        "results": [asdict(result) for result in results],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        payload = run(args)
        if args.list_only:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            _atomic_write_json(args.output, payload)
            print(f"wrote {args.output}")
        return 0
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
