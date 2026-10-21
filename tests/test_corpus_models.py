from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from clinical_doc_assist.corpus.models import (
    AcceptedSource,
    BuildManifest,
    BuildSettings,
    DiscoveryAggregate,
    DiscoveryInput,
    DocumentSection,
    EvidenceChunk,
    EvidenceDocument,
)


def _aggregate() -> DiscoveryAggregate:
    discovery_input = DiscoveryInput(
        path="discovery-a.json",
        run_id="run-a",
        schema_version="1.0",
        status="completed",
        accepted_ids=("NCT05214573",),
    )
    return DiscoveryAggregate(
        inputs=(discovery_input,),
        sources=(AcceptedSource("NCT05214573", ("run-a",)),),
    )


def _document() -> EvidenceDocument:
    section = DocumentSection("summary", "Summary", "Example evidence.")
    return EvidenceDocument(
        document_id="doc-NCT05214573",
        nct_id="NCT05214573",
        title="Example trial",
        source_url="https://clinicaltrials.gov/study/NCT05214573",
        source_type="trial_registry",
        source_updated_date=date(2025, 10, 10),
        retrieved_at=datetime(2026, 10, 21, 9, 0),
        contributing_run_ids=("run-a",),
        sections=(section,),
        unavailable_sections=("outcomes",),
        content_hash="document-hash",
    )


def test_build_settings_validate_limits() -> None:
    assert BuildSettings().to_dict() == {
        "max_chars": 1200,
        "overlap_chars": 150,
    }

    with pytest.raises(ValueError, match="max_chars"):
        BuildSettings(max_chars=0)
    with pytest.raises(ValueError, match="overlap_chars"):
        BuildSettings(max_chars=100, overlap_chars=100)


def test_discovery_aggregate_serializes_inputs_and_sources() -> None:
    payload = _aggregate().to_dict()

    assert payload["inputs"][0]["run_id"] == "run-a"
    assert payload["sources"][0] == {
        "nct_id": "NCT05214573",
        "run_ids": ["run-a"],
    }


def test_document_and_chunk_serialize_provenance() -> None:
    document = _document()
    chunk = EvidenceChunk(
        chunk_id="chunk-1",
        document_id=document.document_id,
        nct_id=document.nct_id,
        section="summary",
        chunk_index=0,
        start_char=0,
        end_char=len("Example evidence."),
        text="Example evidence.",
        content_hash="chunk-hash",
        source_url=document.source_url,
    )

    document_payload = document.to_dict()
    chunk_payload = chunk.to_dict()

    assert document_payload["source_updated_date"] == "2025-10-10"
    assert document_payload["sections"][0]["name"] == "summary"
    assert chunk_payload["document_id"] == document.document_id
    assert chunk_payload["end_char"] == len("Example evidence.")


def test_manifest_serializes_counts_and_duplicate_provenance() -> None:
    aggregate = DiscoveryAggregate(
        inputs=_aggregate().inputs,
        sources=(AcceptedSource("NCT05214573", ("run-a", "run-b")),),
    )
    manifest = BuildManifest(
        build_id="corpus-test",
        status="completed",
        created_at=datetime(2026, 10, 21, 9, 0),
        discovery=aggregate,
        settings=BuildSettings(),
        document_count=1,
        chunk_count=2,
        source_failures=(),
        errors=(),
    )

    payload = manifest.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["document_count"] == 1
    assert payload["duplicate_identifiers"] == [
        {"nct_id": "NCT05214573", "run_ids": ["run-a", "run-b"]}
    ]


def test_output_path_is_recorded_as_string() -> None:
    from clinical_doc_assist.corpus.models import CorpusBuildResult

    manifest = BuildManifest(
        build_id="corpus-test",
        status="no_documents",
        created_at=datetime(2026, 10, 21, 9, 0),
        discovery=_aggregate(),
        settings=BuildSettings(),
        document_count=0,
        chunk_count=0,
        source_failures=(),
        errors=(),
    )
    result = CorpusBuildResult(manifest=manifest, output=Path("artifacts/corpus/test"))

    assert Path(result.summary()["output"]) == Path("artifacts/corpus/test")
