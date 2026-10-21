from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_doc_assist.retrieval.corpus import load_corpus
from clinical_doc_assist.retrieval.models import RetrievalInputError

FIXTURE = Path(__file__).parent / "fixtures" / "retrieval" / "corpus"


def test_loads_valid_corpus_and_chunks() -> None:
    corpus = load_corpus(FIXTURE)

    assert corpus.manifest.build_id == "corpus-fixture"
    assert corpus.manifest.status == "completed"
    assert len(corpus.documents) == 1
    assert len(corpus.chunks) == 2
    assert corpus.chunks[0].chunk_id == "chunk-001"


def test_rejects_empty_corpus(tmp_path: Path) -> None:
    _copy_corpus(tmp_path)
    manifest = _read_json(tmp_path / "manifest.json")
    manifest["chunk_count"] = 0
    _write_json(tmp_path / "manifest.json", manifest)
    (tmp_path / "chunks.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(RetrievalInputError, match="no chunks"):
        load_corpus(tmp_path)


def test_rejects_schema_count_and_missing_document(tmp_path: Path) -> None:
    _copy_corpus(tmp_path)
    manifest = _read_json(tmp_path / "manifest.json")
    manifest["schema_version"] = "2.0"
    _write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(RetrievalInputError, match="schema_version"):
        load_corpus(tmp_path)

    _copy_corpus(tmp_path)
    manifest = _read_json(tmp_path / "manifest.json")
    manifest["chunk_count"] = 3
    _write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(RetrievalInputError, match="chunk_count"):
        load_corpus(tmp_path)

    _copy_corpus(tmp_path)
    chunk = json.loads((tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    chunk["document_id"] = "doc-missing"
    (tmp_path / "chunks.jsonl").write_text(
        json.dumps(chunk) + "\n",
        encoding="utf-8",
    )
    manifest["chunk_count"] = 1
    _write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(RetrievalInputError, match="document"):
        load_corpus(tmp_path)


def _copy_corpus(destination: Path) -> None:
    for name in ("manifest.json", "documents.jsonl", "chunks.jsonl"):
        (destination / name).write_bytes((FIXTURE / name).read_bytes())


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
