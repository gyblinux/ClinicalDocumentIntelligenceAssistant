# Presentation Contract: Plain-Text Answer View

## Default Format

```text
ANSWER
<extractive summary paragraph>

QUALITY
Status: <answered|insufficient_evidence|failed>
Citation checks: <passed|failed>
Evaluation: <matching verdict or not independently evaluated>
Confidence percentage: Not provided

SUPPORTING DETAIL
1. <claim text> [n]
2. <claim text> [n][m]

SOURCES
[1] NCT00000000 — <canonical URL> — sections: summary, title
[2] NCT00000001 — <canonical URL> — sections: summary

LIMITATIONS
<evidence/evaluation limitations>
This is a summary of public research documents, not clinical advice.
```

## Summary Construction

- Use only validated claim text in original order.
- Include whole claims; do not truncate or paraphrase with a model.
- Target 3-5 claims and no more than 180 words.
- Stop before adding a claim that would exceed the summary limit.
- If the first claim alone exceeds the limit, fail with
  `presentation_integrity_error`; do not truncate it.
- Append source markers after each claim.

## Source Numbering

- Scan all claims in original order.
- Number source groups by first citation appearance.
- Deduplicate by `(source_url, nct_id)`.
- Aggregate existing source sections inside one numbered group.
- Keep chunk IDs in the machine artifact, not in the plain-text source list.

## All-Claim Coverage

`SUPPORTING DETAIL` includes every validated claim. The summary may highlight only
the initial claims.

## Length

Count whitespace-separated tokens in the complete rendered text.

- Must be below 1,000 words.
- If complete non-truncated text reaches 1,000 words, fail with
  `presentation_too_long`.
- No lossy fallback is accepted in v1.

## Evaluation Status

If no verdict is supplied or any matching key differs:

```text
Evaluation: Not independently evaluated for this exact answer
```

If matching:

```text
Evaluation: Passed (suite glp1-eval-v1, rubric rag-rubric-v1)
  Retrieval relevance: passed
  Citation validity: passed
  Faithfulness: passed
  Refusal correctness: not_applicable
```

The required matching keys are `answer_id`, `pipeline_id`, `case_id`,
`suite_version`, `rubric_version`, and `configuration_fingerprint`.

When no case ID is supplied, the renderer treats the answer as unevaluated rather
than guessing which evaluation case should apply.

## Status Views

- `answered`: show summary, all claims, sources, quality, limitations.
- `insufficient_evidence`: show reason, quality, limitations; no answer paragraph
  or factual claims.
- `failed`: show stage failure and errors; no answer paragraph or factual claims.

## Determinism

The renderer version and input artifact IDs are stored in presentation metadata.
The same inputs and version produce byte-identical `.txt` output.
