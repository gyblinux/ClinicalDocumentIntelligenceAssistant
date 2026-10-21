"""Command-line entry point for evidence corpus assembly."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from clinical_doc_assist.corpus.builder import CorpusBuilder
from clinical_doc_assist.corpus.models import (
    BuildSettings,
    CorpusBuildResult,
    CorpusError,
)
from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource

BuildRunner = Callable[
    [Sequence[Path], Path, BuildSettings],
    CorpusBuildResult,
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-corpus",
        description="Build a local evidence corpus from discovery artifacts.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build a corpus directory.")
    build.add_argument(
        "--discovery-run",
        action="append",
        type=Path,
        required=True,
        help="Discovery JSON artifact; repeat for multiple runs.",
    )
    build.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory for the corpus artifacts.",
    )
    build.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Maximum characters per chunk.",
    )
    build.add_argument(
        "--overlap-chars",
        type=int,
        default=150,
        help="Maximum overlap when a section must be split.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    run_build: BuildRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = BuildSettings(
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
        )
    except ValueError as exc:
        print(f"Argument error: {exc}", file=sys.stderr)
        return 2

    source: ClinicalTrialsSource | None = None
    try:
        if run_build is None:
            source = ClinicalTrialsSource()
            builder = CorpusBuilder(source=source)
            run_build = builder.build
        result = run_build(args.discovery_run, args.output, settings)
    except CorpusError as exc:
        print(f"Corpus error: {exc}", file=sys.stderr)
        return 2
    finally:
        if source is not None:
            source.close()

    print(json.dumps(result.summary(), indent=2, ensure_ascii=True))
    return {
        "completed": 0,
        "partial": 0,
        "no_documents": 3,
        "failed": 1,
    }[result.manifest.status]


if __name__ == "__main__":
    raise SystemExit(main())
