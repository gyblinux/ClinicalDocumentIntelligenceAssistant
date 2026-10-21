# GLP-1 RAG Evaluation Baseline

**Date**: 2026-10-21

**Case set**: `glp1-eval-v1` (20 cases)

**Mode**: Generated through feature 006

**Evaluation ID**: `evaluation-3f9f0dabcff14677`

The evaluation artifacts are intentionally ignored under:

```text
artifacts/evaluations/baseline-v1/
```

## Aggregate Metrics

| Metric | Value |
| --- | ---: |
| Retrieval hit@k | 0.444444 |
| Retrieval recall@k | 0.444444 |
| Retrieval MRR | 0.244444 |
| Citation validity | 1.000000 |
| Citation coverage | 0.611111 |
| Required key-point coverage | 0.611111 |
| Refusal correctness | 0.650000 |
| Forbidden-statement violations | 0.000000 |

## Failure Attribution

Ten of 20 cases recorded failure diagnoses, all attributed first to retrieval.
Seven of those cases also abstained when expected evidence was unavailable,
producing missing-citation, missing-required-fact, and over-refusal diagnoses.

This indicates that the first baseline is limited primarily by retrieval coverage
for the fixed source-specific questions, not by invalid citations. Citation
validity was 1.0 for answered cases.

## Presentation Acceptance

A plain-text presentation was generated from the live case `glp1-001` pipeline and
its matching failed evaluation verdict. The view contained:

- A deterministic answer paragraph
- All seven validated claims
- One deduplicated source marker
- Explicit failed retrieval-relevance status
- No trust percentage
- The research-only disclaimer

## Delegated Readability Review

The project owner requested an AI-assisted readability review of five saved
presentation outputs. The review scored 9/10 and passed the configured threshold:

| Criterion | Score |
| --- | ---: |
| Direct answer | 2 |
| Claim completeness | 2 |
| Citation clarity | 2 |
| Structure | 1 |
| Caution and limitations | 2 |

The structure deduction reflects duplication between the extractive answer
paragraph and supporting detail, plus the awkward explicit line
`Confidence percentage: Not provided`.

The persisted review is intentionally local under
`artifacts/evaluations/presentation-reviews/`. The five available outputs include
answered, failed-evaluation, over-refusal, and correct-abstention views, but not a
genuine multi-source or conflicting-evidence view. Those two scenarios therefore
remain unverified, and this AI-assisted review must not be described as an
independent human review.

## Limitations

- Key-point coverage is a normalized text-match proxy, not semantic verification.
- Human readability review remains a manual reviewer step.
- The baseline uses one public ClinicalTrials.gov corpus and one answer model.
- This report is a development baseline, not a clinical validation.
