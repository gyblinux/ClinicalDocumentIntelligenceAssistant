# Data Model: RAG Evaluation and Answer Presentation

## EvaluationCase

| Field | Type | Rule |
| --- | --- | --- |
| `case_id` | string | Unique within the set |
| `question` | string | Required and non-empty |
| `answerability` | enum | `answerable` or `unanswerable` |
| `expected_evidence_ids` | string array | Required for answerable cases; stable chunk IDs |
| `required_key_points` | string array | Required for answerable cases |
| `forbidden_statements` | string array | Optional |
| `rubric_version` | string | Required |

## EvaluationSet

| Field | Type | Rule |
| --- | --- | --- |
| `set_version` | string | Required |
| `cases` | EvaluationCase array | Exactly 20-40 unique cases |

## MetricValue

| Field | Type | Rule |
| --- | --- | --- |
| `name` | enum | Defined metric name |
| `value` | number | Usually 0-1 or milliseconds |
| `passed` | boolean or null | Null when metric is informational |
| `details` | object or null | Supporting counts/ranks |

## FailureDiagnosis

| Field | Type | Rule |
| --- | --- | --- |
| `failure_codes` | string array | Versioned taxonomy |
| `affected_stage` | enum | `retrieval`, `answering`, `presentation`, `evaluation`, or `none` |
| `intervention` | enum | Prompt, retrieval, indexing, abstention, presentation, case/rubric, or none |
| `notes` | string or null | Human-readable summary |

Allowed failure codes:

- `retrieval_miss`
- `retrieval_low_rank`
- `missing_citation`
- `invalid_citation`
- `missing_required_fact`
- `forbidden_claim`
- `false_answer`
- `over_refusal`
- `stage_failure`
- `presentation_integrity_error`
- `presentation_too_long`

## CaseEvaluation

| Field | Type | Rule |
| --- | --- | --- |
| `case_id` | string | Matches test set |
| `rubric_version` | string | Case rubric applied |
| `pipeline_id` | string | Required |
| `retrieval_id` | string | Required |
| `answer_id` | string or null | Null if answering never started |
| `configuration_fingerprint` | string | Canonical configuration hash |
| `metrics` | MetricValue array | Includes per-stage metrics |
| `diagnosis` | FailureDiagnosis | Empty codes when successful |
| `latency_ms` | integer | Non-negative |
| `usage` | object | Token/cost data when available |

## EvaluationRun

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `evaluation_id` | string | Unique local identifier |
| `created_at` | ISO 8601 string | Completion time |
| `set_version` | string | Evaluation case-set version |
| `mode` | enum | `generated` or `saved` |
| `rubric_versions` | string array | Unique case rubric versions |
| `configuration` | object | Effective collection, limit, embedding, answer model, and prompt version |
| `configuration_fingerprint` | string | Canonical hash |
| `cases` | CaseEvaluation array | One per case |
| `aggregates` | MetricValue array | Required |
| `errors` | string array | Visible run failures |

## ComparisonRun

| Field | Type | Rule |
| --- | --- | --- |
| `baseline_id` | string | Required |
| `candidate_id` | string | Required |
| `changed_variable` | string | Exactly one |
| `baseline_value` | JSON scalar | Required |
| `candidate_value` | JSON scalar | Required |
| `metric_deltas` | object | Per-metric differences |
| `latency_delta_ms` | integer | Candidate minus baseline |
| `cost_delta` | number or null | Candidate minus baseline when available |
| `status` | enum | `valid` or `rejected` |

## EvaluationVerdict

| Field | Type | Rule |
| --- | --- | --- |
| `verdict_id` | string | Unique |
| `answer_id` | string | Exact answer match |
| `pipeline_id` | string | Exact pipeline match |
| `case_id` | string | Exact case match |
| `suite_version` | string | Exact suite match |
| `rubric_version` | string | Exact rubric match |
| `configuration_fingerprint` | string | Exact configuration match |
| `checks` | object | Named pass/fail check results |
| `status` | enum | `passed`, `failed`, or `not_applicable` |
| `evaluated_at` | ISO 8601 string | Required |

No `trust_percentage` or equivalent probability field is allowed.

## EvaluationVerdictArtifact

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `suite_version` | string | Evaluation suite that produced every verdict |
| `rubric_versions` | string array | Unique declared rubric versions |
| `verdicts` | EvaluationVerdict array | One artifact shared by the evaluation run |

Presentation may display a verdict only when the answer, pipeline, case,
configuration fingerprint, suite, and applicable rubric all match this artifact.

## PresentationReview

| Field | Type | Rule |
| --- | --- | --- |
| `review_id` | string | Unique |
| `reviewer` | string | Required |
| `created_at` | ISO 8601 string | Required |
| `rubric_version` | string | Required |
| `case_ids` | string array | Exactly five representative cases |
| `scores` | object | Five criteria, each 0-2 |
| `aggregate_score` | integer | 0-10 |
| `passed` | boolean | At least 8/10 and no zero for citation clarity or caution |
| `notes` | string or null | Reviewer explanation |

## PresentationRequest

| Field | Type | Rule |
| --- | --- | --- |
| `pipeline_path` | path | Required |
| `case_id` | string or null | Required to select a case-specific verdict |
| `evaluation_path` | path or null | Optional verdict input |
| `format` | enum | Fixed `text` for v1 |
| `renderer_version` | string | Fixed for the current template |

## RenderedAnswer

| Field | Type | Rule |
| --- | --- | --- |
| `presentation_id` | string | Unique |
| `created_at` | ISO 8601 string | Completion time |
| `pipeline_id` | string | Source pipeline |
| `answer_id` | string or null | Source answer |
| `renderer_version` | string | Required |
| `status` | enum | Copied answer/pipeline status |
| `summary` | string or null | Extractive paragraph, at most 180 words |
| `claims` | object array | Every validated claim with source markers |
| `sources` | object array | Canonical sources in first-appearance order |
| `evaluation` | EvaluationVerdict or null | Only when all match keys align |
| `limitations` | string array | Includes non-clinical-use disclaimer |
| `word_count` | integer | Must be below 1,000 |
| `output_path` | path | Persisted plain-text file |

## Presentation Source

| Field | Type | Rule |
| --- | --- | --- |
| `marker` | string | `[1]`, `[2]`, etc. |
| `nct_id` | string | From canonical citation |
| `source_url` | URL | Deduplicated canonical URL |
| `sections` | string array | Existing sections; ordered and unique |

## State Transitions

```text
case_set_valid
  -> pipeline_loaded_or_generated
  -> required_links_valid
  -> metrics_computed
  -> diagnosis_built
  -> evaluation_persisted

pipeline_loaded
  -> presentation_requested
  -> source_map_built
  -> verdict_matched_or_unevaluated
  -> invariants_valid
  -> presented_below_word_limit
  -> plain_text_persisted
```

Presentation violation produces `presentation_integrity_error` or
`presentation_too_long`; it never emits a lossy accepted view.
