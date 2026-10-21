# Clinical Doc Assist

Clinical Doc Assist is a small, early-stage practice project for:

1. Ingesting publicly available clinical research documents.
2. Answering questions from retrieved evidence.
3. Evaluating answer quality with a reproducible test set.

This is a learning project, not a clinical-use system. The pipeline is delivered
in small, independently reviewable stages.

## Current State

Features 002 through 004 are implemented: public trial discovery, deterministic
corpus chunking, and local vector retrieval with citation-ready provenance.

The high-level single-agent pipeline is reviewed in the
[architecture review](specs/001-clinical-documentation-agent/architecture-review.md).
Multi-agent orchestration and production monitoring remain deferred.

Feature 002 handles
[research document discovery and screening](specs/002-research-doc-discovery/spec.md).
It stops after returning accepted, rejected, and needs-review candidates.

### Discovery prototype

Set `DEEPSEEK_API_KEY`, then run:

```powershell
clinical-doc-discover "GLP-1 cardiovascular outcomes" `
  --updated-after 2023-01-01 `
  --updated-before 2026-10-21 `
  --limit 20 `
  --output artifacts/discovery/glp1-cardio.json
```

The command prints one JSON discovery run. It uses ClinicalTrials.gov as its only
source, records UTC time before searching, and stops before downloading or
ingesting documents. The automated tests use fake model and HTTP responses.

If Windows application-control policy blocks the generated executable, use:

```powershell
python -m clinical_doc_assist.research.cli "GLP-1 cardiovascular outcomes" `
  --updated-after 2023-01-01 `
  --updated-before 2026-10-21 `
  --limit 20 `
  --output artifacts/discovery/glp1-cardio.json
```

### Corpus prototype

Build normalized evidence documents and chunks from one or more discovery
artifacts:

```powershell
python -m clinical_doc_assist.corpus.cli build `
  --discovery-run artifacts/discovery/semaglutide-obesity.json `
  --discovery-run artifacts/discovery/tirzepatide-obesity.json `
  --discovery-run artifacts/discovery/glp1-mace.json `
  --output artifacts/corpus/glp1-pilot
```

The output directory contains `manifest.json`, `documents.jsonl`, and
`chunks.jsonl`. A `partial` status means some detailed ClinicalTrials.gov records
failed; successful documents and failures remain inspectable in the manifest.
The stage performs no LLM calls and stops before embeddings or retrieval.

### Retrieval prototype

Start the local TEI and Qdrant services:

```powershell
docker compose up -d
```

Index the current corpus:

```powershell
clinical-doc-retrieve index `
  --corpus artifacts/corpus/glp1-pilot-v2 `
  --collection clinical_evidence_v1
```

Retrieve evidence chunks:

```powershell
clinical-doc-retrieve search `
  "What cardiovascular outcomes were reported for semaglutide?" `
  --collection clinical_evidence_v1 `
  --limit 5
```

The search returns ranked evidence chunks with source provenance. It does not
generate an answer. The Python environment requires only `qdrant-client`; TEI
keeps PyTorch and Transformers inside its Docker container.

See [retrieval acceptance](docs/retrieval-acceptance.md) for the manual Docker
startup, integration test, indexing, search, and idempotency checks.

### Answer prototype

Generate one answer from a saved retrieval run:

```powershell
./.venv/Scripts/python.exe -m clinical_doc_assist.answering.cli `
  --retrieval-run artifacts/retrieval/semaglutide-cardio.json `
  --output artifacts/answers/semaglutide-cardio-answer.json
```

The command validates the retrieval artifact, sends only its recorded question and
evidence to DeepSeek Flash, validates claim-level citations, and persists one JSON
answer record. It supports explicit `insufficient_evidence` and `failed`
outcomes. Docker-backed retrieval services are not required when consuming an
existing artifact.

The persisted answer record preserves retrieval and answer identifiers, evidence,
citations, tool calls, usage, latency, and errors for orchestration and later
evaluation.
Manual acceptance passed with the retrieval containers stopped.
After reinstalling the editable package, the equivalent entry point is
`clinical-doc-answer`.

### Orchestration prototype

Run one complete question-to-answer workflow:

```powershell
./.venv/Scripts/python.exe -m clinical_doc_assist.orchestration.cli `
  "What did NCT07424430 aim to evaluate?" `
  --collection clinical_evidence_v1 `
  --limit 5
```

Docker-backed TEI and Qdrant must be running. The command performs fresh
retrieval for the submitted question, invokes the answering stage, and writes
linked records under `artifacts/retrieval/`, `artifacts/answers/`, and
`artifacts/pipelines/`.

After reinstalling the editable package, the equivalent entry point is
`clinical-doc-ask`.

### Evaluation scope

Feature 007 is implemented:

- [Reproducible RAG evaluation](specs/007-rag-evaluation/spec.md)

Feature 007 evaluates linked feature 006 pipeline records while keeping retrieval
and answer metrics attributable to separate stages. Evaluation is offline and
read-only; it cannot retract an answer already returned to a user. It also renders
a deterministic, human-readable answer view with source references and versioned
quality checks, without presenting a misleading per-answer trust percentage.

### Evaluation and presentation prototype

Feature 007 now provides:

- `clinical-doc-eval run` for saved or generated feature 006 pipeline records
- `clinical-doc-eval compare` for one-variable comparisons
- `clinical-doc-eval review` for persisted human readability reviews
- `clinical-doc-present` for deterministic plain-text answer views

The versioned pilot case set is
[glp1-eval-v1.json](evaluation/cases/glp1-eval-v1.json). The initial live baseline
and its observed limitations are documented in
[evaluation-baseline.md](docs/evaluation-baseline.md).

After reinstalling the editable package, the console commands are available.
During the current checkout they can be run through
`python -m clinical_doc_assist.evaluation.cli`.

## Spec-Driven Development

The project advances through explicit, reviewable gates:

1. Review the [constitution](.specify/memory/constitution.md) and
   [baseline specification](specs/001-clinical-documentation-agent/spec.md).
2. Provide and approve the architecture and implementation direction.
3. Run `$speckit-plan`, then review the plan.
4. Run `$speckit-tasks`, then review the tasks.
5. Run `$speckit-implement` only after approval.

Ingestion, question answering, and evaluation must remain independently
controllable and inspectable at every stage.

See [CHANGELOG.md](CHANGELOG.md) for notable changes.
