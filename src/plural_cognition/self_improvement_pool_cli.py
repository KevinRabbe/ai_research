"""Assemble immutable SI candidate pools from target-free generation artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .self_improvement import build_pool_from_generation_artifacts
from .self_improvement.io import (
    read_generation_artifact,
    write_candidate_pool,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one content-addressed target-free candidate pool."
    )
    parser.add_argument(
        "--generation",
        type=Path,
        action="append",
        required=True,
        help="Canonical target-free generation artifact; repeat per path.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        artifacts = tuple(read_generation_artifact(path) for path in args.generation)
        pool = build_pool_from_generation_artifacts(artifacts)
        write_candidate_pool(args.output, pool)
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        f"wrote {args.output} cases={len(pool.tasks)} paths={len(pool.sources)} "
        f"pool_sha256={pool.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
