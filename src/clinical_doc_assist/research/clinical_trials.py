"""ClinicalTrials.gov discovery adapter."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
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
NCT_ID_PATTERN = re.compile(r"^NCT\d{8}$")
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_DELAY_SECONDS = 5.0


class ClinicalTrialsSource:
    """Search the first approved public clinical research source."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        max_retries: int = 1,
        retry_delay: float = 1.0,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if retry_delay < 0:
            raise ValueError("retry_delay cannot be negative.")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._sleep = sleep or time.sleep

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
        payload = self._get_json(API_URL, params=params)

        studies = payload.get("studies") if isinstance(payload, dict) else None
        if not isinstance(studies, list):
            raise SourceError("ClinicalTrials.gov response has no studies list.")

        return [self._normalize(study) for study in studies if isinstance(study, dict)]

    def fetch_study(self, nct_id: str) -> dict[str, Any]:
        """Fetch one detailed public study record by its approved identifier."""

        if not NCT_ID_PATTERN.fullmatch(nct_id):
            raise SourceError(
                f"Invalid NCT identifier: {nct_id}",
                error_type="validation_error",
            )

        payload = self._get_json(f"{API_URL}/{nct_id}")
        if not isinstance(payload, dict):
            raise SourceError("ClinicalTrials.gov study response must be an object.")
        return payload

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                retryable = status in RETRYABLE_HTTP_STATUSES
                if retryable and attempt < self._max_retries:
                    self._sleep(self._retry_after(exc.response))
                    continue
                raise SourceError(
                    f"ClinicalTrials.gov returned HTTP {status}.",
                    error_type="http_status",
                    http_status=status,
                    retryable=retryable,
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    self._sleep(self._retry_delay)
                    continue
                raise SourceError(
                    f"ClinicalTrials.gov request failed: {exc}",
                    error_type="transport_error",
                    retryable=True,
                ) from exc

            try:
                return response.json()
            except ValueError as exc:
                raise SourceError(
                    "ClinicalTrials.gov returned invalid JSON.",
                    error_type="invalid_response",
                ) from exc

        raise AssertionError("Retry loop exited without returning or raising.")

    def _retry_after(self, response: httpx.Response) -> float:
        raw_delay = response.headers.get("Retry-After")
        if raw_delay is None:
            return self._retry_delay
        try:
            delay = float(raw_delay)
        except ValueError:
            return self._retry_delay
        return max(0.0, min(delay, MAX_RETRY_DELAY_SECONDS))

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
