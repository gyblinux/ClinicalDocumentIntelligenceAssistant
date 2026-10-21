# Artifact Contract: Model Output and Answer Runs

## Model Response

The final model response is JSON only and has one of two shapes.

### Answered

```json
{
  "status": "answered",
  "claims": [
    {
      "text": "One factual statement.",
      "citation_ids": ["chunk-..."]
    }
  ]
}
```

### Insufficient Evidence

```json
{
  "status": "insufficient_evidence",
  "reason": "The supplied evidence does not report the requested result."
}
```

Rules:

- Unknown statuses are invalid.
- `answered` requires at least one claim.
- Every claim requires non-empty text and at least one citation ID.
- `insufficient_evidence` contains no factual claims.
- The model must not author canonical URLs, hashes, or source records.
- Citation IDs use exact `chunk_id` values or
  `trial-metadata:NCT########`.

## Persisted Answer Run

Example of a valid answered artifact:

This abbreviated example shows one evidence item. A real artifact includes the
complete accepted evidence packet, up to 10 results.

```json
{
  "schema_version": "1.0",
  "answer_id": "answer-0123456789abcdef",
  "created_at": "2026-10-21T12:00:08Z",
  "status": "answered",
  "question": "What did NCT07424430 aim to evaluate?",
  "retrieval_id": "retrieval-0123456789abcdef",
  "retrieval_created_at": "2026-10-21T11:58:00Z",
  "evidence": [
    {
      "rank": 2,
      "score": 0.8394273,
      "chunk_id": "chunk-7f7563be8042d8cdfa51a2fa",
      "document_id": "doc-NCT07424430",
      "nct_id": "NCT07424430",
      "section": "summary",
      "text": "The goal of this study is to better understand the real-world effectiveness of semaglutide use on cardio-kidney-metabolic outcomes among adults with T2D and adults with obesity. This is a retrospective longitudinal analysis using the LMC Diabetes Registry. The primary outcome is change in HbA1c from baseline to 3 years among adults with T2D who initiated semaglutide compared with those who initiated other AHAs.",
      "source_url": "https://clinicaltrials.gov/study/NCT07424430",
      "content_hash": "773bb4f334782516bd7ec12073f0f7ddbbb0c47848ca9cf6a4802255e3f3b689"
    }
  ],
  "model": {
    "provider": "deepseek",
    "model": "deepseek-flash",
    "prompt_version": "answering-v1",
    "max_model_turns": 2,
    "max_tool_calls": 3,
    "max_evidence_items": 10,
    "max_output_tokens": 1600,
    "max_claims": 10
  },
  "claims": [
    {
      "claim_id": "claim-1",
      "text": "The study aimed to assess semaglutide's real-world effectiveness on cardio-kidney-metabolic outcomes in adults with type 2 diabetes and adults with obesity.",
      "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"]
    },
    {
      "claim_id": "claim-2",
      "text": "Its primary outcome was change in HbA1c from baseline to three years among adults with type 2 diabetes who initiated semaglutide versus other glucose-lowering therapies.",
      "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"]
    }
  ],
  "reason": null,
  "model_output": "{\"status\":\"answered\",\"claims\":[...]}",
  "citations": [
    {
      "citation_id": "chunk-7f7563be8042d8cdfa51a2fa",
      "source_type": "retrieval_evidence",
      "nct_id": "NCT07424430",
      "section": "summary",
      "source_url": "https://clinicaltrials.gov/study/NCT07424430",
      "content_hash": "773bb4f334782516bd7ec12073f0f7ddbbb0c47848ca9cf6a4802255e3f3b689",
      "lookup_id": null
    }
  ],
  "tool_calls": [],
  "usage": {
    "input_tokens": 850,
    "output_tokens": 115,
    "total_tokens": 965,
    "estimated_cost": null
  },
  "latency_ms": 4200,
  "errors": [],
  "disclaimer": "This is a summary of public research documents, not clinical advice or a substitute for professional medical judgment."
}
```

## Insufficient-Evidence Artifact

```json
{
  "schema_version": "1.0",
  "answer_id": "answer-0123456789abcdef",
  "created_at": "2026-10-21T12:00:08Z",
  "status": "insufficient_evidence",
  "question": "What were the final reported results?",
  "retrieval_id": "retrieval-0123456789abcdef",
  "retrieval_created_at": "2026-10-21T11:58:00Z",
  "evidence": [],
  "model": {
    "provider": "deepseek",
    "model": "deepseek-flash",
    "prompt_version": "answering-v1",
    "max_model_turns": 2,
    "max_tool_calls": 3,
    "max_evidence_items": 10,
    "max_output_tokens": 1600,
    "max_claims": 10
  },
  "claims": [],
  "reason": "The retrieval run contained no evidence.",
  "model_output": null,
  "citations": [],
  "tool_calls": [],
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null,
    "estimated_cost": null
  },
  "latency_ms": 8,
  "errors": [],
  "disclaimer": "This is a summary of public research documents, not clinical advice or a substitute for professional medical judgment."
}
```

## Failed Artifact

A `failed` artifact uses the same identity and evidence snapshot fields, with:

- `status`: `failed`
- Empty `claims`
- Null `reason` unless a safe explanation is useful
- Every attempted tool call
- Available usage and latency
- At least one non-empty `errors` entry

Partial claims must not be included when any citation or model-response validation
fails.

## Feature 006 Handoff

Feature 006 consumes three versioned inputs per evaluation case:

1. The fixed evaluation case.
2. The feature 004 retrieval run that produced the evidence.
3. The feature 005 answer record that references that retrieval run.

The answer record provides claims, validated citations, abstention or failure
status, tool activity, latency, and token usage. The retrieval run provides rank,
score, retrieval status, and retrieval-stage errors. A matching `retrieval_id`
links the two artifacts.

The answer record preserves the answer-side outputs used for scoring, while the
fixed case supplies expected evidence and reference facts. The answer record is
not a substitute for the retrieval artifact when evaluating retrieval relevance or
diagnosing retrieval failures.
