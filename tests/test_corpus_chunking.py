from __future__ import annotations

from datetime import date, datetime

from clinical_doc_assist.corpus.chunking import (
    _is_sentence_boundary,
    chunk_document,
)
from clinical_doc_assist.corpus.models import (
    BuildSettings,
    DocumentSection,
    EvidenceDocument,
)


def _document(*sections: DocumentSection) -> EvidenceDocument:
    return EvidenceDocument(
        document_id="doc-NCT05214573",
        nct_id="NCT05214573",
        title="Example trial",
        source_url="https://clinicaltrials.gov/study/NCT05214573",
        source_type="trial_registry",
        source_updated_date=date(2025, 10, 10),
        retrieved_at=datetime(2026, 10, 21, 9, 0),
        contributing_run_ids=("run-fixture-a",),
        sections=sections,
        unavailable_sections=(),
        content_hash="document-hash",
    )


def test_short_section_stays_one_chunk() -> None:
    document = _document(DocumentSection("summary", "Summary", "Short evidence."))

    chunks = chunk_document(document, BuildSettings(max_chars=100, overlap_chars=10))

    assert len(chunks) == 1
    assert chunks[0].text == "Short evidence."
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len("Short evidence.")


def test_long_section_respects_maximum_and_overlap() -> None:
    text = " ".join(f"Sentence {index}." for index in range(40))
    document = _document(DocumentSection("summary", "Summary", text))

    chunks = chunk_document(document, BuildSettings(max_chars=90, overlap_chars=20))

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 90 for chunk in chunks)
    assert all(
        document.sections[0].content[chunk.start_char : chunk.end_char] == chunk.text
        for chunk in chunks
    )
    assert chunks[1].start_char < chunks[0].end_char


def test_chunks_do_not_cross_sections() -> None:
    document = _document(
        DocumentSection("summary", "Summary", "Summary evidence."),
        DocumentSection("conditions", "Conditions", "Type 2 diabetes."),
    )

    chunks = chunk_document(document, BuildSettings(max_chars=200, overlap_chars=20))

    assert [chunk.section for chunk in chunks] == ["summary", "conditions"]


def test_overlap_starts_on_word_boundaries() -> None:
    text = " ".join(f"Clinical evidence sentence {index}." for index in range(30))
    document = _document(DocumentSection("summary", "Summary", text))

    chunks = chunk_document(document, BuildSettings(max_chars=100, overlap_chars=20))

    for chunk in chunks[1:]:
        previous = text[chunk.start_char - 1]
        current = text[chunk.start_char]
        assert not (previous.isalnum() and current.isalnum())


def test_abbreviations_and_initials_are_not_sentence_boundaries() -> None:
    text = "Use e.g. aspirin at 0.5 mg for J. Smith."

    eg_period = text.index("e.g.") + 3
    assert not _is_sentence_boundary(text, eg_period, 0)
    assert _is_sentence_boundary(text, text.rindex("."), 0)


def test_chunk_ids_are_stable_for_unchanged_content() -> None:
    document = _document(DocumentSection("summary", "Summary", "Stable evidence."))
    settings = BuildSettings(max_chars=100, overlap_chars=10)

    first = chunk_document(document, settings)
    second = chunk_document(document, settings)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.content_hash for chunk in first] == [chunk.content_hash for chunk in second]


def test_unicode_content_is_preserved() -> None:
    document = _document(DocumentSection("title", "Title", "Trial \u00ae with \u2265 evidence."))

    chunks = chunk_document(document, BuildSettings())

    assert chunks[0].text == "Trial \u00ae with \u2265 evidence."
