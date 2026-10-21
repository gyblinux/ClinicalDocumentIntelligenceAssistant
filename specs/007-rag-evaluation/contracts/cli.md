# CLI Contract: Evaluation and Presentation

## Run Evaluation

```text
clinical-doc-eval run \
  --cases PATH \
  [--pipeline-map PATH] \
  [--collection NAME] \
  [--limit 5] \
  [--output-dir artifacts/evaluations]
```

When `--pipeline-map` is supplied, evaluation uses saved pipeline records. The map
is a JSON object:

```json
{
  "case-001": "artifacts/pipelines/pipeline-abc.json",
  "case-002": "artifacts/pipelines/pipeline-def.json"
}
```

When omitted, evaluation invokes feature 006 for each case using the configured
collection and retrieval limit. Collection defaults to `clinical_evidence_v1` and
limit defaults to `5`. Docker and provider services must be available.

Standard output is one evaluation-run JSON object. Quality failures do not make the
CLI fail if the evaluation itself completed.

## Compare

```text
clinical-doc-eval compare \
  --baseline PATH \
  --candidate PATH \
  [--output PATH]
```

Comparison requires matching case/rubric versions and exactly one declared
configuration difference.

## Persist Human Review

```text
clinical-doc-eval review \
  --input PATH \
  [--output-dir artifacts/evaluations/presentation-reviews]
```

The input contains reviewer, date, rubric version, exactly five representative case
IDs, five criterion scores, aggregate score, threshold result, and notes. Invalid
scores or fewer/more than five cases fail with exit code `2`.

## Present

```text
clinical-doc-present \
  --pipeline PATH \
  [--case-id CASE_ID] \
  [--evaluation PATH] \
  [--output PATH]
```

Standard output is the complete plain-text answer view. When `--output` is omitted,
default metadata and text paths are created under `artifacts/presentations/`.
`--case-id` is required for a case-specific verdict; otherwise the view explicitly
shows the unevaluated state.

## Exit Codes

- `0`: evaluation or presentation completed
- `1`: valid input but pipeline/runtime/presentation generation failed
- `2`: invalid arguments, case set, artifact links, unsafe path, or incompatible
  comparison

## Output Separation

- Evaluation standard output: JSON.
- Presentation standard output: plain text.
- Diagnostics: standard error.
- No API key, token, or secret is printed or persisted.
