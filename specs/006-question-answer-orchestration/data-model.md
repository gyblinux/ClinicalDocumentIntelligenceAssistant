# Data Model: Question-to-Answer Orchestration

## QuestionRequest

| Field | Type | Rule |
| --- | --- | --- |
| `question` | string | Required; trimmed; non-empty |
| `collection` | string | Required; trimmed; non-empty |
| `limit` | integer | Defaults to 5; range 1-50 |

The normalized `question` must be passed unchanged to retrieval.

## StageStatus

Allowed stage states:

- `not_started`
- `completed`
- `insufficient_evidence`
- `failed`

Stage status is separate from the overall pipeline status.

## PipelineStatus

| Status | Meaning |
| --- | --- |
| `answered` | Retrieval succeeded and feature 005 returned a cited answer |
| `insufficient_evidence` | Retrieval or answering explicitly abstained |
| `failed` | A required stage or artifact operation failed |

## ArtifactReference

| Field | Type | Rule |
| --- | --- | --- |
| `artifact_id` | string | Retrieval, answer, or pipeline identifier |
| `path` | string | Project-relative persisted path |
| `status` | StageStatus | Persisted stage state |

## StageTiming

| Field | Type | Rule |
| --- | --- | --- |
| `retrieval_ms` | integer or null | Null if retrieval did not run |
| `answer_ms` | integer or null | Null if answering did not run |
| `total_ms` | integer | Non-negative end-to-end duration |

## ConfigurationSnapshot

| Field | Type | Rule |
| --- | --- | --- |
| `collection` | string | Vector collection used |
| `limit` | integer | Requested retrieval limit |
| `embedding_model` | string or null | Effective retrieval model when available |
| `embedding_dimension` | integer or null | Effective dimension when available |
| `answer_model` | string or null | Effective answer model when answering ran |
| `prompt_version` | string or null | Feature 005 prompt version when answering ran |

Secrets must never appear in the snapshot.

## AnswerSummary

| Field | Type | Rule |
| --- | --- | --- |
| `answer_id` | string | Required when an answer artifact exists |
| `status` | string | `answered`, `insufficient_evidence`, or `failed` |
| `claims` | object array | Copied from the validated answer record |
| `reason` | string or null | Abstention explanation |
| `citation_ids` | string array | Unique validated citation IDs |

## PipelineRun

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `pipeline_id` | string | Unique local identifier |
| `created_at` | ISO 8601 string | Completion time |
| `status` | PipelineStatus | Overall result |
| `request` | QuestionRequest | Exact submitted request |
| `configuration` | ConfigurationSnapshot | Effective settings |
| `retrieval` | ArtifactReference or null | Feature 004 artifact link |
| `answer` | ArtifactReference or null | Feature 005 artifact link |
| `answer_summary` | AnswerSummary or null | User-facing answer outcome |
| `timing` | StageTiming | Stage and total timing |
| `errors` | string array | Visible failures |

The pipeline record links artifacts and includes a small normalized answer
summary. It does not duplicate full evidence, tool payloads, or detailed citation
provenance.

## State Transitions

```text
validated
  -> retrieval_started
  -> retrieval_failed -> failed
  -> retrieval_persisted
       -> no_results -> answer_started -> insufficient_evidence
       -> completed  -> answer_started
                         -> answer_persisted -> answered
                         -> answer_persisted -> insufficient_evidence
                         -> answer_persisted -> failed
```

Invalid input fails before the `validated` state and does not create a pipeline
record.

## Artifact Path Rules

Default output locations:

```text
artifacts/retrieval/<retrieval_id>.json
artifacts/answers/<answer_id>.json
artifacts/pipelines/<pipeline_id>.json
```

Paths stored in the pipeline record are project-relative when the output path is
inside the repository. Existing files are not silently overwritten.

## Feature 007 Link

Feature 007 reads:

1. The pipeline record.
2. The feature 004 artifact referenced by the record.
3. The feature 005 artifact referenced by the record, when present.

Evaluation results reference `pipeline_id` and `answer_id`; they do not mutate the
original artifacts.
