from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from clinical_doc_assist.answering.citations import (
    parse_model_response,
    resolve_citations,
)
from clinical_doc_assist.answering.models import (
    AnsweringResponseError,
    CitationValidationError,
    EvidenceItem,
    MetadataLookup,
)


def evidence() -> EvidenceItem:
    return EvidenceItem(
        rank=1,
        score=0.9,
        chunk_id="chunk-1",
        document_id="doc-NCT07424430",
        nct_id="NCT07424430",
        section="summary",
        text="Semaglutide study evidence.",
        source_url="https://clinicaltrials.gov/study/NCT07424430",
        content_hash="a" * 64,
    )


def test_parse_supported_response() -> None:
    response = parse_model_response(
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {
                        "text": "The study evaluates semaglutide.",
                        "citation_ids": ["chunk-1"],
                    }
                ],
            }
        )
    )
    assert response.status == "answered"
    assert response.claims[0].text == "The study evaluates semaglutide."


def test_parse_insufficient_evidence_response() -> None:
    response = parse_model_response(
        '{"status":"insufficient_evidence","reason":"No outcome data."}'
    )
    assert response.status == "insufficient_evidence"
    assert response.reason == "No outcome data."


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "empty"),
        ("not-json", "valid JSON"),
        ("[]", "JSON object"),
        ('{"status":"other"}', "unknown status"),
        ('{"status":"answered","claims":[]}', "non-empty claims"),
        (
            '{"status":"insufficient_evidence","claims":['
            '{"text":"fact","citation_ids":["chunk-1"]}]}',
            "cannot contain claims",
        ),
    ],
)
def test_parse_rejects_invalid_model_response(content: str, message: str) -> None:
    with pytest.raises(AnsweringResponseError, match=message):
        parse_model_response(content)


def test_parse_rejects_more_than_ten_claims() -> None:
    claims = [
        {"text": f"Claim {index}.", "citation_ids": ["chunk-1"]}
        for index in range(11)
    ]

    with pytest.raises(AnsweringResponseError, match="cannot exceed 10 claims"):
        parse_model_response(json.dumps({"status": "answered", "claims": claims}))


def test_resolve_retrieval_citation_uses_canonical_provenance() -> None:
    response = parse_model_response(
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {"text": "Supported fact.", "citation_ids": ["chunk-1"]}
                ],
            }
        )
    )

    resolved = resolve_citations(response, (evidence(),), ())
    assert resolved.claims[0].claim_id == "claim-1"
    assert resolved.citations[0].source_url == (
        "https://clinicaltrials.gov/study/NCT07424430"
    )
    assert resolved.citations[0].content_hash == "a" * 64


def test_resolve_metadata_citation_requires_successful_lookup() -> None:
    response = parse_model_response(
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {
                        "text": "Status is recruiting.",
                        "citation_ids": ["trial-metadata:NCT07424430"],
                    }
                ],
            }
        )
    )
    lookup = MetadataLookup(
        lookup_id="lookup-1",
        nct_id="NCT07424430",
        requested_at=datetime.now(UTC),
        status="completed",
        data={"overall_status": "RECRUITING"},
    )

    resolved = resolve_citations(response, (evidence(),), (lookup,))
    assert resolved.citations[0].source_type == "trial_metadata"
    assert resolved.citations[0].lookup_id == "lookup-1"

    failed = MetadataLookup(
        lookup_id="lookup-2",
        nct_id="NCT07424430",
        requested_at=datetime.now(UTC),
        status="failed",
        error="not found",
    )
    with pytest.raises(CitationValidationError, match="no successful metadata lookup"):
        resolve_citations(response, (evidence(),), (failed,))


def test_resolve_rejects_unknown_citation() -> None:
    response = parse_model_response(
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {"text": "Unsupported.", "citation_ids": ["chunk-unknown"]}
                ],
            }
        )
    )

    with pytest.raises(CitationValidationError, match="does not match"):
        resolve_citations(response, (evidence(),), ())
