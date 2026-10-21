from __future__ import annotations

from datetime import date

import httpx
import pytest

from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource
from clinical_doc_assist.research.models import DiscoveryRequest, SourceError


def _record() -> dict[str, object]:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345678",
                "briefTitle": "Example trial",
                "officialTitle": "A longer example trial title",
            },
            "statusModule": {
                "overallStatus": "COMPLETED",
                "studyFirstPostDateStruct": {"date": "2024-02-01"},
                "lastUpdatePostDateStruct": {"date": "2026-01-15"},
            },
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Example Sponsor"}},
            "descriptionModule": {"briefSummary": "  Example evidence.\nAdditional detail.  "},
            "designModule": {"studyType": "INTERVENTIONAL"},
        }
    }


def test_search_uses_approved_api_and_normalizes_candidate() -> None:
    request = DiscoveryRequest(
        "GLP-1 outcomes",
        date(2023, 1, 1),
        date(2026, 10, 21),
        3,
    )
    captured: list[httpx.Request] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        captured.append(http_request)
        return httpx.Response(200, json={"studies": [_record()]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = ClinicalTrialsSource(client=client)

    candidates = source.search(request, query="GLP-1 cardiovascular")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.nct_id == "NCT12345678"
    assert candidate.title == "Example trial"
    assert candidate.source_url == "https://clinicaltrials.gov/study/NCT12345678"
    assert candidate.source_type == "trial_registry"
    assert candidate.updated_date == date(2026, 1, 15)
    assert candidate.evidence_snippet == "Example evidence. Additional detail."

    params = captured[0].url.params
    assert params["query.term"] == "GLP-1 cardiovascular"
    assert params["filter.advanced"] == ("AREA[LastUpdatePostDate]RANGE[2023-01-01,2026-10-21]")
    assert params["pageSize"] == "3"
    assert "NCTId" in params["fields"]
    assert "LastUpdatePostDate" in params["fields"]
    assert params["sort"] == "LastUpdatePostDate:desc"


def test_search_returns_empty_list_for_no_studies() -> None:
    request = DiscoveryRequest("trial", date(2023, 1, 1), date(2026, 1, 1))
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"studies": []}))
    )

    assert ClinicalTrialsSource(client=client).search(request, query="trial") == []


def test_search_reports_http_and_payload_failures() -> None:
    request = DiscoveryRequest("trial", date(2023, 1, 1), date(2026, 1, 1))

    http_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(503, json={"message": "unavailable"})
        )
    )
    with pytest.raises(SourceError, match="503"):
        ClinicalTrialsSource(client=http_client).search(request, query="trial")

    malformed_client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"studies": "not-a-list"}))
    )
    with pytest.raises(SourceError, match="studies"):
        ClinicalTrialsSource(client=malformed_client).search(request, query="trial")
