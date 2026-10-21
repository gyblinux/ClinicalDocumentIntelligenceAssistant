# Feature Specification: Evidence Embedding and Vector Retrieval

**Feature Branch**: `004-evidence-vector-retrieval`

**Created**: 2026-10-21

**Status**: Draft - baseline scope only

**Input**: Index chunks from feature 003 and return the most relevant evidence
chunks for a user question. Stop before answer generation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Index the Evidence Corpus (Priority: P1)

A user indexes an approved chunk corpus and receives an inspectable index manifest
showing what was indexed and which configuration was used.

**Why this priority**: Retrieval cannot be evaluated until chunks are indexed with
known model and index settings.

**Independent Test**: Index a small corpus and verify that every eligible chunk is
either indexed or reported as a failure.

**Acceptance Scenarios**:

1. **Given** an approved chunk artifact, **When** indexing runs, **Then** the
   system reports the indexed chunk count and index configuration.
2. **Given** an unavailable embedding or vector-store service, **When** indexing
   runs, **Then** the run fails clearly instead of creating an empty success.
3. **Given** a `no_documents` or empty chunk corpus, **When** indexing runs,
   **Then** the system rejects it and does not create an empty index.

---

### User Story 2 - Retrieve Relevant Evidence (Priority: P1)

A user asks a question and receives ranked evidence chunks with source metadata.

**Why this priority**: Relevant, inspectable evidence is the output required by
the later answering stage.

**Independent Test**: Query an indexed fixture corpus and verify that the returned
top results contain chunk text, rank, score, source identifier, and source link.

**Acceptance Scenarios**:

1. **Given** an indexed corpus, **When** a user asks a question, **Then** the
   configured number of evidence chunks is returned in relevance order.
2. **Given** no suitable evidence, **When** retrieval runs, **Then** the user sees
   an explicit no-results outcome.

---

### User Story 3 - Reindex and Compare Runs (Priority: P2)

A user can update the index without duplicating unchanged chunks and can see which
model or corpus version produced the results.

**Why this priority**: Stable indexing makes later retrieval evaluation
reproducible.

**Independent Test**: Run indexing twice with unchanged inputs, then change one
chunk and verify the manifest reports the change without duplicate results.

**Acceptance Scenarios**:

1. **Given** unchanged chunks, **When** indexing reruns, **Then** the system does
   not create duplicate indexed evidence.
2. **Given** changed chunks, model settings, or collection settings, **When** the
   index updates, **Then** the manifest records the change.

### Edge Cases

- The chunk corpus is empty.
- Embedding or vector services are unavailable.
- The configured model dimension does not match the index.
- A chunk was removed or changed since the previous build.
- Multiple chunks receive equal scores.
- A query is empty or cannot be embedded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST consume a valid, non-empty chunk artifact from
  feature 003.
- **FR-002**: Every eligible chunk MUST be indexed or reported as a failure.
- **FR-003**: The system MUST use a configured embedding model and persistent
  vector index with recorded versions.
- **FR-004**: Reindexing unchanged chunks MUST NOT create duplicate points.
- **FR-005**: Users MUST be able to submit a natural-language question.
- **FR-006**: Retrieval MUST return a configurable number of ranked evidence
  chunks.
- **FR-007**: Every result MUST include chunk text, score, source identifier,
  section, and source link.
- **FR-008**: The system MUST report when no evidence results are available.
- **FR-009**: The system MUST report service, dimension, and configuration
  failures clearly.
- **FR-010**: The index and query runs MUST preserve the configuration needed to
  compare results.
- **FR-011**: Retrieval MUST stop before LLM answer generation.
- **FR-012**: The system MUST reject empty, `no_documents`, malformed, or
  zero-chunk corpora without creating an index.

### Key Entities

- **Chunk Corpus**: The approved chunk artifact from feature 003.
- **Index Manifest**: Model, vector dimension, collection, source corpus, counts,
  changes, and errors for one index build.
- **Retrieval Query**: A user question and requested result count.
- **Retrieval Result**: Ranked chunk evidence with score and provenance.
- **Retrieval Run**: Query, configuration, results, errors, and timing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every eligible input chunk is indexed or listed as a failure.
- **SC-002**: Every returned result contains the full provenance required for a
  later citation.
- **SC-003**: Reindexing unchanged chunks does not increase the number of indexed
  evidence points.
- **SC-004**: Changing a chunk, model, or collection setting is visible in the
  index manifest.
- **SC-005**: A user can inspect retrieval results and stop before answer
  generation.
- **SC-006**: Empty or invalid corpora produce no index and a clear rejection.

## Assumptions

- Feature 003 is approved and produces the only accepted chunk input.
- Feature 004 proceeds only when feature 003 reports at least one usable chunk.
- The current architecture direction uses local containerized embedding and a
  free local vector database; exact services and versions are confirmed during
  planning.
- The default result count is five but remains configurable.
- Public data only is used.
- Hybrid search, reranking, answer generation, evaluation metrics, and
  multi-agent behavior are deferred.
- This specification intentionally covers the baseline only; indexing and
  retrieval details will be refined after feature 003 is validated.
