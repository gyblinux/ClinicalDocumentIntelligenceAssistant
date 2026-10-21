# Contract: Fixed Evaluation Cases

## File

One schema-versioned JSON document contains all 20-40 cases.

The example below shows one case for brevity; a valid evaluation set must contain
20-40.

```json
{
  "schema_version": "1.0",
  "set_version": "glp1-eval-v1",
  "cases": [
    {
      "case_id": "case-001",
      "question": "What did NCT07424430 aim to evaluate?",
      "answerability": "answerable",
      "expected_evidence_ids": [
        "chunk-7f7563be8042d8cdfa51a2fa"
      ],
      "required_key_points": [
        "real-world effectiveness",
        "cardio-kidney-metabolic outcomes"
      ],
      "forbidden_statements": [],
      "rubric_version": "rag-rubric-v1"
    }
  ]
}
```

## Validation

- `schema_version` must be `1.0`.
- The evaluation set version is represented by a non-empty `set_version`.
- Exactly 20-40 cases.
- Case IDs are unique, non-empty, and stable.
- Questions are non-empty.
- `answerability` is `answerable` or `unanswerable`.
- Answerable cases require expected evidence and at least one key point.
- Unanswerable cases prohibit expected evidence and required key points.
- `rubric_version` is non-empty.
- Malformed or duplicate cases fail before any pipeline call.

## Key-Point Matching

Normalize text to lowercase, collapse whitespace, and remove insignificant
punctuation. A key point passes only when its normalized phrase occurs in the
combined validated claim text.

This is a deterministic proxy and must be reported as such. It is not presented as
proof of semantic faithfulness.
