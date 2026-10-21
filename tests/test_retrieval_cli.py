from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from clinical_doc_assist.retrieval.cli import main
from clinical_doc_assist.retrieval.models import (
    IndexManifest,
    IndexOutcome,
    RetrievalQuery,
    RetrievalRun,
    RetrievalServiceError,
)


class FakeService:
    def __init__(self) -> None:
        self.index_args: tuple[Path, str, bool] | None = None
        self.search_args: tuple[str, str, int] | None = None

    def index_corpus(
        self,
        corpus: Path,
        *,
        collection: str,
        replace: bool = False,
    ) -> IndexOutcome:
        self.index_args = (corpus, collection, replace)
        manifest = IndexManifest(
            index_id="index-test",
            created_at=datetime(2026, 10, 21, 10, 0),
            corpus_build_id="corpus-fixture",
            corpus_status="completed",
            chunk_count=2,
            point_count=2,
            status="completed",
            tei_model="test-model",
            embedding_dimension=3,
            qdrant_url="http://qdrant.test",
            collection=collection,
            replace_requested=replace,
            errors=(),
        )
        return IndexOutcome(manifest, Path("manifest.json"))

    def search_evidence(
        self,
        text: str,
        *,
        collection: str,
        limit: int,
    ) -> RetrievalRun:
        self.search_args = (text, collection, limit)
        return RetrievalRun(
            retrieval_id="retrieval-test",
            created_at=datetime(2026, 10, 21, 10, 0),
            query=RetrievalQuery.from_values(text, collection, limit),
            tei_model="test-model",
            collection=collection,
            status="no_results",
            results=(),
            errors=(),
        )

    def failing_index(
        self,
        corpus: Path,
        *,
        collection: str,
        replace: bool = False,
    ) -> IndexOutcome:
        outcome = FakeService.index_corpus(
            self,
            corpus,
            collection=collection,
            replace=replace,
        )
        manifest = outcome.manifest
        return IndexOutcome(
            IndexManifest(
                index_id=manifest.index_id,
                created_at=manifest.created_at,
                corpus_build_id=manifest.corpus_build_id,
                corpus_status=manifest.corpus_status,
                chunk_count=manifest.chunk_count,
                point_count=0,
                status="failed",
                tei_model=manifest.tei_model,
                embedding_dimension=manifest.embedding_dimension,
                qdrant_url=manifest.qdrant_url,
                collection=manifest.collection,
                replace_requested=manifest.replace_requested,
                errors=("failed",),
            ),
            outcome.manifest_path,
        )


def test_index_command_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService()
    code = main(
        ["index", "--corpus", "corpus", "--collection", "collection", "--replace"],
        service=service,  # type: ignore[arg-type]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["point_count"] == 2
    assert service.index_args == (Path("corpus"), "collection", True)


def test_search_command_emits_and_persists_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakeService()
    output = tmp_path / "retrieval.json"

    code = main(
        [
            "search",
            "question",
            "--collection",
            "collection",
            "--limit",
            "3",
            "--output",
            str(output),
        ],
        service=service,  # type: ignore[arg-type]
    )

    stdout = capsys.readouterr().out
    assert code == 0
    assert json.loads(stdout)["status"] == "no_results"
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(stdout)
    assert service.search_args == ("question", "collection", 3)


def test_cli_reports_service_errors(capsys: pytest.CaptureFixture[str]) -> None:
    class FailingService(FakeService):
        def search_evidence(
            self,
            text: str,
            *,
            collection: str,
            limit: int,
        ) -> RetrievalRun:
            raise RetrievalServiceError("Qdrant unavailable")

    code = main(
        ["search", "question", "--collection", "collection"],
        service=FailingService(),  # type: ignore[arg-type]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.strip() == "Retrieval error: Qdrant unavailable"


def test_cli_returns_one_for_failed_index(capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService()
    service.index_corpus = service.failing_index  # type: ignore[method-assign]

    code = main(
        ["index", "--corpus", "corpus", "--collection", "collection"],
        service=service,  # type: ignore[arg-type]
    )

    assert code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
