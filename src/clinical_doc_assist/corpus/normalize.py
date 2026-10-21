"""Normalize detailed ClinicalTrials.gov records into evidence documents."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

from clinical_doc_assist.corpus.models import (
    AcceptedSource,
    DocumentSection,
    EvidenceDocument,
)
from clinical_doc_assist.research.models import SourceError

STUDY_URL = "https://clinicaltrials.gov/study/{nct_id}"

SECTION_ORDER = (
    "title",
    "status_dates",
    "summary",
    "conditions",
    "interventions",
    "eligibility",
    "outcomes",
    "sponsor",
)
SECTION_HEADINGS = {
    "title": "Title and Identifiers",
    "status_dates": "Status and Dates",
    "summary": "Summary",
    "conditions": "Conditions",
    "interventions": "Interventions",
    "eligibility": "Eligibility",
    "outcomes": "Outcomes",
    "sponsor": "Sponsor",
}


def normalize_study(
    study: dict[str, Any],
    accepted_source: AcceptedSource,
    *,
    retrieved_at: datetime,
) -> EvidenceDocument:
    """Create one deterministic evidence document from a detailed source."""

    protocol = _mapping(study.get("protocolSection"))
    identification = _mapping(protocol.get("identificationModule"))
    nct_id = _text(identification.get("nctId"))
    if nct_id != accepted_source.nct_id:
        raise SourceError(
            f"Study identifier {nct_id or 'missing'} does not match {accepted_source.nct_id}.",
            error_type="identity_mismatch",
        )

    title = _text(identification.get("briefTitle")) or _text(identification.get("officialTitle"))
    section_values = {
        "title": _title_section(title),
        "status_dates": _status_section(protocol),
        "summary": _summary_section(protocol),
        "conditions": _conditions_section(protocol),
        "interventions": _interventions_section(protocol),
        "eligibility": _eligibility_section(protocol),
        "outcomes": _outcomes_section(protocol),
        "sponsor": _sponsor_section(protocol),
    }

    sections = tuple(
        DocumentSection(
            name=name,
            heading=SECTION_HEADINGS[name],
            content=section_values[name],
        )
        for name in SECTION_ORDER
        if section_values[name]
    )
    unavailable = tuple(name for name in SECTION_ORDER if not section_values[name])
    content_hash = _hash("\n\n".join(f"{section.name}\n{section.content}" for section in sections))
    source_date = _date_from_struct(
        _mapping(protocol.get("statusModule")).get("lastUpdatePostDateStruct")
    )

    return EvidenceDocument(
        document_id=f"doc-{nct_id}",
        nct_id=nct_id,
        title=title or "",
        source_url=STUDY_URL.format(nct_id=nct_id),
        source_type="trial_registry",
        source_updated_date=source_date,
        retrieved_at=retrieved_at,
        contributing_run_ids=accepted_source.run_ids,
        sections=sections,
        unavailable_sections=unavailable,
        content_hash=content_hash,
    )


def _title_section(title: str | None) -> str:
    return title or ""


def _status_section(protocol: dict[str, Any]) -> str:
    status = _mapping(protocol.get("statusModule"))
    values = (
        ("Overall status", _text(status.get("overallStatus"))),
        ("Study start", _date_text(status.get("startDateStruct"))),
        ("Primary completion", _date_text(status.get("primaryCompletionDateStruct"))),
        ("Study completion", _date_text(status.get("completionDateStruct"))),
        ("First posted", _date_text(status.get("studyFirstPostDateStruct"))),
        ("Last updated", _date_text(status.get("lastUpdatePostDateStruct"))),
    )
    return _labeled_lines(values)


def _summary_section(protocol: dict[str, Any]) -> str:
    description = _mapping(protocol.get("descriptionModule"))
    return "\n\n".join(
        text
        for text in (
            _text(description.get("briefSummary")),
            _text(description.get("detailedDescription")),
        )
        if text
    )


def _conditions_section(protocol: dict[str, Any]) -> str:
    conditions = _mapping(protocol.get("conditionsModule")).get("conditions")
    return _bullet_list(conditions)


def _interventions_section(protocol: dict[str, Any]) -> str:
    interventions = _mapping(protocol.get("armsInterventionsModule")).get("interventions")
    if not isinstance(interventions, list):
        return ""

    lines = []
    for intervention in interventions:
        data = _mapping(intervention)
        name = _text(data.get("name"))
        if not name:
            continue
        intervention_type = _text(data.get("type"))
        description = _text(data.get("description"))
        label = f"{intervention_type}: {name}" if intervention_type else name
        lines.append(f"- {label}")
        if description:
            lines.append(f"  {description}")
    return "\n".join(lines)


def _eligibility_section(protocol: dict[str, Any]) -> str:
    eligibility = _mapping(protocol.get("eligibilityModule"))
    values = (
        ("Sex", _text(eligibility.get("sex"))),
        ("Minimum age", _text(eligibility.get("minimumAge"))),
        ("Criteria", _text(eligibility.get("eligibilityCriteria"))),
        ("Study population", _text(eligibility.get("studyPopulation"))),
    )
    return _labeled_lines(values)


def _outcomes_section(protocol: dict[str, Any]) -> str:
    outcomes = _mapping(protocol.get("outcomesModule"))
    lines: list[str] = []
    for label, key in (
        ("Primary outcome", "primaryOutcomes"),
        ("Secondary outcome", "secondaryOutcomes"),
    ):
        items = outcomes.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            data = _mapping(item)
            measure = _text(data.get("measure"))
            if not measure:
                continue
            lines.append(f"- {label}: {measure}")
            description = _text(data.get("description"))
            if description:
                lines.append(f"  {description}")
            timeframe = _text(data.get("timeFrame"))
            if timeframe:
                lines.append(f"  Time frame: {timeframe}")
    return "\n".join(lines)


def _sponsor_section(protocol: dict[str, Any]) -> str:
    sponsors = _mapping(protocol.get("sponsorCollaboratorsModule"))
    lead = _text(_mapping(sponsors.get("leadSponsor")).get("name"))
    collaborators = sponsors.get("collaborators")
    collaborator_names = []
    if isinstance(collaborators, list):
        collaborator_names = [
            name for item in collaborators if (name := _text(_mapping(item).get("name")))
        ]

    parts = []
    if lead:
        parts.append(f"Lead sponsor: {lead}")
    if collaborator_names:
        parts.append(f"Collaborators: {', '.join(collaborator_names)}")
    return "\n".join(parts)


def _labeled_lines(values: tuple[tuple[str, str | None], ...]) -> str:
    return "\n".join(f"{label}: {value}" for label, value in values if value)


def _bullet_list(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return "\n".join(f"- {item}" for item in value if isinstance(item, str) and item.strip())


def _date_text(value: object) -> str | None:
    parsed = _date_from_struct(value)
    return parsed.isoformat() if parsed is not None else None


def _date_from_struct(value: object) -> date | None:
    raw = _text(_mapping(value).get("date"))
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text or None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
