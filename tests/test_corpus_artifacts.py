from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from clinical_doc_assist.corpus.artifacts import (
    aggregate_discovery_artifacts,
    commit_output_directory,
    load_discovery_artifact,
    prepare_output_directory,
    write_corpus_artifacts,
)
from clinical_doc_assist.corpus.models import (
    AcceptedSource,
    BuildManifest,
    BuildSettings,
    CorpusInputError,
    CorpusOutputError,
    DiscoveryAggregate,
    DiscoveryInput,
    DocumentSection,
    EvidenceChunk,
    EvidenceDocument,
)

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"


def test_loads_accepted_identifiers_only() -> None:
    discovery = load_discovery_artifact(FIXTURES / "discovery-a.json")

    assert discovery.run_id == "run-fixture-a"
    assert discovery.accepted_ids == ("NCT05214573", "NCT06811324")


def test_aggregates_duplicate_identifier_provenance() -> None:
    aggregate = aggregate_discovery_artifacts(
        [FIXTURES / "discovery-a.json", FIXTURES / "discovery-b.json"]
    )

    assert [item.nct_id for item in aggregate.sources] == [
        "NCT05214573",
        "NCT06811324",
    ]
    assert aggregate.sources[0].run_ids == ("run-fixture-a", "run-fixture-b")


def test_rejects_invalid_discovery_artifacts(tmp_path: Path) -> None:
    bad_schema = tmp_path / "bad-schema.json"
    bad_schema.write_text(
        json.dumps({"schema_version": "2.0", "run_id": "run-bad"}),
        encoding="utf-8",
    )
    with pytest.raises(CorpusInputError, match="schema_version"):
        load_discovery_artifact(bad_schema)

    bad_identifier = tmp_path / "bad-id.json"
    bad_identifier.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "run-bad",
                "status": "completed",
                "accepted": [
                    {
                        "status": "accepted",
                        "candidate": {"nct_id": "not-an-nct"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CorpusInputError, match="NCT"):
        load_discovery_artifact(bad_identifier)


def test_writes_manifest_documents_and_chunks(tmp_path: Path) -> None:
    document, chunk, manifest = _artifacts()

    write_corpus_artifacts(tmp_path, manifest, (document,), (chunk,))

    assert (
        json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["status"]
        == "completed"
    )
    assert (
        json.loads((tmp_path / "documents.jsonl").read_text(encoding="utf-8"))["nct_id"]
        == "NCT05214573"
    )
    assert (
        json.loads((tmp_path / "chunks.jsonl").read_text(encoding="utf-8"))["chunk_id"] == "chunk-1"
    )


def test_no_documents_writes_manifest_only(tmp_path: Path) -> None:
    _, _, manifest = _artifacts()
    manifest = BuildManifest(
        build_id="corpus-empty",
        status="no_documents",
        created_at=datetime(2026, 10, 21, 9, 0),
        discovery=DiscoveryAggregate((), ()),
        settings=BuildSettings(),
        document_count=0,
        chunk_count=0,
        source_failures=(),
        errors=(),
    )

    write_corpus_artifacts(tmp_path, manifest, (), ())

    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "documents.jsonl").exists()
    assert not (tmp_path / "chunks.jsonl").exists()


def test_rejects_file_as_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "corpus-file"
    output.write_text("not a directory", encoding="utf-8")

    with pytest.raises(CorpusOutputError, match="not a directory"):
        prepare_output_directory(output)


def test_wraps_directory_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    output = tmp_path / "corpus"

    def fail_replace(*_: object) -> None:
        raise PermissionError("access denied")

    monkeypatch.setattr("clinical_doc_assist.corpus.artifacts.os.replace", fail_replace)

    with pytest.raises(CorpusOutputError, match="Cannot publish"):
        commit_output_directory(temporary, output)


def _artifacts() -> tuple[EvidenceDocument, EvidenceChunk, BuildManifest]:
    discovery = DiscoveryInput(
        "discovery-a.json",
        "run-fixture-a",
        "1.0",
        "completed",
        ("NCT05214573",),
    )
    aggregate = DiscoveryAggregate(
        (discovery,),
        (AcceptedSource("NCT05214573", ("run-fixture-a",)),),
    )
    document = EvidenceDocument(
        "doc-NCT05214573",
        "NCT05214573",
        "Example trial",
        "https://clinicaltrials.gov/study/NCT05214573",
        "trial_registry",
        date(2025, 10, 10),
        datetime(2026, 10, 21, 9, 0),
        ("run-fixture-a",),
        (DocumentSection("summary", "Summary", "Evidence"),),
        (),
        "doc-hash",
    )
    chunk = EvidenceChunk(
        "chunk-1",
        document.document_id,
        document.nct_id,
        "summary",
        0,
        0,
        8,
        "Evidence",
        "chunk-hash",
        document.source_url,
    )
    manifest = BuildManifest(
        "corpus-test",
        "completed",
        datetime(2026, 10, 21, 9, 0),
        aggregate,
        BuildSettings(),
        1,
        1,
        (),
        (),
    )
    return document, chunk, manifest
