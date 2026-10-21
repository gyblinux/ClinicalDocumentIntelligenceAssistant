# Feature Specification: Evidence Corpus Assembly and Chunking

**Feature Branch**: `003-evidence-corpus-chunking`

**Created**: 2026-10-21

**Status**: Draft

**Input**: Convert accepted research records from feature 002 into an inspectable
local evidence corpus with normalized sections and deterministic, citation-ready
chunks. Stop before embeddings or vector search.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Materialize Accepted Evidence Sources (Priority: P1)

A user provides one or more completed discovery artifacts. The system combines
their accepted identifiers, removes duplicates, retrieves each detailed public
source record, and creates one evidence document per successful source.

**Why this priority**: Embedding or answering before the evidence documents exist
would provide no reliable basis for retrieval.

**Independent Test**: Use multiple discovery artifacts containing accepted,
rejected, needs-review, and duplicate records. Verify that only unique accepted
records become evidence documents and that source retrieval failures are
reported separately.

**Acceptance Scenarios**:

1. **Given** one or more discovery artifacts with accepted sources, **When** corpus assembly
   starts, **Then** each accepted source produces one evidence document or a
   clearly reported failure.
2. **Given** rejected or needs-review records in the discovery run, **When**
   corpus assembly starts, **Then** those records are not silently included.
3. **Given** the same accepted identifier in multiple artifacts, **When** corpus
   assembly starts, **Then** the source is retrieved once and all contributing
   run identifiers are retained.
4. **Given** artifacts with no accepted records, **When** corpus assembly starts,
   **Then** the run ends with an explicit `no_documents` manifest.

---

### User Story 2 - Normalize Useful Evidence Sections (Priority: P1)

The user can inspect a clean, sectioned representation of each evidence source.
Known information is preserved, missing information is explicit, and no clinical
content is invented.

**Why this priority**: Clean section boundaries produce more meaningful chunks and
more trustworthy citations.

**Independent Test**: Normalize records with complete, partial, duplicate, and
malformed fields and verify that available sections are retained while omissions
are visible.

**Acceptance Scenarios**:

1. **Given** a detailed source record, **When** normalization completes, **Then**
   its title, source identity, dates, status, summary, conditions, interventions,
   eligibility, and outcomes are preserved when present.
2. **Given** an unavailable section, **When** normalization completes, **Then**
   the document records it as unavailable rather than inventing content.

---

### User Story 3 - Produce Deterministic Citation-Ready Chunks (Priority: P2)

The user receives chunks that stay within one document section and retain enough
source information to support later citations.

**Why this priority**: Chunk quality and provenance determine whether retrieval
can return useful, verifiable evidence.

**Independent Test**: Chunk documents containing short and long sections, verify
size limits and overlap behavior, and confirm that unchanged inputs reproduce the
same chunk identifiers and content.

**Acceptance Scenarios**:

1. **Given** a short section, **When** chunking completes, **Then** the section
   remains one chunk.
2. **Given** a long section, **When** chunking completes, **Then** it is split at
   natural boundaries without exceeding the configured maximum.
3. **Given** any chunk, **When** the corpus is inspected, **Then** the chunk
   identifies its source, section, order, and character range.

---

### User Story 4 - Inspect and Rerun the Corpus Build (Priority: P2)

A user can see what was processed, what failed, and whether a rebuild changed the
corpus.

**Why this priority**: The stage must be independently controllable and
reproducible before indexing begins.

**Independent Test**: Run the same build twice with unchanged source snapshots and
compare outputs, then change one source and verify that the difference is visible.

**Acceptance Scenarios**:

1. **Given** an unchanged input and source snapshot, **When** the build reruns,
   **Then** document and chunk identities remain stable.
2. **Given** a changed or unavailable source, **When** the build reruns, **Then**
   the manifest identifies the affected document.

### Edge Cases

- The discovery artifacts contain no accepted sources.
- Multiple discovery artifacts contain the same accepted identifier.
- An accepted source no longer exists or cannot be retrieved.
- Required identity fields conflict with the discovery record.
- Optional sections are absent or empty.
- A source contains duplicate or repeated section text.
- A section contains Unicode text, unusually long paragraphs, or no sentence
  boundaries.
