"""ClinicalTrials.gov discovery adapter."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from clinical_doc_assist.research.models import (
    DiscoveryRequest,
    ResearchCandidate,
    SourceError,
)

API_URL = "https://clinicaltrials.gov/api/v2/studies"
STUDY_URL = "https://clinicaltrials.gov/study/{nct_id}"
RESPONSE_FIELDS = (
    "NCTId",
    "BriefTitle",
    "OfficialTitle",
    "OverallStatus",
    "StudyType",
    "LastUpdatePostDate",
    "StudyFirstPostDate",
    "BriefSummary",
    "LeadSponsorName",
)


class ClinicalTrialsSource:
    """Search the first approved public clinical research source."""

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def close(self) -> None:
        """Close the owned HTTP client."""

        if self._owns_client:
            self._client.close()

    def search(
        self,
        request: DiscoveryRequest,
        *,
        query: str,
    ) -> list[ResearchCandidate]:
        """Return normalized candidates for one query."""

        normalized_query = query.strip()
        if not normalized_query:
            raise SourceError("search query cannot be empty.")

        params = {
            "query.term": normalized_query,
            "filter.advanced": (
                "AREA[LastUpdatePostDate]"
                f"RANGE[{request.updated_after.isoformat()},"
                f"{request.updated_before.isoformat()}]"
            ),
            "pageSize": str(request.limit),
            "fields": ",".join(RESPONSE_FIELDS),
            "sort": "LastUpdatePostDate:desc",
        }
        try:
            response = self._client.get(API_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SourceError(
                f"ClinicalTrials.gov returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"ClinicalTrials.gov request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError("ClinicalTrials.gov returned invalid JSON.") from exc

        studies = payload.get("studies") if isinstance(payload, dict) else None
        if not isinstance(studies, list):
            raise SourceError("ClinicalTrials.gov response has no studies list.")

        return [self._normalize(study) for study in studies if isinstance(study, dict)]

    @staticmethod
    def _normalize(study: dict[str, Any]) -> ResearchCandidate:
        protocol = _mapping(study.get("protocolSection"))
        identification = _mapping(protocol.get("identificationModule"))
        status_module = _mapping(protocol.get("statusModule"))
        sponsors = _mapping(protocol.get("sponsorCollaboratorsModule"))
        description = _mapping(protocol.get("descriptionModule"))
        design = _mapping(protocol.get("designModule"))

        nct_id = _text(identification.get("nctId"))
        title = (
            _text(identification.get("briefTitle"))
            or _text(identification.get("officialTitle"))
            or ""
        )
        summary = _text(description.get("briefSummary")) or ""
        sponsor = _text(_mapping(sponsors.get("leadSponsor")).get("name"))

        return ResearchCandidate(
            nct_id=nct_id,
            title=title,
            source_url=STUDY_URL.format(nct_id=nct_id) if nct_id else API_URL,
            source_type="trial_registry",
            updated_date=_date_from_struct(status_module.get("lastUpdatePostDateStruct")),
            first_posted_date=_date_from_struct(status_module.get("studyFirstPostDateStruct")),
            status=_text(status_module.get("overallStatus")),
            study_type=_text(design.get("studyType")),
            sponsor=sponsor,
            evidence_snippet=" ".join(summary.split())[:500],
        )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _date_from_struct(value: object) -> date | None:
    raw_date = _text(_mapping(value).get("date"))
    if raw_date is None:
        return None
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None
