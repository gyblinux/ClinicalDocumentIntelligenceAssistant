"""Single-source corpus builder with deterministic local artifacts."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from clinical_doc_assist.corpus.artifacts import (
    aggregate_discovery_artifacts,
    commit_output_directory,
    prepare_output_directory,
    write_corpus_artifacts,
)
from clinical_doc_assist.corpus.chunking import chunk_document
from clinical_doc_assist.corpus.models import (
    BuildManifest,
    BuildSettings,
    CorpusBuildResult,
    CorpusOutputError,
    CorpusStatus,
    EvidenceChunk,
    EvidenceDocument,
    SourceFailure,
)
from clinical_doc_assist.corpus.normalize import normalize_study
from clinical_doc_assist.research.models import SourceError


class StudySource(Protocol):
    """Detailed study source required by the corpus builder."""

    def fetch_study(self, nct_id: str) -> dict[str, Any]:
        """Return one detailed study record."""


class CorpusBuilder:
    """Build a deterministic local corpus from discovery artifacts."""

    def __init__(
        self,
        *,
        source: StudySource,
        now: Callable[[], datetime] | None = None,
        build_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._source = source
        self._now = now or (lambda: datetime.now(UTC))
        self._build_id_factory = build_id_factory or (lambda: f"corpus-{uuid4().hex[:16]}")

    def build(
        self,
        discovery_paths: Sequence[Path],
        output: Path,
        settings: BuildSettings,
    ) -> CorpusBuildResult:
        """Build and atomically publish one corpus directory."""

        prepare_output_directory(output)
        discovery = aggregate_discovery_artifacts(discovery_paths)
        created_at = self._now()
        build_id = self._build_id_factory()

        documents: list[EvidenceDocument] = []
        chunks: list[EvidenceChunk] = []
        failures: list[SourceFailure] = []
        for accepted_source in discovery.sources:
            try:
                study = self._source.fetch_study(accepted_source.nct_id)
                document = normalize_study(
                    study,
                    accepted_source,
                    retrieved_at=created_at,
                )
            except SourceError as exc:
                failures.append(
                    SourceFailure(
                        nct_id=accepted_source.nct_id,
                        reason=str(exc),
                        error_type=exc.error_type,
                        http_status=exc.http_status,
                        retryable=exc.retryable,
                    )
                )
                continue

            documents.append(document)
            chunks.extend(chunk_document(document, settings))

        status = _resolve_status(
            accepted_count=len(discovery.sources),
            document_count=len(documents),
            failure_count=len(failures),
        )
        errors = ("No usable evidence documents were produced.",) if status == "failed" else ()
        manifest = BuildManifest(
            build_id=build_id,
            status=status,
            created_at=created_at,
            discovery=discovery,
            settings=settings,
            document_count=len(documents),
            chunk_count=len(chunks),
            source_failures=tuple(failures),
            errors=errors,
        )

        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(
                tempfile.mkdtemp(
                    prefix=f".{output.name}.",
                    dir=output.parent,
                )
            )
        except OSError as exc:
            raise CorpusOutputError(
                f"Cannot create temporary corpus output near {output}: {exc}"
            ) from exc
        try:
            write_corpus_artifacts(temporary, manifest, documents, chunks)
            commit_output_directory(temporary, output)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        return CorpusBuildResult(manifest=manifest, output=output)


def _resolve_status(
    *,
    accepted_count: int,
    document_count: int,
    failure_count: int,
) -> CorpusStatus:
    if accepted_count == 0:
        return "no_documents"
    if document_count == 0:
        return "failed"
    if failure_count:
        return "partial"
    return "completed"
