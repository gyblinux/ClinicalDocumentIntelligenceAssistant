from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from clinical_doc_assist.corpus.builder import CorpusBuilder
from clinical_doc_assist.corpus.models import BuildSettings, CorpusOutputError
from clinical_doc_assist.research.models import SourceError

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"


class FakeSource:
    def __init__(self, studies: dict[str, dict[str, object]]) -> None:
        self.studies = studies
        self.calls: list[str] = []

    def fetch_study(self, nct_id: str) -> dict[str, object]:
        self.calls.append(nct_id)
        study = self.studies.get(nct_id)
        if study is None:
            raise SourceError(f"Study {nct_id} unavailable")
        return study


def _study(nct_id: str = "NCT05214573") -> dict[str, object]:
    study = json.loads((FIXTURES / "study-NCT05214573.json").read_text(encoding="utf-8"))
    protocol = study["protocolSection"]
    assert isinstance(protocol, dict)
    identification = protocol["identificationModule"]
    assert isinstance(identification, dict)
    identification["nctId"] = nct_id
    return study


def _builder(source: FakeSource) -> CorpusBuilder:
    return CorpusBuilder(
        source=source,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
        build_id_factory=lambda: "corpus-test",
    )


def test_builds_deduplicated_corpus_across_artifacts(tmp_path: Path) -> None:
    source = FakeSource(
        {
            "NCT05214573": _study(),
            "NCT06811324": _study("NCT06811324"),
        }
    )
    output = tmp_path / "corpus"

    result = _builder(source).build(
        [FIXTURES / "discovery-a.json", FIXTURES / "discovery-b.json"],
        output,
        BuildSettings(),
    )

    assert result.manifest.status == "completed"
    assert result.manifest.document_count == 2
    assert result.manifest.chunk_count > 0
    assert source.calls == ["NCT05214573", "NCT06811324"]
    assert (output / "manifest.json").exists()
    assert (output / "documents.jsonl").exists()
    assert (output / "chunks.jsonl").exists()


def test_one_source_failure_creates_partial_build(tmp_path: Path) -> None:
    source = FakeSource({"NCT05214573": _study()})
    output = tmp_path / "partial"

    result = _builder(source).build(
        [FIXTURES / "discovery-a.json"],
        output,
        BuildSettings(),
    )

    assert result.manifest.status == "partial"
    assert result.manifest.document_count == 1
    assert result.manifest.source_failures[0].nct_id == "NCT06811324"
    assert result.manifest.source_failures[0].error_type == "source_error"
    assert result.manifest.source_failures[0].retryable is False
    assert (output / "manifest.json").exists()


def test_no_accepted_sources_creates_no_documents_manifest(tmp_path: Path) -> None:
    source = FakeSource({})
    output = tmp_path / "empty"

    result = _builder(source).build(
        [FIXTURES / "discovery-empty.json"],
        output,
        BuildSettings(),
    )

    assert result.manifest.status == "no_documents"
    assert result.manifest.document_count == 0
    assert source.calls == []
    assert (output / "manifest.json").exists()
    assert not (output / "documents.jsonl").exists()


def test_all_source_failures_create_failed_manifest(tmp_path: Path) -> None:
    source = FakeSource({})
    output = tmp_path / "failed"

    result = _builder(source).build(
        [FIXTURES / "discovery-a.json"],
        output,
        BuildSettings(),
    )

    assert result.manifest.status == "failed"
    assert result.manifest.document_count == 0
    assert len(result.manifest.source_failures) == 2
    assert (output / "manifest.json").exists()


def test_nonempty_output_is_rejected_before_retrieval(tmp_path: Path) -> None:
    source = FakeSource({"NCT05214573": _study()})
    output = tmp_path / "occupied"
    output.mkdir()
    (output / "existing.txt").write_text("occupied", encoding="utf-8")

    with pytest.raises(CorpusOutputError, match="not empty"):
        _builder(source).build(
            [FIXTURES / "discovery-a.json"],
            output,
            BuildSettings(),
        )

    assert source.calls == []


def test_unchanged_artifacts_rebuild_identically(tmp_path: Path) -> None:
    study = _study()
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = _builder(FakeSource({"NCT05214573": study})).build(
        [FIXTURES / "discovery-b.json"],
        first_output,
        BuildSettings(),
    )
    second = _builder(FakeSource({"NCT05214573": study})).build(
        [FIXTURES / "discovery-b.json"],
        second_output,
        BuildSettings(),
    )

    assert first.manifest.build_id == second.manifest.build_id
    assert (first_output / "documents.jsonl").read_text(encoding="utf-8") == (
        second_output / "documents.jsonl"
    ).read_text(encoding="utf-8")
    assert (first_output / "chunks.jsonl").read_text(encoding="utf-8") == (
        second_output / "chunks.jsonl"
    ).read_text(encoding="utf-8")
