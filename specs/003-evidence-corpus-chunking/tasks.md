---
description: "Implementation tasks for evidence corpus assembly and chunking"
---

# Tasks: Evidence Corpus Assembly and Chunking

**Input**: Design documents from `specs/003-evidence-corpus-chunking/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), and [contracts/](contracts/)

**Tests**: Included because deterministic artifacts, stable identity, and offline
verification are constitutional requirements.

## Phase 1: Setup

**Purpose**: Add the new stage without changing feature 002 behavior.

- [X] T001 Add the `clinical-doc-corpus` script entry point in `pyproject.toml`
- [X] T002 Create `src/clinical_doc_assist/corpus/__init__.py`, `src/clinical_doc_assist/corpus/models.py`, `src/clinical_doc_assist/corpus/artifacts.py`, `src/clinical_doc_assist/corpus/normalize.py`, `src/clinical_doc_assist/corpus/chunking.py`, `src/clinical_doc_assist/corpus/builder.py`, `src/clinical_doc_assist/corpus/cli.py`, and corresponding test files under `tests/`

---

## Phase 2: Foundational

**Purpose**: Shared records, discovery-artifact validation, and detailed source retrieval.

- [X] T003 [P] Write serialization and validation tests for `DiscoveryInput`, `EvidenceDocument`, `DocumentSection`, `EvidenceChunk`, `SourceFailure`, and `BuildManifest` in `tests/test_corpus_models.py`
- [X] T004 Implement typed corpus records and JSON serialization in `src/clinical_doc_assist/corpus/models.py`; enforce corpus schema `1.0`, valid chunk settings, and exclusive `end_char` offsets
- [X] T005 [P] Write discovery artifact tests for schema/run-ID validation, accepted-only extraction, duplicate identifiers across runs, malformed inputs, and atomic corpus manifest writing in `tests/test_corpus_artifacts.py`
- [X] T006 Implement discovery artifact loading and corpus artifact writing in `src/clinical_doc_assist/corpus/artifacts.py`
- [X] T007 [P] Extend `tests/test_clinical_trials.py` with mocked detailed-study retrieval, success normalization input, HTTP failure, and identifier mismatch cases
- [X] T008 Add `ClinicalTrialsSource.fetch_study(nct_id)` using `GET https://clinicaltrials.gov/api/v2/studies/{nctId}` in `src/clinical_doc_assist/research/clinical_trials.py`

**Checkpoint**: Shared records, validated inputs, artifact I/O, and detailed source retrieval are ready.

---

## Phase 3: User Story 1 - Materialize Accepted Evidence Sources (Priority: P1)

**Goal**: Turn unique accepted identifiers from multiple discovery artifacts into
evidence-document source records or explicit failures.

**Independent Test**: Build from two discovery fixtures with an overlapping NCT ID
and one source failure; verify one retrieval for the duplicate, all contributing
run IDs retained, and the failure isolated from successful sources.

### Tests

- [X] T009 [P] [US1] Write builder tests for accepted-only selection, multi-artifact deduplication, identity mismatch, source failure isolation, and `completed` versus `partial` outcomes in `tests/test_corpus_builder.py`

### Implementation

- [X] T010 [US1] Implement deterministic discovery-input aggregation and NCT deduplication in `src/clinical_doc_assist/corpus/builder.py`
- [X] T011 [US1] Implement detailed-source retrieval and accepted-identity verification in `src/clinical_doc_assist/corpus/builder.py`
- [X] T012 [US1] Implement per-source success/failure records and `completed`, `partial`, `no_documents`, or `failed` resolution in `src/clinical_doc_assist/corpus/builder.py`

**Checkpoint**: Unique accepted sources are materialized independently of normalization.

---

## Phase 4: User Story 2 - Normalize Useful Evidence Sections (Priority: P1)

**Goal**: Convert detailed ClinicalTrials.gov records into stable, inspectable
text sections without inventing missing content.

**Independent Test**: Normalize a trimmed real study response with complete and
missing optional modules; verify section text, unavailable-section reporting,
source metadata, and unchanged input stability.

### Tests

- [X] T013 [P] [US2] Write normalization tests for title, status/dates, summary, conditions, interventions, eligibility, outcomes, sponsor, missing sections, and malformed optional fields using `tests/fixtures/corpus/` in `tests/test_corpus_normalize.py`

### Implementation

- [X] T014 [US2] Implement normalized evidence documents and section extraction in `src/clinical_doc_assist/corpus/normalize.py`
- [X] T015 [US2] Add deterministic content hashing and unavailable-section tracking in `src/clinical_doc_assist/corpus/normalize.py`
- [X] T016 [US2] Integrate normalized documents into successful builder outcomes in `src/clinical_doc_assist/corpus/builder.py`

**Checkpoint**: Successful sources produce inspectable sectioned evidence documents.

---

## Phase 5: User Story 3 - Produce Deterministic Citation-Ready Chunks (Priority: P2)

