"""Command-line entry point for evidence indexing and retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from clinical_doc_assist.retrieval.models import (
    IndexOutcome,
    RetrievalConfig,
    RetrievalError,
    RetrievalInputError,
    RetrievalOutputError,
    RetrievalRun,
    RetrievalServiceError,
)
from clinical_doc_assist.retrieval.qdrant import QdrantVectorStore
from clinical_doc_assist.retrieval.service import RetrievalService, write_json_atomic
from clinical_doc_assist.retrieval.tei import TEIClient


class RetrievalCommands(Protocol):
    def index_corpus(
        self,
        corpus: Path,
        *,
        collection: str,
        replace: bool = False,
    ) -> IndexOutcome: ...

    def search_evidence(
        self,
        text: str,
        *,
        collection: str,
        limit: int = 5,
    ) -> RetrievalRun: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-doc-retrieve",
        description="Index and retrieve public clinical evidence chunks.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    index = commands.add_parser("index", help="Embed and index a corpus.")
    index.add_argument("--corpus", type=Path, required=True)
    index.add_argument("--collection", default="clinical_evidence_v1")
    index.add_argument("--replace", action="store_true")

    search = commands.add_parser("search", help="Retrieve ranked evidence chunks.")
    search.add_argument("query")
    search.add_argument("--collection", default="clinical_evidence_v1")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--output", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: RetrievalCommands | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    tei: TEIClient | None = None
    vector_store: QdrantVectorStore | None = None

    try:
        if service is None:
            config = RetrievalConfig.from_env()
            tei = TEIClient(
                base_url=config.tei_url,
                model=config.tei_model,
                embedding_dimension=config.embedding_dimension,
            )
            vector_store = QdrantVectorStore(
                collection=args.collection,
                url=config.qdrant_url,
                api_key=config.qdrant_api_key,
            )
            service = RetrievalService(
                config=config,
                tei=tei,
                vector_store=vector_store,
            )

        if args.command == "index":
            return _run_index(
                service,
                corpus=args.corpus,
                collection=args.collection,
                replace=args.replace,
            )
        return _run_search(
            service,
            query=args.query,
            collection=args.collection,
            limit=args.limit,
            output=args.output,
        )
    except (RetrievalInputError, RetrievalOutputError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except RetrievalServiceError as exc:
        print(f"Retrieval error: {exc}", file=sys.stderr)
        return 1
    except RetrievalError as exc:
        print(f"Retrieval error: {exc}", file=sys.stderr)
        return 1
    finally:
        if tei is not None:
            tei.close()
        if vector_store is not None:
            vector_store.close()


def _run_index(
    service: RetrievalCommands,
    *,
    corpus: Path,
    collection: str,
    replace: bool,
) -> int:
    outcome = service.index_corpus(
        corpus,
        collection=collection,
        replace=replace,
    )
    summary = outcome.manifest.summary()
    summary["manifest_path"] = str(outcome.manifest_path)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if outcome.manifest.status == "completed" else 1


def _run_search(
    service: RetrievalCommands,
    *,
    query: str,
    collection: str,
    limit: int,
    output: Path | None,
) -> int:
    run = service.search_evidence(query, collection=collection, limit=limit)
    payload = run.to_dict()
    if output is not None:
        write_json_atomic(output, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
