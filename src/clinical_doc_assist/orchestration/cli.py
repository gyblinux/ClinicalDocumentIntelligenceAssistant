"""Command-line entry point for one question-to-answer pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from openai import OpenAI

from clinical_doc_assist.answering.agent import AnswerAgent, DeepSeekModelClient
from clinical_doc_assist.answering.models import (
    AnswerConfig,
    AnsweringError,
    AnsweringInputError,
)
from clinical_doc_assist.answering.service import AnswerService
from clinical_doc_assist.answering.tools import TrialMetadataTool
from clinical_doc_assist.config import DEFAULT_MODEL, Settings, SettingsError
from clinical_doc_assist.orchestration.models import (
    DEFAULT_RETRIEVAL_LIMIT,
    OrchestrationError,
    OrchestrationInputError,
    PipelineOutcome,
    QuestionRequest,
)
from clinical_doc_assist.orchestration.service import OrchestrationService
from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource
from clinical_doc_assist.retrieval.models import RetrievalConfig
from clinical_doc_assist.retrieval.qdrant import QdrantVectorStore
from clinical_doc_assist.retrieval.service import RetrievalService
from clinical_doc_assist.retrieval.tei import TEIClient


class OrchestrationCommands(Protocol):
    def ask(
        self,
        request: QuestionRequest,
        *,
        output: Path | None = None,
    ) -> PipelineOutcome: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-ask",
        description="Retrieve evidence and answer one public clinical research question.",
    )
    parser.add_argument("question")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--limit", type=int, default=DEFAULT_RETRIEVAL_LIMIT)
    parser.add_argument("--pipeline-dir", type=Path, default=Path("artifacts/pipelines"))
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: OrchestrationCommands | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    tei: TEIClient | None = None
    vector_store: QdrantVectorStore | None = None
    model_client: DeepSeekModelClient | None = None
    source: ClinicalTrialsSource | None = None

    try:
        try:
            request = QuestionRequest(
                question=args.question,
                collection=args.collection,
                limit=args.limit,
            )
        except ValueError as exc:
            raise OrchestrationInputError(str(exc)) from exc

        if service is None:
            load_dotenv()
            try:
                retrieval_config = RetrievalConfig.from_env(load_env_file=False)
            except ValueError as exc:
                raise OrchestrationInputError(str(exc)) from exc
            tei = TEIClient(
                base_url=retrieval_config.tei_url,
                model=retrieval_config.tei_model,
                embedding_dimension=retrieval_config.embedding_dimension,
            )
            vector_store = QdrantVectorStore(
                collection=request.collection,
                url=retrieval_config.qdrant_url,
                api_key=retrieval_config.qdrant_api_key,
            )
            retrieval = RetrievalService(
                config=retrieval_config,
                tei=tei,
                vector_store=vector_store,
            )

            configured_model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
            if not configured_model:
                configured_model = DEFAULT_MODEL

            def agent_factory(allowed_nct_ids: frozenset[str]) -> AnswerAgent:
                nonlocal model_client, source
                try:
                    settings = Settings.from_env(load_env_file=False)
                except SettingsError as exc:
                    raise AnsweringInputError(str(exc)) from exc
                if model_client is None:
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

            answering = AnswerService(
                config=AnswerConfig(provider="deepseek", model=configured_model),
                agent_factory=agent_factory,
            )
            service = OrchestrationService(
                retrieval=retrieval,
                answering=answering,
                embedding_dimension=retrieval_config.embedding_dimension,
                pipeline_dir=args.pipeline_dir,
            )

        outcome = service.ask(request)
        print(json.dumps(outcome.run.to_dict(), indent=2, ensure_ascii=True))
        return outcome.exit_code
    except OrchestrationInputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except (OrchestrationError, AnsweringError, SettingsError) as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1
    finally:
        if model_client is not None:
            model_client.close()
        if source is not None:
            source.close()
        if tei is not None:
            tei.close()
        if vector_store is not None:
            vector_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
