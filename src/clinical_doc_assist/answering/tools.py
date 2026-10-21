"""The single allowlisted ClinicalTrials.gov metadata tool."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from clinical_doc_assist.answering.models import (
    MAX_TOOL_CALLS,
    NCT_ID_PATTERN,
    AnsweringToolError,
    MetadataLookup,
)
from clinical_doc_assist.research.models import SourceError

METADATA_TOOL_NAME = "fetch_trial_metadata"
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": METADATA_TOOL_NAME,
        "description": (
            "Fetch compact public metadata for an NCT identifier that appears in "
            "the supplied retrieval evidence."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "description": "An allowed NCT identifier such as NCT07424430.",
                }
            },
            "required": ["nct_id"],
            "additionalProperties": False,
        },
    },
}


class TrialMetadataSource(Protocol):
    def fetch_study(self, nct_id: str) -> dict[str, Any]: ...


class TrialMetadataTool:
    """Execute bounded metadata lookups without allowing broad trial access."""

    def __init__(
        self,
        *,
        source: TrialMetadataSource,
        allowed_nct_ids: frozenset[str],
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        max_lookups: int = MAX_TOOL_CALLS,
    ) -> None:
        invalid_ids = [value for value in allowed_nct_ids if not NCT_ID_PATTERN.fullmatch(value)]
        if invalid_ids:
            raise ValueError("allowed_nct_ids contains an invalid identifier.")
        if max_lookups != MAX_TOOL_CALLS:
            raise ValueError(f"max_lookups must be {MAX_TOOL_CALLS}.")

        self._source = source
        self._allowed_nct_ids = allowed_nct_ids
        self._now = now or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: f"lookup-{uuid4().hex[:12]}")
        self._lookups: list[MetadataLookup] = []
        self._looked_up_nct_ids: set[str] = set()
        # Duplicate/blocked attempts are recorded but do not make another network call.
        self._source_lookup_count = 0

    @property
    def lookups(self) -> tuple[MetadataLookup, ...]:
        return tuple(self._lookups)

    def execute(self, nct_id: str) -> MetadataLookup:
        """Validate and execute one metadata lookup."""

        normalized_id = nct_id.strip()
        if not NCT_ID_PATTERN.fullmatch(normalized_id):
            raise AnsweringToolError(f"invalid NCT identifier: {nct_id!r}")
        if self._source_lookup_count >= MAX_TOOL_CALLS:
            raise AnsweringToolError(f"metadata lookup limit is {MAX_TOOL_CALLS}.")
        if normalized_id not in self._allowed_nct_ids:
            return self._record_failure(
                normalized_id,
                "NCT identifier is not present in retrieved evidence.",
            )
        if normalized_id in self._looked_up_nct_ids:
            return self._record_failure(
                normalized_id,
                "NCT metadata was already requested in this answer run.",
            )

        self._looked_up_nct_ids.add(normalized_id)
        self._source_lookup_count += 1
        try:
            raw_study = self._source.fetch_study(normalized_id)
            lookup = MetadataLookup(
                lookup_id=self._id_factory(),
                nct_id=normalized_id,
                requested_at=self._now(),
                status="completed",
                data=normalize_trial_metadata(raw_study, expected_nct_id=normalized_id),
            )
        except SourceError as exc:
            lookup = MetadataLookup(
                lookup_id=self._id_factory(),
                nct_id=normalized_id,
                requested_at=self._now(),
                status="failed",
                error=str(exc),
            )
        self._lookups.append(lookup)
        return lookup

    def _record_failure(self, nct_id: str, message: str) -> MetadataLookup:
        lookup = MetadataLookup(
            lookup_id=self._id_factory(),
            nct_id=nct_id,
            requested_at=self._now(),
            status="failed",
            error=message,
        )
        self._lookups.append(lookup)
        return lookup


def normalize_trial_metadata(
    study: dict[str, Any],
    *,
    expected_nct_id: str,
) -> dict[str, Any]:
    """Reduce a ClinicalTrials.gov study payload to compact public metadata."""

    protocol = _mapping(study.get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    status = _mapping(protocol.get("statusModule"))
    design = _mapping(protocol.get("designModule"))
    sponsors = _mapping(protocol.get("sponsorCollaboratorsModule"))
    arms = _mapping(protocol.get("armsInterventionsModule"))

    nct_id = _text(identification.get("nctId")) or expected_nct_id
    if nct_id != expected_nct_id:
        raise SourceError(
            f"ClinicalTrials.gov returned {nct_id} for requested {expected_nct_id}.",
            error_type="identifier_mismatch",
        )

    enrollment_info = _mapping(design.get("enrollmentInfo"))
    enrollment_count = enrollment_info.get("count")
    if isinstance(enrollment_count, bool) or not isinstance(enrollment_count, int):
        enrollment_count = None

    return {
        "nct_id": nct_id,
        "title": (
            _text(identification.get("briefTitle"))
            or _text(identification.get("officialTitle"))
        ),
        "overall_status": _text(status.get("overallStatus")),
        "study_type": _text(design.get("studyType")),
        "phases": _text_list(design.get("phases")),
        "enrollment": {
            "count": enrollment_count,
            "type": _text(enrollment_info.get("enrollmentType")),
        },
        "start_date": _date_value(status.get("startDateStruct")),
        "primary_completion_date": _date_value(status.get("primaryCompletionDateStruct")),
        "completion_date": _date_value(status.get("completionDateStruct")),
        "lead_sponsor": _text(_mapping(sponsors.get("leadSponsor")).get("name")),
        "interventions": _interventions(arms.get("interventions")),
    }


def _interventions(value: object) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str | None]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if name is None:
            continue
        result.append({"name": name, "type": _text(item.get("type"))})
    return result


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _date_value(value: object) -> str | None:
    return _text(_mapping(value).get("date"))
