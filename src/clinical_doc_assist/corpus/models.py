"""Typed records for evidence corpus assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias

CorpusStatus: TypeAlias = Literal[
    "completed",
    "partial",
    "no_documents",
    "failed",
]
CorpusSchemaVersion: TypeAlias = Literal["1.0"]

CORPUS_SCHEMA_VERSION: CorpusSchemaVersion = "1.0"


class CorpusError(RuntimeError):
    """Base error for corpus assembly."""


class CorpusInputError(CorpusError):
    """Raised when discovery or source input is invalid."""


class CorpusOutputError(CorpusError):
    """Raised when a corpus output location cannot be used safely."""


@dataclass(frozen=True, slots=True)
class BuildSettings:
    """Deterministic chunking configuration."""

    max_chars: int = 1200
    overlap_chars: int = 150

    def __post_init__(self) -> None:
        if self.max_chars < 1:
            raise ValueError("max_chars must be at least 1.")
        if not 0 <= self.overlap_chars < self.max_chars:
            raise ValueError("overlap_chars must be non-negative and less than max_chars.")

    def to_dict(self) -> dict[str, int]:
        return {
            "max_chars": self.max_chars,
            "overlap_chars": self.overlap_chars,
        }


@dataclass(frozen=True, slots=True)
class DiscoveryInput:
    """One validated discovery artifact."""

    path: str
    run_id: str
    schema_version: str
    status: str
    accepted_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "status": self.status,
            "accepted_ids": list(self.accepted_ids),
        }


@dataclass(frozen=True, slots=True)
class AcceptedSource:
    """One deduplicated accepted identifier and its input runs."""

    nct_id: str
    run_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "run_ids": list(self.run_ids),
        }


@dataclass(frozen=True, slots=True)
class DiscoveryAggregate:
    """Validated discovery inputs and deduplicated source identifiers."""

    inputs: tuple[DiscoveryInput, ...]
    sources: tuple[AcceptedSource, ...]

    def duplicate_identifiers(self) -> tuple[AcceptedSource, ...]:
        return tuple(source for source in self.sources if len(source.run_ids) > 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": [item.to_dict() for item in self.inputs],
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """One named text section in an evidence document."""

    name: str
    heading: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "heading": self.heading,
            "content": self.content,
        }


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    """One normalized public research source."""

    document_id: str
    nct_id: str
    title: str
    source_url: str
    source_type: str
    source_updated_date: date | None
    retrieved_at: datetime
    contributing_run_ids: tuple[str, ...]
    sections: tuple[DocumentSection, ...]
    unavailable_sections: tuple[str, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "nct_id": self.nct_id,
            "title": self.title,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "source_updated_date": (
                self.source_updated_date.isoformat()
                if self.source_updated_date is not None
                else None
            ),
            "retrieved_at": self.retrieved_at.isoformat(),
            "contributing_run_ids": list(self.contributing_run_ids),
            "sections": [section.to_dict() for section in self.sections],
            "unavailable_sections": list(self.unavailable_sections),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    """One bounded, citation-ready document section."""

    chunk_id: str
    document_id: str
    nct_id: str
    section: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    content_hash: str
    source_url: str

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index cannot be negative.")
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("chunk character range must be positive.")
        if self.end_char - self.start_char != len(self.text):
            raise ValueError("chunk character range must match text length.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "nct_id": self.nct_id,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
            "content_hash": self.content_hash,
            "source_url": self.source_url,
        }


@dataclass(frozen=True, slots=True)
class SourceFailure:
    """One accepted source that could not become a document."""

    nct_id: str
    reason: str
    error_type: str = "source_error"
    http_status: int | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "reason": self.reason,
            "error_type": self.error_type,
            "http_status": self.http_status,
            "retryable": self.retryable,
        }


@dataclass(frozen=True, slots=True)
class BuildManifest:
    """Top-level result for one corpus build."""

    build_id: str
    status: CorpusStatus
    created_at: datetime
    discovery: DiscoveryAggregate
    settings: BuildSettings
    document_count: int
    chunk_count: int
    source_failures: tuple[SourceFailure, ...]
    errors: tuple[str, ...] = ()
    schema_version: CorpusSchemaVersion = CORPUS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "build_id": self.build_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "discovery_runs": [item.to_dict() for item in self.discovery.inputs],
            "identifiers": [source.to_dict() for source in self.discovery.sources],
            "duplicate_identifiers": [
                source.to_dict() for source in self.discovery.duplicate_identifiers()
            ],
            "settings": self.settings.to_dict(),
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "source_failures": [failure.to_dict() for failure in self.source_failures],
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class CorpusBuildResult:
    """A terminal build outcome and its output directory."""

    manifest: BuildManifest
    output: Path

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.manifest.status,
            "build_id": self.manifest.build_id,
            "output": str(self.output),
            "document_count": self.manifest.document_count,
            "chunk_count": self.manifest.chunk_count,
            "source_failures": len(self.manifest.source_failures),
        }