**Goal**: Produce stable chunks that remain within one document section and retain
source provenance.

**Independent Test**: Chunk short, paragraph-heavy, sentence-heavy, Unicode, and
overlong fixture sections; verify size, overlap, offsets, stable IDs, and no
cross-section content.

### Tests

- [X] T017 [P] [US3] Write chunking tests for short and long sections, paragraph and sentence boundaries, overlap limits, character offsets, Unicode, content hashes, and stable chunk IDs in `tests/test_corpus_chunking.py`

### Implementation

- [X] T018 [US3] Implement deterministic section, paragraph, and sentence chunking in `src/clinical_doc_assist/corpus/chunking.py` with a default maximum of 1,200 characters and overlap of no more than 150 characters
- [X] T019 [US3] Integrate chunk generation and stable chunk identity into `src/clinical_doc_assist/corpus/builder.py`

**Checkpoint**: The builder can produce citation-ready evidence chunks.

---

## Phase 6: User Story 4 - Inspect and Rerun the Corpus Build (Priority: P2)

**Goal**: Emit reproducible local artifacts and expose stage outcomes through a
small CLI.

**Independent Test**: Run the CLI against fixture artifacts, inspect every output
file, rerun unchanged inputs, and invoke `no_documents`, `partial`, `failed`, and
unsafe-output cases.

### Tests

- [X] T020 [P] [US4] Write manifest and CLI contract tests for output layout, counts, duplicate provenance, stable rebuilds, `no_documents`, `partial`, `failed`, exit codes, and unsafe output paths in `tests/test_corpus_cli.py`

### Implementation

- [X] T021 [US4] Implement complete manifest assembly and build-ID generation in `src/clinical_doc_assist/corpus/builder.py`
- [X] T022 [US4] Implement temporary-directory build and atomic final-directory replacement in `src/clinical_doc_assist/corpus/artifacts.py`
- [X] T023 [US4] Implement `clinical-doc-corpus build`, repeatable `--discovery-run`, JSON summary, progress separation, and exit codes in `src/clinical_doc_assist/corpus/cli.py`

**Checkpoint**: Feature 003 is independently runnable, inspectable, and deterministic.

---

## Phase 7: Polish and Verification

- [X] T024 [P] Update `README.md` and `CHANGELOG.md` with the corpus build command, output layout, and stop-before-embedding boundary
- [X] T025 Run `pytest`, `ruff check .`, formatting checks, CLI help, offline quickstart scenarios, and a live build against `artifacts/discovery/*.json`
- [X] T026 Review the implementation against `spec.md` and `plan.md`, confirm no embeddings, vector storage, retrieval, or answering were added, and verify the three local discovery artifacts yield a usable non-empty corpus
- [X] T027 Align chunk overlap starts to word boundaries and guard sentence splitting against common abbreviations in `src/clinical_doc_assist/corpus/chunking.py` with tests in `tests/test_corpus_chunking.py`
- [X] T028 Add one bounded retry for HTTP 429 and transient 5xx source responses with concise structured source failures in `src/clinical_doc_assist/research/clinical_trials.py`, `src/clinical_doc_assist/research/models.py`, and `src/clinical_doc_assist/corpus/models.py`
- [X] T029 Wrap corpus filesystem and directory-publish failures as `CorpusOutputError` in `src/clinical_doc_assist/corpus/artifacts.py` and `src/clinical_doc_assist/corpus/builder.py`, with CLI tests in `tests/test_corpus_cli.py`
- [X] T030 Add regression tests for word boundaries, abbreviations, retry behavior, structured manifest failures, and output-error concision in `tests/`
- [X] T031 Run all checks and rebuild the live corpus into a new output directory to verify zero mid-word chunk starts

---

## Dependencies and Execution Order

- T001-T002 require the approved plan and completed feature 002 artifact contract.
- T003-T008 require setup completion.
- US1 requires T003-T008.
- US2 requires detailed retrieval from US1.
- US3 requires normalized documents from US2.
- US4 requires chunked output from US3.
- T024-T026 require US4.

## Parallel Opportunities

- T003, T005, and T007 use separate test areas and can be written in parallel
  after setup.
- Story test tasks T009, T013, T017, and T020 target separate files and can be
  prepared independently after their prerequisites exist.
- Documentation T024 can proceed once the CLI contract is stable while T025-T026
  run.

## MVP Scope

US1 and US2 form the first usable increment: unique accepted sources become
normalized evidence documents. US3 adds the required chunks, and US4 makes the
stage controllable and reproducible.

## Implementation Strategy

1. Add the package and shared records.
2. Validate discovery inputs and detailed retrieval.
3. Materialize unique source documents.
4. Normalize sections deterministically.
5. Chunk each section with stable provenance.
6. Write the atomic corpus directory and CLI.
7. Validate against fixtures and the three local discovery artifacts.
