# Feature Specification: Research Document Discovery and Screening

**Feature Branch**: `002-research-doc-discovery`

**Created**: 2026-10-21

**Status**: Draft

**Input**: Use one research agent to find publicly available clinical research
documents from a reliable source, obtain the current date and time, filter
candidates for source reliability and recency, and return the screening result
before document ingestion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Relevant Research Candidates (Priority: P1)

A user provides a clinical research topic, a date window, and a maximum number
of candidates. The research agent searches the approved clinical research
source and returns relevant document candidates with their source information.

**Why this priority**: Discovery produces the first useful evidence input and can
be inspected before any document is ingested.

**Independent Test**: Run a topic and date window against the approved source and
verify that candidates are returned with titles, identifiers, source links, and
source dates.

**Acceptance Scenarios**:

1. **Given** a valid topic, date window, and candidate limit, **When** discovery
   runs, **Then** candidates are returned in a structured list.
2. **Given** no matching records, **When** discovery runs, **Then** the user sees
   an explicit no-results result rather than an empty success.

---

### User Story 2 - Use Current Time for Recency (Priority: P1)

Before searching, the agent obtains the current date and time from a dedicated
capability and records it with the discovery run.

**Why this priority**: Recency filtering and later review depend on an explicit,
auditable time reference.

**Independent Test**: Run discovery and verify that the current-time result is
recorded before search results; simulate a time failure and verify that no search
is performed.

**Acceptance Scenarios**:

1. **Given** a working current-time capability, **When** discovery starts,
   **Then** the time is recorded in the run output before candidates.
2. **Given** the current-time capability fails, **When** discovery starts,
   **Then** discovery stops without searching or returning accepted candidates.

---

### User Story 3 - Screen and Explain Candidates (Priority: P2)

The agent reflects on each candidate using the approved source and date policy.
The user receives accepted, rejected, and needs-review candidates with specific
reason codes.

**Why this priority**: The user must understand why a document is considered
usable before ingestion.

**Independent Test**: Provide candidates with approved metadata, unapproved
metadata, duplicate identifiers, missing dates, and dates outside the window;
verify that each is classified correctly with a reason.

**Acceptance Scenarios**:

1. **Given** a candidate from the approved source with complete metadata,
   **When** screening completes, **Then** it is accepted or marked needs-review
   with a reason.
2. **Given** an unapproved source, missing required metadata, or a date outside
   the requested window, **When** screening completes, **Then** the candidate is
   rejected with a specific reason.
3. **Given** two candidates with the same official identifier, **When** screening
   completes, **Then** the duplicate relationship is reported.

### Edge Cases

- The approved source returns an error, rate limit, or malformed response.
- Current time is unavailable or invalid.
- A candidate has no official identifier, publication date, or update date.
- Publication and update dates conflict.
- A record falls exactly on a date-window boundary.
- Multiple candidates share an identifier or canonical source link.
- The source changes between discovery runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST provide a research topic, date window, and candidate
  limit.
- **FR-002**: The agent MUST obtain the current date and time from a dedicated
  application capability before its first search.
- **FR-003**: Discovery MUST stop without searching if the current date and time
  cannot be obtained.
- **FR-004**: The first release MUST search only its approved clinical research
  source.
- **FR-005**: Each candidate MUST include title, official identifier when
  available, source link, source type, publication or update date, retrieval
  time, and a short evidence snippet.
- **FR-006**: The system MUST independently validate source, required metadata,
  and date-window compliance.
- **FR-007**: The system MUST identify duplicate candidates using official
  identifiers or a canonical source link.
- **FR-008**: The agent MUST classify every candidate as accepted, rejected, or
  needs-review with a reason code.
- **FR-009**: The system MUST preserve the query, current time, source response
  summary, candidate decisions, and failures for that run.
- **FR-010**: Discovery MUST stop before downloading, parsing, or ingesting any
  document.
- **FR-011**: Source failures and incomplete runs MUST be reported as failures,
  not as successful empty results.

### Key Entities

- **Discovery Request**: Topic, inclusive date window, and candidate limit.
- **Research Candidate**: A source record and its provenance metadata.
- **Screening Decision**: Accepted, rejected, or needs-review status with reason
  codes and supporting metadata.
- **Discovery Run**: The request, recorded current time, search summary, candidate
  decisions, and failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every returned candidate includes source provenance and a screening
  decision.
- **SC-002**: Every accepted candidate comes from the approved source and falls
  within the requested date window.
- **SC-003**: A failed current-time capability results in zero searches and zero
  accepted candidates.
- **SC-004**: Every duplicate, out-of-window record, and missing-metadata record
  receives an identifiable reason code.
- **SC-005**: A user can inspect the complete discovery run and stop before
  ingestion.

## Assumptions

- The first release uses ClinicalTrials.gov as its only approved discovery source.
- The first release collects structured source records and does not download or
  parse PDFs.
- The date window is supplied explicitly; “latest” without a window is not a
  supported request.
- The current-time capability returns an ISO 8601 date and time with timezone.
- One research agent may perform discovery and structured reflection in separate
  model steps; multi-agent orchestration is out of scope.
- General web search, PubMed, Europe PMC, query rewriting, and automatic retries
  are deferred.
