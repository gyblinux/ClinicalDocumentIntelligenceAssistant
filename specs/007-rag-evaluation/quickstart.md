# Quickstart: RAG Evaluation and Answer Presentation

**Status**: Implemented; initial 20-case baseline completed on 2026-10-21

**Observed baseline**: Generated all 20 cases through feature 006 with no
evaluation-infrastructure errors. Retrieval hit@k was 0.444, citation validity was
1.0, refusal correctness was 0.65, and ten cases recorded retrieval-led failure
diagnoses. Details are in [evaluation-baseline.md](../../docs/evaluation-baseline.md).

## Prerequisites

- Completed feature 006 pipeline records, or Docker/DeepSeek services to generate
  them
- A versioned evaluation case JSON containing 20-40 cases
- Python project environment

See [the case contract](contracts/cases.md) for the test-set schema.

## Evaluate Saved Pipeline Records

Create a JSON map from case IDs to saved pipeline paths:

```json
{
  "case-001": "artifacts/pipelines/pipeline-001.json",
  "case-002": "artifacts/pipelines/pipeline-002.json"
}
```

Run:

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  run \
  --cases artifacts/evaluations/glp1-eval-v1.json \
  --pipeline-map artifacts/evaluations/glp1-pipeline-map.json \
  --output-dir artifacts/evaluations
```

Expected output is one evaluation-run JSON with per-case and aggregate metrics.
Quality failures are reported in the report and do not crash a completed
evaluation.

## Evaluate Current Pipelines

Start TEI, Qdrant, and provider configuration, then omit `--pipeline-map`:

```bash
docker compose up -d

./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  run \
  --cases artifacts/evaluations/glp1-eval-v1.json \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output-dir artifacts/evaluations
```

Each case executes the feature 006 orchestration flow and stores linked artifacts.

## Compare One Change

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  compare \
  --baseline artifacts/evaluations/evaluation-baseline.json \
  --candidate artifacts/evaluations/evaluation-candidate.json \
  --output artifacts/evaluations/comparison-v1.json
```

The command rejects comparisons with different case sets or more than one changed
configuration variable.

## Render a Plain-Text Answer

Without an evaluation verdict:

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  present \
  --pipeline artifacts/pipelines/pipeline-001.json
```

With an exact matching verdict:

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  present \
  --pipeline artifacts/pipelines/pipeline-001.json \
  --case-id case-001 \
  --evaluation artifacts/evaluations/evaluation-v1-verdicts.json
```

The evaluation command writes that file as a versioned artifact containing the
suite version, rubric versions, and verdict list. A verdict is displayed only when
its artifact IDs, suite, rubric, and configuration fingerprint match the rendered
answer.

The plain-text view is under 1,000 words and includes:

- A deterministic summary paragraph of at most 180 words
- Every validated claim in supporting details
- Deduplicated numbered sources
- Answer status and limitations
- A versioned evaluation verdict only when all match keys agree
- No trust percentage

## Human Review

Score five representative rendered answers from 0-2 on:

- Direct answer
- Claim completeness
- Citation clarity
- Structure
- Caution and limitations

Target at least 8/10, with no zero for citation clarity or caution.

Persist the completed review:

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.evaluation.cli \
  review \
  --input artifacts/evaluations/presentation-review-input.json \
  --output-dir artifacts/evaluations/presentation-reviews
```

## Tests

```bash
./.venv/Scripts/python.exe -m pytest -o addopts= -q
./.venv/Scripts/python.exe -m ruff check .
```
