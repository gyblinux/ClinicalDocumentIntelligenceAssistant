# Implementation Plan: Evidence Embedding and Vector Retrieval

**Branch**: `004-evidence-vector-retrieval` | **Date**: 2026-10-21 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/004-evidence-vector-retrieval/spec.md`

## Summary

Add a local retrieval stage that validates a feature 003 corpus, embeds chunks
through a TEI Docker service, stores vectors and provenance in Qdrant, and returns
ranked evidence chunks for a question. The Python application remains on the host
and talks to two localhost services.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing `httpx`; add `qdrant-client`; use no
PyTorch/Transformers dependency

**Embedding Service**: Hugging Face TEI CPU Docker image
`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`

**Embedding Model**: `BAAI/bge-small-en-v1.5`, 384 dimensions

**Vector Store**: Qdrant Docker image `qdrant/qdrant:v1.19.2`

**Storage**: Qdrant named volume plus local JSON index and retrieval manifests

**Testing**: `pytest` with fake TEI and vector-store clients; Docker smoke test
is opt-in

**Target Platform**: Host Python CLI on Windows, Linux containers through Docker
Desktop/WSL2

**Project Type**: Single Python package with a `clinical-doc-retrieve` CLI

**Performance Goals**: Index the current 208-chunk corpus in small batches and
return five nearest chunks per query

**Constraints**: Services bind to localhost only; no answer generation, reranker,
hybrid search, or multi-agent work

**Scale/Scope**: One local corpus, one collection, one user, and a small curated
evaluation set

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Public evidence only**: Indexed chunks originate from the approved feature 003
  corpus and retain public source provenance.
- **Evidence-grounded answers**: Retrieval returns exact chunk text and source
  links; answer generation remains outside this feature.
- **Reproducible evaluation**: Model, dimension, collection, corpus build, point
  count, query, limit, and scores are recorded.
- **Independent stages**: Corpus construction, indexing, retrieval, answering, and
  evaluation remain separate commands.
- **Small scope**: Two local containers, one model, one collection, and one CLI;
  no application container or vector-store abstraction is introduced.

No constitutional violations or exceptions are required.

## Project Structure

### Documentation

```text
specs/004-evidence-vector-retrieval/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- cli.md
|   |-- services.md
|   `-- artifacts.md
`-- checklists/
    `-- requirements.md
```

### Source Code

```text
compose.yml
.env.example

src/clinical_doc_assist/retrieval/
|-- __init__.py
|-- models.py          # Config, corpus, index, query, and result records
|-- corpus.py          # Feature 003 corpus and manifest validation
|-- tei.py             # TEI health, info, and batch embedding client
|-- qdrant.py          # Collection validation, point IDs, upsert, and search
|-- service.py         # Index and retrieval orchestration
`-- cli.py             # clinical-doc-retrieve index/search

tests/
|-- fixtures/retrieval/
|-- test_retrieval_models.py
|-- test_retrieval_corpus.py
|-- test_retrieval_tei.py
|-- test_retrieval_qdrant.py
|-- test_retrieval_service.py
|-- test_retrieval_cli.py
`-- integration/test_retrieval_stack.py
```

**Structure Decision**: Keep the feature isolated in a `retrieval/` package. The
TEI client uses existing HTTP support; Qdrant uses its official Python client.

## Design

### Corpus Preflight

1. Read `manifest.json`, `documents.jsonl`, and `chunks.jsonl`.
2. Require corpus schema `1.0`.
3. Require `completed` or `partial` status and `chunk_count > 0`.
4. Require every chunk to reference an existing document.
5. Reject malformed or empty corpora before contacting Docker services.

### TEI Client

- Check `GET /health`.
- Read `GET /info` for model identity and input constraints.
- Generate embeddings with `POST /embed` and `{"inputs": [...]}`.
- Batch at most 32 inputs per request.
- Require a consistent 384-dimensional vector per configured model.
- Report unavailable, invalid, or dimension-mismatched responses concisely.

### Qdrant Index

- Connect through `qdrant-client`.
- Default collection name: `clinical_evidence_v1`.
- Use Cosine distance.
- Create the collection when absent.
- If present, verify vector dimension and distance.
- Without `--replace`, use deterministic upserts and allow idempotent reindexing.
- With `--replace`, delete and recreate the collection before indexing.
- Derive point IDs with UUID5 from `chunk_id` so unchanged chunks are idempotent.
- Upsert payloads containing all chunk provenance.

### Commands

```text
clinical-doc-retrieve index \
  --corpus artifacts/corpus/glp1-pilot-v2 \
  --collection clinical_evidence_v1 \
  [--replace]

clinical-doc-retrieve search "QUESTION" \
  --collection clinical_evidence_v1 \
  [--limit 5] \
  [--output artifacts/retrieval/<run-id>.json]
```

### Output

- Index prints and optionally writes an index manifest under
  `artifacts/index-runs/`.
- Search prints one retrieval-run JSON object and optionally writes it.
- Search output contains ranked chunk text, score, and source provenance.
- No answer is generated.

### Docker Services

Provide a root `compose.yml` with:

- TEI CPU image, host port `127.0.0.1:8080`, named model volume.
- Qdrant `v1.19.2`, host port `127.0.0.1:6333`, named storage volume.

The host application uses `127.0.0.1`. Future application containers would use
the Compose service names instead.

### Testing Strategy

- Corpus manifest and chunk validation.
- TEI request, batching, response, and dimension checks.
- UUID5 point identity and Qdrant collection guards.
- Index orchestration with fake clients.
- Retrieval ordering, scores, provenance, and no-results behavior.
- CLI JSON, optional output files, and concise failure exit codes.
- Opt-in live integration test only when Docker services are available.

## Complexity Tracking

No violations. The only added framework is the Qdrant client; embedding and
vector scoring remain outside the Python process in purpose-built local services.
