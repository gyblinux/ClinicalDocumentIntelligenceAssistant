"""Command-line entry point for evidence-grounded answering."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from clinical_doc_assist.answering.agent import AnswerAgent, DeepSeekModelClient
from clinical_doc_assist.answering.models import (
    AnswerConfig,
    AnsweringError,
    AnsweringInputError,
    AnsweringOutputError,
)
from clinical_doc_assist.answering.service import AnsweringCommands, AnswerService
from clinical_doc_assist.answering.tools import TrialMetadataTool
from clinical_doc_assist.config import DEFAULT_MODEL, Settings, SettingsError
from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-answer",
        description="Answer from one saved public clinical evidence retrieval run.",
    )
    parser.add_argument("--retrieval-run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: AnsweringCommands | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    model_client: DeepSeekModelClient | None = None
    source: ClinicalTrialsSource | None = None

    try:
        if service is None:
            load_dotenv()
            configured_model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
            if not configured_model:
                configured_model = DEFAULT_MODEL

            def agent_factory(allowed_nct_ids: frozenset[str]) -> AnswerAgent:
                nonlocal model_client, source
                if model_client is None:
                    settings = Settings.from_env(load_env_file=False)
                    model_client = DeepSeekModelClient(
                        client=OpenAI(
                            api_key=settings.api_key,
                            base_url=settings.base_url,
                        ),
                        model=settings.model,
                    )
                if source is None:
                    source = ClinicalTrialsSource()
                return AnswerAgent(
                    model=model_client,
                    metadata_tool=TrialMetadataTool(
                        source=source,
                        allowed_nct_ids=allowed_nct_ids,
                    ),
                )

            service = AnswerService(
                config=AnswerConfig(provider="deepseek", model=configured_model),
                agent_factory=agent_factory,
            )

        outcome = service.answer(
            args.retrieval_run,
            output=args.output,
        )
        print(json.dumps(outcome.run.to_dict(), indent=2, ensure_ascii=True))
        return outcome.exit_code
    except (SettingsError, AnsweringInputError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except AnsweringOutputError as exc:
        print(f"Answer error: {exc}", file=sys.stderr)
        return 1
    except AnsweringError as exc:
        print(f"Answer error: {exc}", file=sys.stderr)
        return 1
    finally:
        if model_client is not None:
            model_client.close()
        if source is not None:
            source.close()


if __name__ == "__main__":
    raise SystemExit(main())
