# Data Model: Research Document Discovery

## DiscoveryRequest

Represents one user request.

| Field | Type | Rule |
| --- | --- | --- |
| `topic` | string | Required, trimmed, 1-500 characters |
| `updated_after` | date | Required, inclusive lower bound |
| `updated_before` | date | Required, inclusive upper bound, not before `updated_after` |
| `limit` | integer | Default 5; range 1-20 |

## ResearchCandidate

Represents an authoritative result returned by the approved source adapter.

| Field | Type | Rule |
| --- | --- | --- |
| `nct_id` | string or null | Official identifier; shape `NCT` plus 8 digits when present |
| `title` | string | Required |
| `source_url` | string | Canonical ClinicalTrials.gov study URL |
| `source_type` | string | Fixed as `trial_registry` in this release |
| `updated_date` | date or null | `LastUpdatePostDate` |
| `first_posted_date` | date or null | `StudyFirstPostDate` |
| `status` | string or null | Overall study status |
| `study_type` | string or null | Study type |
| `sponsor` | string or null | Lead sponsor name |
| `evidence_snippet` | string | Trimmed brief summary, maximum 500 characters |

## ModelDecision

Represents the research agent's advisory reflection for one candidate.

| Field | Type | Rule |
| --- | --- | --- |
| `nct_id` | string | Must match a candidate from tool output |
| `status` | enum | `accepted`, `rejected`, or `needs_review` |
| `reason_codes` | string array | At least one supplied code |

Model decisions do not override deterministic rejections.

## ScreeningDecision

Represents the final, application-authoritative result.

| Field | Type | Rule |
| --- | --- | --- |
| `candidate` | ResearchCandidate | The record being assessed |
| `status` | enum | `accepted`, `rejected`, or `needs_review` |
| `reason_codes` | string array | Fixed reason codes explaining the result |
| `duplicate_of` | string or null | Original NCT ID when duplicate |

## DiscoveryRun

Represents the complete stage output.

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed discovery artifact version, initially `1.0` |
| `run_id` | string | Unique identifier for this discovery run |
| `status` | enum | `completed`, `no_results`, or `failed` |
| `request` | DiscoveryRequest | Original validated request |
| `current_time` | ISO 8601 string or null | Recorded before search |
| `searches` | search summary array | Terms and date windows used |
| `accepted` | ScreeningDecision array | Usable candidates |
| `rejected` | ScreeningDecision array | Deterministically or reflectively rejected |
| `needs_review` | ScreeningDecision array | Ambiguous or incomplete classifications |
| `errors` | string array | Visible stage failures |

## Reason Codes

- `approved_source`: source is the approved ClinicalTrials.gov adapter.
- `within_date_window`: update date is inside the inclusive window.
- `unique_identifier`: identifier is present and not duplicated.
- `relevant_topic`: model reflection found the candidate relevant.
- `off_topic`: model reflection found the candidate unrelated.
- `missing_identifier`: NCT identifier is absent or malformed.
- `invalid_date`: source date is missing or invalid.
- `outside_date_window`: update date is outside the request.
- `duplicate`: identifier was seen earlier.
- `ambiguous_metadata`: metadata is incomplete or conflicting.
- `missing_reflection`: no usable model decision was returned.

## State Transitions

```text
requested -> clock_recorded -> searched -> reflected -> screened -> completed
                                  |                      |
                                  `-> failed             `-> no_results
```

No transition reaches ingestion. A failed clock prevents every search.
