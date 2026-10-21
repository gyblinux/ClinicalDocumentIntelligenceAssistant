from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from clinical_doc_assist.corpus.models import AcceptedSource
from clinical_doc_assist.corpus.normalize import normalize_study
from clinical_doc_assist.research.models import SourceError

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"


def _study() -> dict[str, object]:
    return json.loads((FIXTURES / "study-NCT05214573.json").read_text(encoding="utf-8"))


def test_normalizes_expected_sections() -> None:
    document = normalize_study(
        _study(),
        AcceptedSource("NCT05214573", ("run-fixture-a", "run-fixture-b")),
        retrieved_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
    )

    sections = {section.name: section.content for section in document.sections}
    assert document.document_id == "doc-NCT05214573"
    assert document.source_updated_date == date(2025, 10, 10)
    assert document.contributing_run_ids == ("run-fixture-a", "run-fixture-b")
    assert "Observational study" in sections["summary"]
    assert "GLP-1 receptor agonist" in sections["interventions"]
    assert "Major adverse cardiovascular events" in sections["outcomes"]
    assert "21 Years" in sections["eligibility"]
    assert document.unavailable_sections == ()


def test_missing_sections_are_reported_not_invented() -> None:
    study = _study()
    protocol = study["protocolSection"]
    assert isinstance(protocol, dict)
    protocol.pop("outcomesModule")
    protocol.pop("eligibilityModule")

    document = normalize_study(
        study,
        AcceptedSource("NCT05214573", ("run-fixture-a",)),
        retrieved_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
    )

    assert "outcomes" in document.unavailable_sections
    assert "eligibility" in document.unavailable_sections
    assert all(section.name not in {"outcomes", "eligibility"} for section in document.sections)


def test_missing_title_is_reported() -> None:
    study = _study()
    protocol = study["protocolSection"]
    assert isinstance(protocol, dict)
    identification = protocol["identificationModule"]
    assert isinstance(identification, dict)
    identification.pop("briefTitle")
    identification.pop("officialTitle")

    document = normalize_study(
        study,
        AcceptedSource("NCT05214573", ("run-fixture-a",)),
        retrieved_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
    )

    assert document.title == ""
    assert "title" in document.unavailable_sections


def test_identifier_mismatch_fails_closed() -> None:
    with pytest.raises(SourceError, match="NCT05214573"):
        normalize_study(
            _study(),
            AcceptedSource("NCT06811324", ("run-fixture-a",)),
            retrieved_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
        )


def test_unchanged_study_has_stable_document_hash() -> None:
    source = AcceptedSource("NCT05214573", ("run-fixture-a",))
    timestamp = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

    first = normalize_study(_study(), source, retrieved_at=timestamp)
    second = normalize_study(_study(), source, retrieved_at=timestamp)

    assert first.content_hash == second.content_hash
    assert first.sections == second.sections
