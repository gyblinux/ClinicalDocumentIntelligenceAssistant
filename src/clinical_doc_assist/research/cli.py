"""Command-line entry point for research document discovery."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date

from openai import OpenAI

from clinical_doc_assist.config import Settings, SettingsError
from clinical_doc_assist.research.agent import ResearchAgent
from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource
from clinical_doc_assist.research.models import (
    DiscoveryError,
    DiscoveryRequest,
    DiscoveryRun,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-discover",
        description="Discover and screen public clinical research records.",
    )
    parser.add_argument("topic", help="Clinical research topic to search.")
    parser.add_argument(
        "--updated-after",
        required=True,
        type=_date_argument,
        help="Inclusive lower update date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--updated-before",
        required=True,
        type=_date_argument,
        help="Inclusive upper update date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum candidates, from 1 to 20.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    run_discovery: Callable[[DiscoveryRequest], DiscoveryRun] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        request = DiscoveryRequest(
            topic=args.topic,
            updated_after=args.updated_after,
            updated_before=args.updated_before,
            limit=args.limit,
        )
    except ValueError as exc:
        print(f"Argument error: {exc}", file=sys.stderr)
        return 2

    source: ClinicalTrialsSource | None = None
    try:
        if run_discovery is None:
            settings = Settings.from_env()
            source = ClinicalTrialsSource()
            agent = ResearchAgent(
                client=OpenAI(
                    api_key=settings.api_key,
                    base_url=settings.base_url,
                ),
                model=settings.model,
                source=source,
                max_steps=settings.max_steps,
            )
            run_discovery = agent.run

        run = run_discovery(request)
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except DiscoveryError as exc:
        print(f"Discovery error: {exc}", file=sys.stderr)
        return 1
    finally:
        if source is not None:
            source.close()

    print(json.dumps(run.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _date_argument(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date '{value}'; expected YYYY-MM-DD") from exc


if __name__ == "__main__":
    raise SystemExit(main())
