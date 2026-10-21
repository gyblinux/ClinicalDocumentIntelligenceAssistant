"""CLI entry points for evaluation and answer presentation."""

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
from clinical_doc_assist.evaluation.comparison import compare_evaluations
from clinical_doc_assist.evaluation.models import (
    DEFAULT_COLLECTION,
    DEFAULT_RETRIEVAL_LIMIT,
    EvaluationError,
    EvaluationInputError,
    EvaluationOutcome,
    EvaluationOutputError,
    PresentationOutcome,
    PresentationRequest,
    PresentationTooLongError,
)
from clinical_doc_assist.evaluation.presentation import (
    PresentationService,
    persist_presentation_review,
)
from clinical_doc_assist.evaluation.runner import EvaluationService
from clinical_doc_assist.orchestration.service import OrchestrationService
from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource
from clinical_doc_assist.retrieval.models import RetrievalConfig
from clinical_doc_assist.retrieval.qdrant import QdrantVectorStore
from clinical_doc_assist.retrieval.service import RetrievalService
from clinical_doc_assist.retrieval.tei import TEIClient


class EvaluationCommands(Protocol):
    def run(
        self,
        cases_path: Path,
        *,
        pipeline_map: Path | None = None,
        collection: str = DEFAULT_COLLECTION,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> EvaluationOutcome: ...


class PresentationCommands(Protocol):
    def present(self, request: PresentationRequest) -> PresentationOutcome: ...


class _Runtime:
    def __init__(self, pipeline_dir: Path, collection: str) -> None:
        load_dotenv()
        try:
            self.retrieval_config = RetrievalConfig.from_env(load_env_file=False)
        except ValueError as exc:
            raise EvaluationInputError(str(exc)) from exc
        self.tei = TEIClient(
            base_url=self.retrieval_config.tei_url,
            model=self.retrieval_config.tei_model,
            embedding_dimension=self.retrieval_config.embedding_dimension,
        )
        self.vector_store = QdrantVectorStore(
            collection=collection,
            url=self.retrieval_config.qdrant_url,
            api_key=self.retrieval_config.qdrant_api_key,
        )
        self.model_client: DeepSeekModelClient | None = None
        self.source: ClinicalTrialsSource | None = None
        self.service = OrchestrationService(
            retrieval=RetrievalService(
                config=self.retrieval_config,
                tei=self.tei,
                vector_store=self.vector_store,
            ),
            answering=AnswerService(
                config=self._answer_config(),
                agent_factory=self._agent_factory,
            ),
            embedding_dimension=self.retrieval_config.embedding_dimension,
            pipeline_dir=pipeline_dir,
        )

    def _answer_config(self) -> AnswerConfig:
        model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        return AnswerConfig(provider="deepseek", model=model)

    def _agent_factory(self, allowed_nct_ids: frozenset[str]) -> AnswerAgent:
        try:
            settings = Settings.from_env(load_env_file=False)
        except SettingsError as exc:
            raise AnsweringInputError(str(exc)) from exc
        if self.model_client is None:
            self.model_client = DeepSeekModelClient(
                client=OpenAI(
                    api_key=settings.api_key,
                    base_url=settings.base_url,
                ),
                model=settings.model,
            )
        if self.source is None:
            self.source = ClinicalTrialsSource()
        return AnswerAgent(
            model=self.model_client,
            metadata_tool=TrialMetadataTool(
                source=self.source,
                allowed_nct_ids=allowed_nct_ids,
            ),
        )

    def close(self) -> None:
        if self.model_client is not None:
            self.model_client.close()
        if self.source is not None:
            self.source.close()
        self.tei.close()
        self.vector_store.close()


def build_eval_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinical-doc-eval")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Evaluate fixed cases.")
    run.add_argument("--cases", type=Path, required=True)
    run.add_argument("--pipeline-map", type=Path)
    run.add_argument("--collection", default=DEFAULT_COLLECTION)
    run.add_argument("--limit", type=int, default=DEFAULT_RETRIEVAL_LIMIT)
    run.add_argument("--output-dir", type=Path, default=Path("artifacts/evaluations"))

    compare = commands.add_parser("compare", help="Compare two evaluation runs.")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--output", type=Path)

    review = commands.add_parser("review", help="Persist a human presentation review.")
    review.add_argument("--input", type=Path, required=True)
    review.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/evaluations/presentation-reviews"),
    )
    return parser


def build_present_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinical-doc-present")
    parser.add_argument("--pipeline", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main_eval(
    argv: Sequence[str] | None = None,
    *,
    service: EvaluationCommands | None = None,
) -> int:
    args = build_eval_parser().parse_args(argv)
    runtime: _Runtime | None = None
    try:
        if args.command == "run":
            if service is None:
                if args.pipeline_map is None:
                    runtime = _Runtime(
                        Path("artifacts/pipelines"),
                        args.collection,
                    )
                    orchestrator = runtime.service
                else:
                    orchestrator = None
                service = EvaluationService(
                    orchestrator=orchestrator,
                    output_dir=args.output_dir,
                )
            outcome = service.run(
                args.cases,
                pipeline_map=args.pipeline_map,
                collection=args.collection,
                limit=args.limit,
            )
            print(json.dumps(outcome.run.to_dict(), indent=2, ensure_ascii=True))
            return 0
        if args.command == "compare":
            outcome = compare_evaluations(
                args.baseline,
                args.candidate,
                output=args.output,
            )
            print(json.dumps(outcome.run.to_dict(), indent=2, ensure_ascii=True))
            return 0
        review, _ = persist_presentation_review(
            args.input,
            output_dir=args.output_dir,
        )
        print(json.dumps(review.to_dict(), indent=2, ensure_ascii=True))
        return 0
    except (EvaluationInputError, SettingsError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except (EvaluationOutputError, AnsweringError, EvaluationError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 1
    finally:
        if runtime is not None:
            runtime.close()


def main_present(
    argv: Sequence[str] | None = None,
    *,
    service: PresentationCommands | None = None,
) -> int:
    args = build_present_parser().parse_args(argv)
    if service is None:
        service = PresentationService()
    try:
        outcome = service.present(
            PresentationRequest(
                pipeline_path=args.pipeline,
                case_id=args.case_id,
                evaluation_path=args.evaluation,
                output_path=args.output,
            )
        )
        print(outcome.text, end="")
        return 0
    except (EvaluationInputError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except (PresentationTooLongError, EvaluationError) as exc:
        print(f"Presentation error: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch module execution to evaluation or presentation."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["present"]:
        return main_present(arguments[1:])
    return main_eval(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
