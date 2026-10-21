# Feature Specification: Evidence-Grounded Answers

**Feature Branch**: `005-evidence-grounded-answers`

**Created**: 2026-10-21

**Status**: Implemented and validated 2026-10-21

**Input**: Convert one saved feature 004 retrieval run into one answer using only
its recorded question and retrieved evidence, provide traceable citations, abstain
when evidence is insufficient, and optionally use one restricted trial-metadata
tool for an NCT identifier already present in that evidence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer from Retrieved Evidence (Priority: P1)

A user first creates a retrieval run in feature 004. The user then runs feature
005 against that saved run. The question recorded by feature 004 becomes the
question for this single-turn answer, and the system returns a concise answer
grounded only in the saved evidence.

**Why this priority**: This completes the primary question-answering behavior.

**Independent Test**: Use a completed retrieval run with known passages and
verify that the answer uses only those passages and that every factual claim cites
a valid retrieved evidence identifier.

**Acceptance Scenarios**:

1. **Given** retrieved evidence contains enough information, **When** the user
   runs the answer workflow, **Then** the answer contains only supported claims
   and every citation resolves to a retrieved evidence item.
2. **Given** retrieved evidence contains conflicting findings, **When** the system
   answers, **Then** it describes the conflict instead of choosing a fact without
   evidence.
3. **Given** a saved retrieval run and no live retrieval service, **When** the
   answer workflow runs, **Then** it uses the saved evidence without re-querying
   the retrieval service.

---

### User Story 2 - Abstain When Evidence Is Insufficient (Priority: P1)

When the retrieved passages do not support an answer, the system explicitly
abstains and explains why.

**Why this priority**: An unsupported answer is worse than a clear refusal.

**Independent Test**: Use empty retrieval and irrelevant retrieval cases and
verify an `insufficient_evidence` result with no generated factual answer.

**Acceptance Scenarios**:

1. **Given** no evidence results, **When** the workflow runs, **Then** the system
   abstains without calling the answer model.
2. **Given** results do not contain enough evidence, **When** the answer model
   responds, **Then** the system returns an explicit insufficient-evidence result.
3. **Given** malformed retrieval input, **When** the workflow starts, **Then** the
   workflow reports an input failure instead of presenting an answer.

---

### User Story 3 - Use Trial Metadata as a Supporting Tool (Priority: P2)

The answer workflow can look up structured metadata for an already retrieved NCT
identifier when the metadata is necessary to interpret the evidence.

**Why this priority**: One controlled tool adds useful context without broad
agent capabilities.

**Independent Test**: Ask a question that requires study status or intervention
metadata and verify that the lookup is recorded and its result remains tied to an
accepted trial.

**Acceptance Scenarios**:

1. **Given** a retrieved trial identifier, **When** metadata is required, **Then**
   the workflow may call the structured trial lookup tool and any resulting
   factual claim must cite that metadata result.
2. **Given** the tool fails, **When** the workflow answers, **Then** it either
   answers from available evidence or explicitly states the metadata limitation.
3. **Given** an NCT identifier absent from retrieved evidence, **When** a lookup
   is requested, **Then** the tool rejects the request.

---

### User Story 4 - Persist and Inspect the Answer Record (Priority: P2)

A user receives a persisted answer record for each run. The record contains the
question inherited from retrieval, input evidence, answer claims, citations, tool
use, model configuration, timing, and failures, so the user can inspect it after
the workflow completes.

**Why this priority**: A durable answer record keeps the stage reproducible and
reviewable instead of exposing only transient console output.

The answer record is also the feature 005 handoff to feature 006. Feature 006
combines it with the corresponding feature 004 retrieval artifact and a fixed
evaluation case. The answer record supplies answer-side outcomes; the retrieval
artifact remains the source for retrieval ranking and retrieval-stage errors.

**Independent Test**: Run a supported and an unsupported question and verify both
persisted answer records contain complete status and provenance.

**Acceptance Scenarios**:

1. **Given** a completed answer run, **When** the persisted record is inspected, **Then**
   it contains all accepted citations and model usage metadata.
2. **Given** a failure or abstention, **When** the persisted record is inspected, **Then**
   the outcome explains the reason without presenting an unsupported answer.
3. **Given** an answered run, **When** a citation is selected, **Then** it preserves
   the canonical public source provenance from retrieval or the recorded metadata
   lookup, not model-authored provenance.
4. **Given** a persisted answer record and its corresponding retrieval artifact,
   **When** feature 006 evaluation begins, **Then** it can associate the case with
   both stages and score answer-side outcomes without rerunning the answer stage.

## Scope Boundaries

- This feature handles one saved retrieval run and one question per run.
- Conversation history, follow-up-question memory, and chat interfaces are outside
  this feature.
- Retrieval, query rewriting, web browsing, and source re-screening are outside
  this feature.
- Clinical advice, diagnosis, treatment recommendations, and clinical
  decision-making are prohibited.
- Evaluation scoring, a web API, production observability, and multi-agent
  orchestration remain outside this feature.

### Edge Cases