- Two accepted records resolve to the same source identifier.
- The source changes between corpus builds.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST consume one or more existing research discovery
  artifacts and MUST NOT perform a new topic search.
- **FR-002**: Only accepted records MUST be included by default.
- **FR-003**: For each accepted source, the system MUST retrieve the detailed
  public record using its official source identifier.
- **FR-004**: The system MUST verify that the retrieved record matches the
  accepted identifier before creating a document.
- **FR-005**: The system MUST preserve source identifier, source link, source type,
  source date, retrieval time, and title in each document.
- **FR-006**: The system MUST preserve available title, status, summary,
  conditions, interventions, eligibility, outcomes, sponsor, and dates as
  distinct sections.
- **FR-007**: Missing sections MUST be identified as unavailable and MUST NOT be
  inferred or fabricated.
- **FR-008**: Chunks MUST NOT cross evidence-document or section boundaries.
- **FR-009**: Short sections MUST remain one chunk; long sections MUST be split at
  paragraph or sentence boundaries into chunks no larger than 1,200 characters.
- **FR-010**: Split sections MUST use an overlap of no more than 150 characters.
- **FR-011**: Every chunk MUST include a stable chunk identifier, source
  identifier, section name, chunk order, character range, source link, and content
  hash.
- **FR-012**: Rebuilding unchanged content MUST reproduce the same document and
  chunk identities.
- **FR-013**: The build MUST produce an inspectable manifest containing settings,
  processed sources, failed sources, document counts, chunk counts, and content
  changes.
- **FR-014**: A failed source MUST NOT corrupt successful documents; the overall
  run MUST identify partial completion.
- **FR-015**: The stage MUST stop before embeddings, vector indexing, retrieval,
  or question answering.
- **FR-016**: The system MUST deduplicate accepted identifiers across discovery
  artifacts and preserve every contributing run identifier.
- **FR-017**: If no accepted identifiers are available, the system MUST produce a
  `no_documents` manifest with zero documents and zero chunks.
- **FR-018**: The corpus build outcome MUST be one of `completed`, `partial`,
  `no_documents`, or `failed`.

### Key Entities

- **Discovery Input**: One or more accepted source records from feature 002
  artifacts.
- **Evidence Document**: One normalized public research source.
- **Document Section**: A named part of an evidence document, such as summary,
  eligibility, or outcomes.
- **Evidence Chunk**: A bounded, source-linked portion of one section.
- **Corpus Build Manifest**: The inputs, settings, source outcomes, counts, errors,
  and version information for one build.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every generated evidence document maps to exactly one accepted
  discovery record.
- **SC-002**: Every generated chunk resolves to one source and one named section.
- **SC-003**: No generated chunk exceeds 1,200 characters or crosses a source or
  section boundary.
- **SC-004**: Two builds with unchanged source snapshots produce identical
  document and chunk identifiers in 100% of cases.
- **SC-005**: Every source failure appears in the build manifest, and a partial
  run is never reported as fully successful.
- **SC-006**: A user can inspect documents, chunks, and the manifest and stop
  before feature 004 begins.
- **SC-007**: Duplicate identifiers across discovery artifacts result in one
  source retrieval while all contributing run identifiers are visible.
- **SC-008**: Zero accepted records produce a `no_documents` manifest rather than
  an empty successful corpus.

## Assumptions

- Feature 002 produces one or more versioned discovery artifacts consumed here.
- The first release uses structured ClinicalTrials.gov records rather than
  downloaded PDFs.
- Rejected and needs-review records are excluded unless a future specification
  adds an explicit override.
- Deterministic section and paragraph chunking is preferred over LLM-based
  rewriting.
- The 1,200-character maximum and 150-character overlap are starting defaults and
  may be evaluated and revised.
- Full-text publications, PDF parsing, OCR, embeddings, and vector retrieval are
  outside this feature.
- The follow-on retrieval boundary is described in
  [feature 004](../004-evidence-vector-retrieval/spec.md).
