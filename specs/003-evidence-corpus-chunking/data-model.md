# Data Model: Evidence Corpus Assembly and Chunking

## DiscoveryInput

One validated discovery artifact.

| Field | Type | Rule |
| --- | --- | --- |
| `path` | string | Local JSON artifact provided by the user |
| `schema_version` | string | Must equal `1.0` |
| `run_id` | string | Required and non-empty |
| `status` | enum | `completed` or `no_results` |
| `accepted_ids` | string array | NCT IDs extracted from accepted decisions |

## EvidenceDocument

One normalized source record.

| Field | Type | Rule |
| --- | --- | --- |
| `document_id` | string | Stable `doc-<nct_id>` value |
| `nct_id` | string | Matches an accepted identifier |
| `title` | string | Source title; may be empty only when marked unavailable |
| `source_url` | string | Canonical ClinicalTrials.gov study URL |
| `source_type` | string | Fixed as `trial_registry` |
| `source_updated_date` | date or null | From the detailed source |
| `retrieved_at` | ISO 8601 string | Build retrieval time |
| `contributing_run_ids` | string array | Every discovery run containing the accepted ID |
| `sections` | DocumentSection array | Named normalized content |
| `unavailable_sections` | string array | Sections absent from the source |
| `content_hash` | string | Hash of normalized searchable content |

## DocumentSection

| Field | Type | Rule |
| --- | --- | --- |
| `name` | string | Stable lowercase section identifier |
| `heading` | string | Human-readable section heading |
| `content` | string | Normalized text; no invented content |

## EvidenceChunk

| Field | Type | Rule |
| --- | --- | --- |
| `chunk_id` | string | Stable hash-derived identifier |
| `document_id` | string | Parent evidence document |
| `nct_id` | string | Source identifier |
| `section` | string | One section name |
| `chunk_index` | integer | Zero-based order within the section |
| `start_char` | integer | Inclusive character offset in section text |
| `end_char` | integer | Exclusive character offset in section text |
| `text` | string | Chunk text, maximum 1,200 characters |
| `content_hash` | string | Hash of chunk text |
| `source_url` | string | Canonical source link |

## SourceFailure

| Field | Type | Rule |
| --- | --- | --- |
| `nct_id` | string | Accepted identifier that failed |
| `reason` | string | Actionable retrieval or validation error |
| `error_type` | string | Stable category such as `http_status` or `identity_mismatch` |
| `http_status` | integer or null | Source HTTP status when applicable |
| `retryable` | boolean | Whether retrying the source may succeed |

## BuildManifest

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed corpus schema version, initially `1.0` |
| `build_id` | string | Unique build identifier |
| `status` | enum | `completed`, `partial`, `no_documents`, or `failed` |
| `created_at` | ISO 8601 string | Build completion time |
| `discovery_runs` | DiscoveryInput summary array | Input paths and run IDs |
| `settings` | object | Maximum characters and overlap |
| `document_count` | integer | Written documents |
| `chunk_count` | integer | Written chunks |
| `source_failures` | SourceFailure array | Per-source failures |
| `duplicate_identifiers` | object array | Identifier and contributing run IDs |
| `errors` | string array | Build-level failures |

## State Transitions

```text
inputs_validated
  -> no_documents
  -> sources_retrieved
       -> failed
       -> completed
       -> partial
```

Chunks are created only from successful documents. Feature 004 may consume only a
manifest with `completed` or `partial` status and a non-zero chunk count.