- Retrieval run is malformed, has no recorded question, or lacks required source
  provenance.
- Retrieval run contains no results.
- Retrieval results exist but do not support the recorded question.
- The model returns a citation not present in retrieval input.
- The model returns a citation to metadata that was not successfully retrieved.
- The answer contains unsupported facts.
- Retrieved evidence conflicts.
- The model returns malformed output or no factual claims with citations.
- The metadata tool returns an error.
- The model exceeds its bounded step or output limit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow MUST consume exactly one valid saved retrieval run and
  use its recorded query as the question.
- **FR-002**: The workflow MUST reject a retrieval run missing its question or
  containing an evidence item without content, an identifier, or canonical source
  provenance before invoking the answer model.
- **FR-003**: Factual answer claims MUST be limited to information supported by
  retrieved evidence or a successful structured metadata lookup.
- **FR-004**: Every accepted factual claim MUST be associated with one or more
  citations to retrieved evidence or a successful metadata lookup.
- **FR-005**: The system MUST reject missing, malformed, or unknown citations
  rather than accepting the answer.
- **FR-006**: Citation provenance MUST come from retrieval input or the recorded
  tool result; model-authored URLs and metadata MUST NOT be trusted.
- **FR-007**: The system MUST return an explicit insufficient-evidence result when
  evidence is absent or does not adequately support the question.
- **FR-008**: The system MUST abstain without invoking the answer model when the
  retrieval run contains no results.
- **FR-009**: The workflow MUST provide one structured trial-metadata lookup tool
  restricted to NCT identifiers already present in the retrieval evidence.
- **FR-010**: Tool calls, failures, requested NCT identifiers, and returned
  metadata identifiers MUST be recorded.
- **FR-011**: The answer run MUST record the question, retrieval ID, evidence IDs,
  model, prompt version, tool usage, latency, token usage when available,
  citations, status, and errors.
- **FR-012**: The workflow MUST NOT perform retrieval, web browsing, query
  rewriting, or conversational memory during answering.
- **FR-013**: The system MUST make clear that the response summarizes research
  documents and is not clinical advice or decision-making.
- **FR-014**: The workflow MUST stop before evaluation scoring.
- **FR-015**: The persisted answer record MUST preserve its retrieval identity and
  the answer outcomes needed by feature 006 for citation, faithfulness, refusal,
  latency, and usage scoring.

### Key Entities

- **Retrieval Input**: One saved feature 004 result containing the question,
  retrieval identity, and ranked evidence.
- **Evidence Item**: A retrieved passage with an identifier, text, NCT identifier,
  section, source URL, and content hash.
- **Answer Claim**: One concise factual statement associated with one or more
  citations.
- **Answer Citation**: A validated reference to retrieved evidence or a successful
  metadata lookup, including canonical public provenance.
- **Metadata Lookup**: One recorded request and response for an NCT identifier
  already present in retrieved evidence.
- **Answer Run**: Retrieval identity, question, evidence, claims, citations, tool
  activity, model configuration, usage, timing, status, and errors; its persisted
  record is the answer-stage handoff to evaluation.

## Success Criteria *(mandatory)*

- **SC-001**: Every accepted factual claim resolves to at least one valid retrieved
  evidence or metadata citation.
- **SC-002**: The validation set produces zero citations outside the supplied
  evidence and successful metadata-lookup allowlists.
- **SC-003**: Every empty or insufficient-evidence case produces an explicit
  insufficient-evidence result rather than unsupported factual claims.
- **SC-004**: Every answer artifact permits a reviewer to reconstruct the recorded
  question, input evidence, answer claims, model output, and citations.
- **SC-005**: Every trial metadata lookup is limited to an NCT identifier present
  in the input evidence.
- **SC-006**: No malformed, uncited, or invalidly cited model output is presented
  as an answered result.
- **SC-007**: A saved retrieval run can be processed by the answer workflow without
  a live vector-search service.
- **SC-008**: Every returned answer includes the research-summary disclaimer.
- **SC-009**: Feature 006 can associate every persisted answer record with its
  corresponding retrieval artifact and score answer-side outcomes without
  regenerating that answer.

## Assumptions

- Feature 004 provides schema-versioned retrieval runs with a recorded question,
  evidence text, identifiers, source URLs, and content hashes.
- The input evidence originates from the accepted public corpus established by
  features 002 through 004; feature 005 does not independently re-screen source
  trust.
- Retrieval relevance does not guarantee evidence sufficiency. The answer workflow
  must remain conservative.
- Application code validates citation identity and canonical provenance. It does
  not prove that every claim logically follows from its citation.
- Semantic faithfulness and retrieval quality are measured by feature 006.
- Feature 006 consumes a fixed evaluation case, the corresponding feature 004
  retrieval artifact, and the feature 005 answer record. The answer record alone
  is not treated as a substitute for retrieval rank, score, status, or errors.
- One configured answer model performs answering and optional metadata tool use.
- Live retrieval services are required only to create or refresh a retrieval run,
  not to consume an existing run.
- A web API, conversation memory, and production observability are not part of
  this feature.
