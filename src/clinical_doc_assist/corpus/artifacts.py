"""Discovery input and local corpus artifact handling."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from clinical_doc_assist.corpus.models import (
    AcceptedSource,
    BuildManifest,
    CorpusInputError,
    CorpusOutputError,
    DiscoveryAggregate,
    DiscoveryInput,
    EvidenceChunk,
    EvidenceDocument,
)
from clinical_doc_assist.research.models import SCHEMA_VERSION

NCT_PREFIX = "NCT"


def load_discovery_artifact(path: Path) -> DiscoveryInput:
    """Load and validate one feature 002 discovery artifact."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusInputError(f"Cannot read discovery artifact {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CorpusInputError(f"Discovery artifact {path} must contain an object.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise CorpusInputError(
            f"Discovery artifact {path} must use schema_version {SCHEMA_VERSION}."
        )

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise CorpusInputError(f"Discovery artifact {path} has no valid run_id.")

    status = payload.get("status")
    if status not in {"completed", "no_results"}:
        raise CorpusInputError(f"Discovery artifact {path} must be completed or no_results.")

    accepted = payload.get("accepted")
    if not isinstance(accepted, list):
        raise CorpusInputError(f"Discovery artifact {path} has no accepted list.")

    accepted_ids: list[str] = []
    for decision in accepted:
        if not isinstance(decision, dict) or decision.get("status") != "accepted":
            raise CorpusInputError(
                f"Discovery artifact {path} contains an invalid accepted decision."
            )
        candidate = decision.get("candidate")
        nct_id = candidate.get("nct_id") if isinstance(candidate, dict) else None
        if not _is_nct_id(nct_id):
            raise CorpusInputError(f"Discovery artifact {path} contains an invalid NCT identifier.")
        if nct_id not in accepted_ids:
            accepted_ids.append(nct_id)

    return DiscoveryInput(
        path=str(path),
        run_id=run_id,
        schema_version=SCHEMA_VERSION,
        status=status,
        accepted_ids=tuple(accepted_ids),
    )


def aggregate_discovery_artifacts(paths: Sequence[Path]) -> DiscoveryAggregate:
    """Load multiple discovery artifacts and deduplicate accepted identifiers."""

    if not paths:
        raise CorpusInputError("At least one discovery artifact is required.")

    inputs = tuple(load_discovery_artifact(path) for path in paths)
    source_runs: dict[str, list[str]] = {}
    for discovery in inputs:
        for nct_id in discovery.accepted_ids:
            run_ids = source_runs.setdefault(nct_id, [])
            if discovery.run_id not in run_ids:
                run_ids.append(discovery.run_id)

    sources = tuple(
        AcceptedSource(nct_id=nct_id, run_ids=tuple(run_ids))
        for nct_id, run_ids in source_runs.items()
    )
    return DiscoveryAggregate(inputs=inputs, sources=sources)


def write_corpus_artifacts(
    directory: Path,
    manifest: BuildManifest,
    documents: Iterable[EvidenceDocument],
    chunks: Iterable[EvidenceChunk],
) -> None:
    """Write all corpus artifact files into an existing directory."""

    try:
        directory.mkdir(parents=True, exist_ok=True)
        _write_json(directory / "manifest.json", manifest.to_dict())

        document_records = tuple(documents)
        chunk_records = tuple(chunks)
        if document_records:
            _write_jsonl(
                directory / "documents.jsonl",
                (document.to_dict() for document in document_records),
            )
        if chunk_records:
            _write_jsonl(
                directory / "chunks.jsonl",
                (chunk.to_dict() for chunk in chunk_records),
            )
    except OSError as exc:
        raise CorpusOutputError(f"Cannot write corpus artifacts in {directory}: {exc}") from exc


def prepare_output_directory(output: Path) -> None:
    """Ensure the final output directory can be replaced safely."""

    try:
        if output.exists():
            if not output.is_dir():
                raise CorpusOutputError(f"Output path {output} is not a directory.")
            if any(output.iterdir()):
                raise CorpusOutputError(f"Output directory {output} is not empty.")
    except OSError as exc:
        raise CorpusOutputError(f"Cannot inspect output path {output}: {exc}") from exc


def commit_output_directory(temporary: Path, output: Path) -> None:
    """Atomically move a completed temporary build to its final path."""

    try:
        if output.exists():
            output.rmdir()
        os.replace(temporary, output)
    except OSError as exc:
        raise CorpusOutputError(f"Cannot publish corpus to {output}: {exc}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False))
            stream.write("\n")


def _is_nct_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 11
        and value.startswith(NCT_PREFIX)
        and value[3:].isdigit()
    )
