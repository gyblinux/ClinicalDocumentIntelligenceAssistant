# Clinical Doc Assist

Clinical Doc Assist is a small, early-stage practice project for:

1. Ingesting publicly available clinical research documents.
2. Answering questions from retrieved evidence.
3. Evaluating answer quality with a reproducible test set.

This is a learning project, not a clinical-use system. Architecture and
implementation decisions are intentionally deferred.

## Current State

The repository has a Spec Kit baseline and a provisional code scaffold. The
specification defines the project scope only; the existing source code is not an
approved architecture.

A high-level single-agent pipeline has been proposed and reviewed in the
[architecture review](specs/001-clinical-documentation-agent/architecture-review.md).
Multi-agent orchestration and operational infrastructure are deferred. This is
not yet an approved plan.

The first feature is
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
