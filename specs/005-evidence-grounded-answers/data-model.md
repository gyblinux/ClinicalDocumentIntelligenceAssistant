# Data Model: Evidence-Grounded Answers

## RetrievalInput

Feature 004 schema version `1.0` is the only accepted input contract.

| Field | Type | Rule |
| --- | --- | --- |
| `retrieval_id` | string | Required and non-empty |
| `created_at` | ISO 8601 string | Required |
| `query.text` | string | Required; becomes the answer question |
| `query.collection` | string | Required |
| `query.limit` | integer | Required; 1-50 |
| `results` | EvidenceItem array | Required; `completed` has 1-10, `no_results` has 0 |
| `status` | enum | Must be `completed` or `no_results` |
| `errors` | string array | Preserved in the answer snapshot when present |

Invalid schema, missing provenance, duplicate evidence identifiers, more than 10
results, or retrieval status `failed` are input errors.

## EvidenceItem

| Field | Type | Rule |
| --- | --- | --- |
| `rank` | integer | One-based and unique |
| `score` | number | Preserved retrieval score |
| `chunk_id` | string | Required; unique citation identifier |
| `document_id` | string | Required |
| `nct_id` | string | Must match `NCT` followed by eight digits |
| `section` | string | Required and non-empty |
| `text` | string | Required and non-empty |
| `source_url` | URL | Required HTTP(S) public source |
| `content_hash` | string | Required and non-empty |

## AnswerConfig

| Field | Type | Rule |
| --- | --- | --- |
| `provider` | string | Fixed provider name, such as `deepseek` |
| `model` | string | Effective configured model |
| `prompt_version` | string | Fixed version for this answering contract |
| `max_model_turns` | integer | Fixed at `2` |
| `max_tool_calls` | integer | Fixed at `3` |
| `max_evidence_items` | integer | Fixed at `10` |
| `max_output_tokens` | integer | Fixed at `800` |
| `max_claims` | integer | Fixed at `10` |

## ModelClaim

Internal representation of one model-authored claim before application identifiers
and canonical provenance are added.

| Field | Type | Rule |
| --- | --- | --- |
| `text` | string | Required and non-empty |
| `citation_ids` | string array | Required; at least one entry |

## MetadataLookup

| Field | Type | Rule |
| --- | --- | --- |
| `lookup_id` | string | Local unique identifier |
| `nct_id` | string | Must occur in input evidence |
| `requested_at` | ISO 8601 string | Required |
| `status` | enum | `completed` or `failed` |
| `data` | object or null | Normalized public metadata on success |
| `error` | string or null | Failure detail |

Normalized metadata may contain title, overall status, study type, phase,
enrollment, start date, completion date, sponsors, and interventions. It must not
contain raw private or patient-level data.

## AnswerCitation

| Field | Type | Rule |
| --- | --- | --- |
| `citation_id` | string | `chunk_id` or `trial-metadata:NCT########` |
| `source_type` | enum | `retrieval_evidence` or `trial_metadata` |
| `nct_id` | string | Required |
| `section` | string or null | Retrieval evidence section when available |
| `source_url` | URL | Canonical application-provided source |
| `content_hash` | string or null | Retrieval content hash when available |
| `lookup_id` | string or null | Successful metadata lookup when applicable |

Citation identifiers are validated against two allowlists:

1. Exact retrieval `chunk_id` values in the input artifact.
2. Metadata citation IDs created from successful lookups for retrieved NCT IDs.

Model-authored URLs, NCT identifiers, hashes, and source names are not copied into
the artifact.

## AnswerClaim

| Field | Type | Rule |
| --- | --- | --- |
| `claim_id` | string | Application-generated sequential identifier |
| `text` | string | Model-authored factual statement |
| `citation_ids` | string array | At least one validated citation |

An `answered` run requires at least one claim. Every claim must reference at least
one matching entry in the run's citation collection.

## ModelUsage

| Field | Type | Rule |
| --- | --- | --- |
| `input_tokens` | integer or null | Recorded when provider returns it |
| `output_tokens` | integer or null | Recorded when provider returns it |
| `total_tokens` | integer or null | Recorded when provider returns it |
| `estimated_cost` | null | Not calculated by feature 005 |

## AnswerRun

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `answer_id` | string | Unique local run identifier |
| `created_at` | ISO 8601 string | Run completion time |
| `status` | enum | `answered`, `insufficient_evidence`, or `failed` |
| `question` | string | Copied from `RetrievalInput.query.text` |
| `retrieval_id` | string | Copied from input |
| `retrieval_created_at` | ISO 8601 string | Copied from input |
| `evidence` | EvidenceItem array | Accepted evidence snapshot |
| `model` | AnswerConfig | Effective model and prompt version |
| `claims` | AnswerClaim array | Empty for abstention or failure |
| `reason` | string or null | Required for insufficient evidence |
| `model_output` | string or null | Final model text preserved for review |
| `citations` | AnswerCitation array | Enriched from validated IDs |
| `tool_calls` | MetadataLookup array | Every attempted lookup |
| `usage` | ModelUsage | Provider usage when available |
| `latency_ms` | integer | End-to-end stage duration |
| `errors` | string array | Visible input-after-validation or runtime failures |
| `disclaimer` | string | Required research-only notice |

## Status Semantics

| Status | Claims | Reason | Process Exit |
| --- | --- | --- | --- |
| `answered` | At least one | Null | `0` |
| `insufficient_evidence` | Empty | Required | `0` |
| `failed` | Empty | Null or diagnostic | `1` |

An invalid or unreadable retrieval artifact produces CLI exit `2` and no answer
artifact because a trustworthy run identity and question are unavailable.

## Validation Order

```text
load_artifact
  -> reject_invalid_input
  -> abstain_if_no_results
  -> build_evidence_allowlist
  -> model_call
  -> execute_allowed_tool_calls
  -> final_model_call
  -> validate_model_response
  -> validate_citations
  -> persist_answer_artifact
```

## State Transitions

```text
loaded_no_results -> insufficient_evidence
loaded_with_evidence -> model_answered -> citations_valid -> answered
loaded_with_evidence -> model_abstained -> insufficient_evidence
loaded_with_evidence -> model_or_tool_failed -> failed
loaded_with_evidence -> malformed_or_invalid_citations -> failed
invalid_input -> rejected_without_artifact
```
