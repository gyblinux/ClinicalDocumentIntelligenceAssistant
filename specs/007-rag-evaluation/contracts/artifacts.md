# Artifact Contract: Evaluation Runs

## Evaluation Run

```json
{
  "schema_version": "1.0",
  "evaluation_id": "evaluation-0123456789abcdef",
  "created_at": "2026-10-21T13:00:00Z",
  "set_version": "glp1-eval-v1",
  "mode": "saved",
  "rubric_versions": ["rag-rubric-v1"],
  "configuration": {
    "collection": "clinical_evidence_v1",
    "limit": 5,
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "embedding_dimension": 384,
    "answer_model": "deepseek-flash",
    "prompt_version": "answering-v1"
  },
  "configuration_fingerprint": "sha256:...",
  "cases": [
    {
      "case_id": "case-001",
      "rubric_version": "rag-rubric-v1",
      "pipeline_id": "pipeline-abc",
      "retrieval_id": "retrieval-def",
      "answer_id": "answer-ghi",
      "configuration_fingerprint": "sha256:...",
      "metrics": [
        {"name": "retrieval_hit_at_k", "value": 1.0, "passed": true, "details": {"rank": 2}},
        {"name": "retrieval_recall_at_k", "value": 1.0, "passed": true, "details": {"found": 1, "expected": 1}},
        {"name": "citation_validity", "value": 1.0, "passed": true, "details": null},
        {"name": "required_key_point_coverage", "value": 1.0, "passed": true, "details": null}
      ],
      "diagnosis": {
        "failure_codes": [],
        "affected_stage": "none",
        "intervention": "none",
        "notes": null
      },
      "latency_ms": 4700,
      "usage": {"input_tokens": 1704, "output_tokens": 1176, "total_tokens": 2880}
    }
  ],
  "aggregates": [
    {"name": "retrieval_hit_at_k", "value": 0.9, "passed": null, "details": null},
    {"name": "citation_validity", "value": 1.0, "passed": null, "details": null}
  ],
  "errors": []
}
```

## Evaluation Verdict Artifact

```json
{
  "schema_version": "1.0",
  "suite_version": "glp1-eval-v1",
  "rubric_versions": ["rag-rubric-v1"],
  "verdicts": [
    {
      "verdict_id": "verdict-0123456789abcdef",
      "answer_id": "answer-ghi",
      "pipeline_id": "pipeline-abc",
      "case_id": "case-001",
      "suite_version": "glp1-eval-v1",
      "rubric_version": "rag-rubric-v1",
      "configuration_fingerprint": "sha256:...",
      "checks": {
        "retrieval_relevance": "passed",
        "citation_validity": "passed",
        "faithfulness": "passed",
        "refusal_correctness": "not_applicable"
      },
      "status": "passed",
      "evaluated_at": "2026-10-21T13:00:00Z"
    }
  ]
}
```

The wrapper makes suite and rubric versions visible before presentation matching.
No trust, correctness, or confidence percentage is permitted.

## Files

```text
artifacts/evaluations/<evaluation_id>.json
artifacts/evaluations/<evaluation_id>-verdicts.json
artifacts/presentations/<presentation_id>.json
artifacts/presentations/<presentation_id>.txt
artifacts/evaluations/presentation-reviews/<review_id>.json
```

Evaluation and presentation artifacts are separate from feature 005 and 006 source
artifacts and never overwrite them.

## Presentation Review

Human readability review records contain:

- Reviewer and time
- Rubric version
- Five representative case IDs
- Five criterion scores
- Aggregate score and threshold result
- Notes

The required threshold is at least `8/10`, with no zero for citation clarity or
caution.
