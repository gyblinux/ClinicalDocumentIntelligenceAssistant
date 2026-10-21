---
description: "Implementation tasks for evidence embedding and vector retrieval"
---

# Tasks: Evidence Embedding and Vector Retrieval

**Input**: Design documents from `specs/004-evidence-vector-retrieval/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), and [contracts/](contracts/)

**Tests**: Included because offline validation, idempotent indexing, and clear
service failures are constitutional requirements.

## Phase 1: Setup

**Purpose**: Add the local service stack and CLI boundary.

- [X] T001 Add `qdrant-client` and the `clinical-doc-retrieve` script entry point in `pyproject.toml`
- [X] T002 Create `src/clinical_doc_assist/retrieval/__init__.py`, `src/clinical_doc_assist/retrieval/models.py`, `src/clinical_doc_assist/retrieval/corpus.py`, `src/clinical_doc_assist/retrieval/tei.py`, `src/clinical_doc_assist/retrieval/qdrant.py`, `src/clinical_doc_assist/retrieval/service.py`, `src/clinical_doc_assist/retrieval/cli.py`, and corresponding test files under `tests/`
- [X] T003 Create `compose.yml` and extend `.env.example` with pinned TEI `cpu-1.9`, Qdrant `v1.19.2`, `BAAI/bge-small-en-v1.5`, localhost ports, named volumes, and retrieval configuration

---

## Phase 2: Foundational

**Purpose**: Shared configuration, corpus validation, and service adapters.

- [X] T004 [P] Write configuration and artifact-model tests for `RetrievalConfig` defaults, one-to-fifty result limits, index manifests, retrieval runs, and result serialization in `tests/test_retrieval_models.py`
- [X] T005 Implement `RetrievalConfig`, `IndexManifest`, `RetrievalQuery`, `RetrievalResult`, and `RetrievalRun` JSON records in `src/clinical_doc_assist/retrieval/models.py`; enforce retrieval result limits from 1 through 50
- [X] T006 [P] Write corpus tests for valid `completed` and `partial` builds, schema and count mismatches, zero chunks, malformed JSONL, and missing document references in `tests/test_retrieval_corpus.py` using `tests/fixtures/retrieval/`
- [X] T007 Implement feature 003 manifest, document, and chunk validation in `src/clinical_doc_assist/retrieval/corpus.py`
- [X] T008 [P] Write TEI tests for `/health`, `/info`, single and batched `/embed`, model and dimension mismatches, malformed vectors, and concise service failures in `tests/test_retrieval_tei.py`
- [X] T009 Implement the TEI HTTP adapter in `src/clinical_doc_assist/retrieval/tei.py` using existing `httpx`, with a maximum batch size of 32
- [X] T010 [P] Write Qdrant adapter tests for collection creation, dimension/distance validation, deterministic UUID5 point IDs, upsert payloads, replace behavior, and query mapping in `tests/test_retrieval_qdrant.py`
- [X] T011 Implement collection management, deterministic point IDs, upsert, and query points in `src/clinical_doc_assist/retrieval/qdrant.py` using `qdrant-client`, Cosine distance, and payload preservation

**Checkpoint**: Corpus validation and both local service adapters work with fakes.

---

## Phase 3: User Story 1 - Index the Evidence Corpus (Priority: P1)

**Goal**: Validate a corpus, embed all chunks, and write an inspectable index
manifest with idempotent Qdrant points.

**Independent Test**: Index a small fixture corpus through fake TEI and Qdrant
clients and verify every chunk is either upserted or reported as a failure.

### Tests

- [X] T012 [P] [US1] Write index orchestration tests for corpus preflight, batching, point creation, index manifest counts, partial failures, and collection creation in `tests/test_retrieval_service.py`
- [X] T013 [P] [US1] Write `index` CLI contract tests for required arguments, `--replace`, JSON summary, service failures, and exit codes in `tests/test_retrieval_cli.py`

### Implementation

- [X] T014 [US1] Implement `index_corpus` orchestration and local index-manifest output in `src/clinical_doc_assist/retrieval/service.py`
- [X] T015 [US1] Implement the `index` command branch in `src/clinical_doc_assist/retrieval/cli.py` with standard-output JSON and standard-error diagnostics

**Checkpoint**: A valid feature 003 corpus can be indexed completely through fake services.

---

## Phase 4: User Story 2 - Retrieve Relevant Evidence (Priority: P1)

**Goal**: Embed a question, query Qdrant, and return ranked evidence with complete
source provenance.

**Independent Test**: Query a fake indexed fixture and verify rank, score, chunk
text, source metadata, no-results behavior, and optional result persistence.

### Tests

- [X] T016 [P] [US2] Write retrieval-service tests for one and multiple results, rank assignment, score preservation, no-results status, limit enforcement, and malformed payloads in `tests/test_retrieval_service.py`
- [X] T017 [P] [US2] Write `search` CLI contract tests for query validation, JSON output, optional `--output`, and service failures in `tests/test_retrieval_cli.py`

### Implementation

- [X] T018 [US2] Implement `search_evidence` orchestration and `RetrievalRun` assembly in `src/clinical_doc_assist/retrieval/service.py`
- [X] T019 [US2] Implement the `search` command branch and optional retrieval-run artifact in `src/clinical_doc_assist/retrieval/cli.py`

**Checkpoint**: The feature returns inspectable evidence chunks and stops before answering.

---

## Phase 5: User Story 3 - Reindex and Compare Runs (Priority: P2)

**Goal**: Repeated indexing is idempotent, model/collection changes are visible,
and service configuration failures are actionable.

**Independent Test**: Index unchanged fixture chunks twice, then verify the same
point IDs and point count; test dimension mismatch, `--replace`, invalid
configuration, and unavailable TEI/Qdrant errors.

### Tests

- [X] T020 [P] [US3] Write reindex and compatibility tests for stable UUID5 IDs, unchanged point counts, `--replace`, dimension mismatch, and changed model metadata in `tests/test_retrieval_qdrant.py` and `tests/test_retrieval_service.py`
- [X] T021 [P] [US3] Write concise failure tests for unavailable TEI, unavailable Qdrant, invalid configuration, and dimension mismatch in `tests/test_retrieval_tei.py`, `tests/test_retrieval_qdrant.py`, and `tests/test_retrieval_cli.py`

### Implementation

- [X] T022 [US3] Implement idempotent upsert metadata, explicit replace handling, and dimension/distance guards in `src/clinical_doc_assist/retrieval/qdrant.py` and `src/clinical_doc_assist/retrieval/service.py`
- [X] T023 [US3] Implement environment loading, service preflight, model/dimension checks, and concise exit-code mapping in `src/clinical_doc_assist/retrieval/cli.py`

**Checkpoint**: Reindexing and service configuration are controlled and reproducible.

---

## Phase 6: Polish and Verification

- [X] T024 [P] Update `README.md` and `CHANGELOG.md` with index/search commands, Docker services, service URLs, and the stop-before-answer boundary
- [X] T025 [P] Add an opt-in Docker integration test in `tests/integration/test_retrieval_stack.py` that indexes a small fixture corpus and runs one query against TEI and Qdrant
- [X] T026 Run all offline checks, run the opt-in Docker integration test, index `artifacts/corpus/glp1-pilot-v2`, run sample queries, and verify index and retrieval manifests

---

## Dependencies and Execution Order

- T002-T003 require T001.
- T004-T011 require T002 and T003.
- T012-T015 require T004-T011.
- T016-T019 require T011 and at least one indexed test collection.
- T020-T023 require the index and search paths.
- T024-T026 require all implementation tasks.

## Parallel Opportunities

- T004, T006, T008, and T010 use separate fixture/test files.
- US1 tests T012 and T013 can be prepared in parallel.
- US2 tests T016 and T017 can be prepared in parallel.
- US3 tests T020 and T021 can be prepared in parallel.
- Documentation T024 and Docker integration setup T025 can proceed independently
  after the CLI contract is stable.

## MVP Scope

US1 plus US2 forms the minimum executable feature: index a validated corpus and
retrieve ranked evidence. US3 adds reindex and configuration hardening required
for reproducible operation.

## Implementation Strategy

1. Add dependencies, Compose services, and configuration.
2. Validate corpora and implement TEI/Qdrant adapters.
3. Build the index workflow and manifest.
4. Build the search workflow and retrieval artifact.
5. Add idempotent reindex and service compatibility guards.
6. Run offline tests, Docker integration, and manual acceptance against the
   current 208-chunk corpus.
