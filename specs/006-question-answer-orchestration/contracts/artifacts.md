# Artifact Contract: Question-to-Answer Pipeline

## Stage Artifacts

Each valid question that reaches retrieval produces:

```text
artifacts/retrieval/<retrieval_id>.json
```

When answering starts, it also produces:

```text
artifacts/answers/<answer_id>.json
```

The full stage contracts remain owned by feature 004 and feature 005.

## Pipeline Record

```json
{
  "schema_version": "1.0",
  "pipeline_id": "pipeline-0123456789abcdef",
  "created_at": "2026-10-21T12:00:10Z",
  "status": "answered",
  "request": {
    "question": "What did NCT07424430 aim to evaluate?",
    "collection": "clinical_evidence_v1",
    "limit": 5
  },
  "configuration": {
    "collection": "clinical_evidence_v1",
    "limit": 5,
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "embedding_dimension": 384,
    "answer_model": "deepseek-flash",
    "prompt_version": "answering-v1"
  },
  "retrieval": {
    "artifact_id": "retrieval-0123456789abcdef",
    "path": "artifacts/retrieval/retrieval-0123456789abcdef.json",
    "status": "completed"
  },
  "answer": {
    "artifact_id": "answer-0123456789abcdef",
    "path": "artifacts/answers/answer-0123456789abcdef.json",
    "status": "completed"
  },
  "answer_summary": {
    "answer_id": "answer-0123456789abcdef",
    "status": "answered",
    "claims": [
      {
        "claim_id": "claim-1",
        "text": "The study evaluates semaglutide outcomes.",
        "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"]
      }
    ],
    "reason": null,
    "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"]
  },
  "timing": {
    "retrieval_ms": 420,
    "answer_ms": 4300,
    "total_ms": 4720
  },
  "errors": []
}
```

## Insufficient-Evidence Record

For no-results retrieval:

- Pipeline `status`: `insufficient_evidence`
- Retrieval artifact remains linked with status `completed` or `no_results`
- Answer artifact remains linked with status `insufficient_evidence`
- `answer_summary.claims`: empty
- `answer_summary.reason`: non-empty

## Failed Record

For a retrieval failure:

- Pipeline `status`: `failed`
- Retrieval reference may be null
- Answer reference and summary are null
- Error identifies the retrieval stage

For an answer failure:

- Pipeline `status`: `failed`
- Retrieval reference remains available
- Answer reference remains available when the failed answer record was persisted
- Error identifies the answer stage

## Immutability and Evaluation

Feature 006 writes each artifact once and does not rewrite a completed answer.
Feature 007 reads the pipeline and linked stage artifacts and persists a separate
evaluation result referenced by `pipeline_id`. Evaluation must not alter or
withdraw the original answer record.
