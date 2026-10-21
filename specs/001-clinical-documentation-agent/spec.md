# Feature Specification: Public Clinical Research Q&A Practice Baseline

**Feature Branch**: `master (baseline snapshot)`

**Created**: 2026-10-21

**Status**: Delivered baseline; implemented through feature 007

**Input**: A small practice project that ingests publicly available clinical
research documents, answers questions using retrieved evidence, and evaluates
answer quality with a reproducible test set.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest Public Clinical Research (Priority: P1)

A user adds a small set of publicly available clinical research documents and
confirms which sources are ready to answer questions.

**Why this priority**: The project needs a known, public evidence collection
before it can answer or evaluate anything.

**Independent Test**: Add a small set of public documents, then inspect the
list of sources accepted for question answering.

**Acceptance Scenarios**:

1. **Given** a publicly available clinical research document, **When** the user
   ingests it, **Then** the system reports that it is available as a source.
2. **Given** an unsupported or unreadable document, **When** ingestion is
   attempted, **Then** the system reports the problem without claiming the
   document is available.

---

### User Story 2 - Answer from Retrieved Evidence (Priority: P2)

A user asks a question about the ingested research, receives an answer grounded
in relevant evidence, and can identify the supporting source material.

**Why this priority**: Evidence-based question answering is the central use of
the ingested documents.

**Independent Test**: Ask a question supported by the corpus and verify that the
answer cites supporting evidence; ask an unsupported question and verify that the
system states the evidence is insufficient.

**Acceptance Scenarios**:

1. **Given** relevant evidence exists, **When** the user asks a question,
   **Then** the answer uses that evidence and identifies its source.
2. **Given** no adequate evidence exists, **When** the user asks a question,
   **Then** the system states that it cannot answer from the available evidence.

---

### User Story 3 - Reproduce Answer Evaluation (Priority: P3)

A user evaluates answers against a fixed test set and reruns the same evaluation
to compare answer quality.

**Why this priority**: The project must demonstrate quality in a repeatable way
without adding broader product features.

**Independent Test**: Run the fixed test set twice with unchanged inputs and
verify that both runs produce comparable per-case and aggregate results.

**Acceptance Scenarios**:

1. **Given** a fixed test set, **When** evaluation runs, **Then** the system
   reports per-case and aggregate quality results.
2. **Given** unchanged documents, questions, and test-set version, **When**
   evaluation runs again, **Then** the results can be compared reproducibly.

### Edge Cases

- The corpus contains no relevant evidence for a question.
- Ingested sources contain duplicate or conflicting evidence.
- A document is unsupported, incomplete, or unreadable.
- A test case is malformed or cannot produce an answer.
- Documents, questions, or test-set contents change between evaluation runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST ingest only publicly available clinical research
  documents.
- **FR-002**: The system MUST show which documents are available as evidence
  sources.
- **FR-003**: Users MUST be able to ask questions about the ingested documents.
- **FR-004**: Answers MUST be grounded in retrieved evidence.
- **FR-005**: Answers MUST identify the supporting source material.
- **FR-006**: The system MUST state when the available evidence is insufficient.
- **FR-007**: The system MUST evaluate answers using a fixed, reproducible test
  set.
- **FR-008**: Evaluation MUST report per-case and aggregate quality results.
- **FR-009**: Ingestion, question answering, and evaluation MUST be independently
  runnable and inspectable.
- **FR-010**: Stage failures MUST be reported clearly and MUST NOT be presented as
  successful results.

### Key Entities

- **Research Document**: A publicly available clinical research source.
- **Question**: A user request answered from the ingested documents.
- **Evidence Answer**: A response connected to supporting source material.
- **Evaluation Case**: A fixed question-and-expected-quality case in the test set.
- **Evaluation Result**: Per-case and aggregate quality information for a run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can ingest a small public corpus and see every accepted
  source.
- **SC-002**: Every answered question identifies at least one supporting source,
  and unsupported questions return an insufficient-evidence response.
- **SC-003**: A fixed test set produces per-case and aggregate quality results in
  one evaluation run.
- **SC-004**: Two runs with unchanged inputs and test-set version produce
  comparable result artifacts.
- **SC-005**: A user can stop after ingestion, question answering, or evaluation
  and inspect that stage's output before continuing.

## Assumptions

- This is a small practice project, not a production or clinical-use system.
- Publicly available clinical research documents are the only input data.
- The corpus and test set remain small enough for a single user to inspect.
- The delivered architecture, artifacts, commands, and limitations are maintained
  in [the architecture brief](../../docs/architecture.md).
