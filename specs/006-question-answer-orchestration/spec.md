# Feature Specification: Question-to-Answer Orchestration

**Feature Branch**: `006-question-answer-orchestration`

**Created**: 2026-10-21

**Status**: Draft - awaiting review

**Input**: Provide a one-question user interface that accepts any question
answerable from the current public clinical corpus, retrieves fresh evidence for
that exact question, invokes the feature 005 answer stage, and persists linked
retrieval, answer, and orchestration records.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a Corpus-Backed Question (Priority: P1)

A user submits one clinical research question. The interface retrieves evidence
for that question from the current public corpus, invokes the evidence-grounded
answering stage, and returns either a cited answer or an explicit
insufficient-evidence response.

**Why this priority**: This is the user-facing workflow that makes features 004
and 005 usable without manually coordinating two stages.

**Independent Test**: Submit a supported question, verify that retrieval receives
the same question text, feature 005 receives the resulting retrieval artifact, and
the user receives a cited answer linked to that retrieval.

**Acceptance Scenarios**:

1. **Given** a non-empty question and available retrieval evidence, **When** the
   user runs the interface, **Then** a fresh retrieval run and answer record are
   produced for that exact question.
2. **Given** a new question in a later invocation, **When** the interface runs,
   **Then** it performs new retrieval and does not reuse evidence selected for a
   previous question.
3. **Given** no supporting evidence, **When** retrieval completes without results,
   **Then** the user receives an explicit insufficient-evidence outcome.

---

### User Story 2 - Inspect the Linked Pipeline Record (Priority: P1)

After one question completes, the user can inspect a pipeline record that links
the question, retrieval outcome, answer record, statuses, timing, and errors.

**Why this priority**: The interface must preserve the independently controlled
stages required by the project constitution.

**Independent Test**: Run one question and verify that the pipeline record
identifies exactly one retrieval artifact and one answer record whose question and
retrieval identifiers agree.

**Acceptance Scenarios**:

1. **Given** a completed answer or abstention, **When** the pipeline record is
   inspected, **Then** it links the originating question to both stage artifacts.
2. **Given** a stage failure, **When** the pipeline record is inspected, **Then**
   it identifies the failed stage and preserves any artifact produced before the
   failure.

---

### User Story 3 - Fail Clearly When the Pipeline Cannot Run (Priority: P2)

The user receives a clear failure when required retrieval or answer services are
unavailable or produce invalid output.

**Why this priority**: The interface must never convert infrastructure failure or
invalid input into an unsupported answer.

**Independent Test**: Simulate unavailable retrieval, no results, retrieval
failure, and answer failure; verify each outcome is distinct and inspectable.

**Acceptance Scenarios**:

1. **Given** required retrieval services are unavailable, **When** the interface
   runs, **Then** it reports retrieval failure without invoking answering.
2. **Given** retrieval succeeds but answering fails, **When** the interface
   completes, **Then** the retrieval artifact and failed answer record remain
   available for review.
3. **Given** an empty question, **When** the interface starts, **Then** it rejects
   the request before retrieval or model use.

## Scope Boundaries

- The interface handles one question per invocation.
- Each question uses a fresh retrieval run against the configured public corpus.
- Feature 004 owns retrieval and feature 005 owns answer generation, citation
  validation, and abstention.
- Conversation history, follow-up-question memory, and multi-turn chat sessions
  are outside this feature.
- Query rewriting, broad web browsing, and source re-screening are outside this
  feature.
- Public documents only; private patient records and clinical decision-making are
  prohibited.
- Evaluation scoring, a web API, production monitoring, and multi-agent
  orchestration remain outside this feature.

### Edge Cases

- Question is empty or whitespace-only.
- Retrieval services, embedding model, or vector index are unavailable.
- The selected collection is empty or returns no results.
- Retrieval returns malformed or unusable evidence.
- Answer generation fails after retrieval succeeds.
- Answer citations fail validation.
- Two invocations ask different questions.
- An output path or generated record identifier collides with an existing file.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The interface MUST accept exactly one non-empty research question per
  invocation.
- **FR-002**: The interface MUST use the submitted question text as the feature 004
  retrieval query without silently substituting a different question.
- **FR-003**: The interface MUST perform a fresh retrieval run for every question
  invocation.
- **FR-004**: The interface MUST use the configured public feature 003 corpus,
  feature 004 embedding service, and vector collection; it MUST NOT browse or
  retrieve from unrelated sources.
- **FR-005**: The interface MUST invoke feature 005 with the retrieval artifact
  produced for the same question, preserving its citation validation,
  abstention, and one allowlisted trial-metadata tool.
- **FR-006**: The interface MUST preserve both the feature 004 retrieval artifact
  and the feature 005 answer record.
- **FR-007**: The interface MUST persist one pipeline record linking the question,
  retrieval ID and artifact, answer ID and artifact, stage statuses, timing, and
  errors.
- **FR-008**: When retrieval produces no results, the interface MUST return the
  feature 005 insufficient-evidence outcome without invoking the answer model.
- **FR-009**: When retrieval cannot run or fails, the interface MUST report a
  retrieval-stage failure and MUST NOT fabricate or reuse an answer.
- **FR-010**: When retrieval succeeds but answering fails, the interface MUST
  preserve the retrieval artifact and failed answer record for inspection.
- **FR-011**: Answers returned through the interface MUST retain feature 005
  citation validation, source provenance, and the research-only disclaimer.
- **FR-012**: The interface MUST NOT carry conversation history or reuse evidence
  from a previous question unless a later feature explicitly adds that behavior.
- **FR-013**: The interface MUST stop before evaluation scoring.

### Key Entities

- **Question Request**: One question, selected public collection, and retrieval
  limit.
- **Retrieval Artifact**: The feature 004 evidence result produced specifically for
  the question.
- **Answer Record**: The feature 005 answer, abstention, or failure record produced
  from that retrieval artifact.
- **Pipeline Record**: One inspectable record linking the question, retrieval and
  answer artifacts, stage statuses, timing, and errors.

## Success Criteria *(mandatory)*

- **SC-001**: Every valid question produces a cited answer, an explicit
  insufficient-evidence outcome, or a clearly identified stage failure.
- **SC-002**: Every invocation produces exactly one question-specific retrieval
  artifact and records whether an answer record was produced.
- **SC-003**: Every successful or abstained answer links to the retrieval artifact
  created for the same question.
- **SC-004**: No-results retrieval does not invoke the answer model.
- **SC-005**: Different questions cannot silently share one retrieval result
  through the orchestration interface.
- **SC-006**: Retrieval and answer failures identify the failed stage and preserve
  available artifacts.
- **SC-007**: A reviewer can reconstruct the question and trace both stage outputs
  from the pipeline record.
- **SC-008**: A feature 007 evaluation can consume one linked pipeline record per
  fixed evaluation case without manually coordinating the two lower-level stages.

## Assumptions

- Features 004 and 005 are available and retain their current artifact contracts.
- The user's question is used directly as the retrieval query; intelligent query
  rewriting is deferred.
- Retrieval is always invoked by the orchestration layer before answering; the
  model does not decide whether to retrieve.
- Docker-backed TEI and Qdrant services are available when retrieval runs.
- The answer model and public trial metadata service are available for supported
  answer generation.
- The initial interface is one-shot and local; it does not preserve chat history.
- The public corpus, collection, retrieval settings, and model configuration are
  recorded for reproducibility.
- Feature 007 consumes the linked pipeline record for evaluation while retaining
  access to the underlying retrieval and answer artifacts.
