# Clinical Doc Assist

Clinical Doc Assist is a small, evidence-grounded RAG practice project. It
discovers public ClinicalTrials.gov records, builds a searchable evidence corpus,
answers questions with validated citations, evaluates quality against a fixed
20-case set, and renders deterministic plain-text answer views.

It is not a clinical decision-support system. Do not use it for diagnosis,
treatment, or patient-specific medical decisions.

## What it does

```text
public trial discovery
  -> normalized documents and deterministic chunks
  -> local embeddings and Qdrant vector search
  -> evidence-grounded cited answer
  -> linked retrieval/answer pipeline
  -> fixed-case evaluation
  -> readable answer presentation
```

Implemented capabilities:

- ClinicalTrials.gov discovery with current-time context and deterministic source
  screening.
- Corpus assembly with preserved NCT IDs, sections, URLs, and content hashes.
- Local TEI embeddings and Qdrant retrieval.
- DeepSeek Flash answers constrained to retrieved evidence.
- Claim-level citation validation, metadata-tool allowlisting, and abstention.
- One-question end-to-end orchestration with linked artifacts.
- Fixed 20-case evaluation, failure attribution, one-variable comparison, and
  versioned verdicts.
- Plain-text presentation with all claims, deduplicated sources, and no per-answer
  trust percentage.

## Engineering highlights

- Explicit stage boundaries with versioned JSON/JSONL artifacts.
- One bounded answering agent instead of unnecessary multi-agent orchestration.
- Local TEI and Qdrant services that keep heavyweight embedding dependencies out of
  the host Python process.
- Deterministic citation validation, abstention, indexing IDs, and presentation.
- A reproducible 20-case evaluation suite with separate retrieval and answer
  metrics.
- Offline-first testing with optional real Docker integration tests.
- GitHub Spec Kit specifications, plans, tasks, and requirement checklists for
  every implemented feature.

## Baseline results

The first generated evaluation run completed all 20 cases with zero
evaluation-infrastructure errors:

| Metric | Result |
| --- | ---: |
| Retrieval hit@k | 0.444 |
| Retrieval MRR | 0.244 |
| Citation validity | 1.000 |
| Citation coverage | 0.611 |
| Refusal correctness | 0.650 |
| Forbidden-statement violations | 0.000 |

The baseline identifies retrieval coverage as the primary weakness rather than
invalid citations. These figures are development measurements, not evidence of
clinical reliability. See the [full evaluation report](docs/evaluation-baseline.md).

## Documentation

| Document | Purpose |
| --- | --- |
| [Documentation index](docs/README.md) | Reading order for all project documentation |
| [Architecture brief](docs/architecture.md) | Current system design, stage boundaries, data flow, artifacts, and limitations |
| [Usage guide](docs/usage.md) | Setup, configuration, commands, evaluation, presentation, tests, and troubleshooting |
| [Technology guide](docs/technology-guide.md) | Beginner-to-intermediate explanations of the stack and RAG concepts |
| [Evaluation baseline](docs/evaluation-baseline.md) | Initial metrics, failure analysis, and known limitations |
| [Changelog](CHANGELOG.md) | User-visible and operationally important changes |

## Requirements

- Python 3.11+
- Git Bash on Windows
- Docker Desktop with Linux containers
- DeepSeek API key
- Internet access for ClinicalTrials.gov and DeepSeek

## Quick start

Install from Git Bash:

```bash
cd /path/to/clinical_doc_assist

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` in `.env`, then start local retrieval services:

```bash
docker compose up -d
docker compose ps
```

## Run one question

The shortest end-to-end example assumes the GLP-1 corpus is already indexed:

```bash
clinical-doc-ask \
  "What did NCT07424430 aim to evaluate?" \
  --collection clinical_evidence_v1 \
  --limit 5
```

This writes linked retrieval, answer, and pipeline artifacts under `artifacts/`.
If the collection has no adequate evidence, the result is
`insufficient_evidence`.

## Build the evidence collection

Run the stages independently when you need to inspect or debug the corpus:

```bash
clinical-doc-discover \
  "GLP-1 cardiovascular outcomes" \
  --updated-after 2023-01-01 \
  --updated-before 2026-10-21 \
  --limit 20 \
  --output artifacts/discovery/glp1-cardio.json

clinical-doc-corpus build \
  --discovery-run artifacts/discovery/glp1-cardio.json \
  --output artifacts/corpus/glp1-pilot

clinical-doc-retrieve index \
  --corpus artifacts/corpus/glp1-pilot \
  --collection clinical_evidence_v1 \
  --replace
```

Search the collection directly:

```bash
clinical-doc-retrieve search \
  "What cardiovascular outcomes were reported for semaglutide?" \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output artifacts/retrieval/semaglutide-cardio.json
```

## Evaluate and present

Evaluate the current pipeline against the checked-in 20-case suite:

```bash
clinical-doc-eval run \
  --cases evaluation/cases/glp1-eval-v1.json \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output-dir artifacts/evaluations
```

Render a saved pipeline:

```bash
clinical-doc-present \
  --pipeline artifacts/pipelines/pipeline-001.json \
  --case-id glp1-001 \
  --evaluation artifacts/evaluations/evaluation-verdicts.json
```

See the [usage guide](docs/usage.md) for saved evaluation, comparison, review, and
full command options.

## Test

```bash
python -m pytest -o addopts= -q
python -m ruff check .
```

Run Docker integration tests when TEI and Qdrant are active:

```bash
RUN_DOCKER_INTEGRATION=1 python -m pytest -o addopts= -q tests/integration
```

## Repository map

```text
src/clinical_doc_assist/
  research/       public discovery and screening
  corpus/         normalization and deterministic chunking
  retrieval/      TEI embeddings and Qdrant search
  answering/      grounded agent and citation validation
  orchestration/  linked question-to-answer pipeline
  evaluation/     metrics, verdicts, comparison, and presentation

specs/            approved feature specifications, plans, and tasks
tests/            offline unit/contract tests and env-gated Docker integration tests
evaluation/       fixed evaluation case set
docs/             maintained architecture, usage, technology, and acceptance docs
artifacts/        ignored local stage outputs
```

## Current limitations

- The current source implementation uses ClinicalTrials.gov records rather than
  arbitrary PDF/protocol ingestion.
- Retrieval coverage on the first 20-case baseline is limited; see the
  [baseline report](docs/evaluation-baseline.md).
- Key-point matching is a deterministic text proxy, not semantic proof.
- Readability review was AI-assisted rather than independently human-reviewed.
- Multi-source and conflicting-evidence presentation cases are not yet covered.
- No API, CI pipeline, dashboard, reranker, OCR, or production monitoring exists.

## Spec-driven development

Project behavior is governed by
[`.specify/memory/constitution.md`](.specify/memory/constitution.md):

1. Review and update the relevant specification.
2. Obtain approval for the specification.
3. Generate and approve the plan.
4. Generate and approve tasks.
5. Implement only after approval.
6. Keep tests, artifacts, and changelog entries traceable.

Ingestion, question answering, and evaluation remain separately controllable by
design.
