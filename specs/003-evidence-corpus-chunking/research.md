# Research: Evidence Corpus Assembly and Chunking

## Detailed Source Retrieval

**Decision**: Reuse the existing ClinicalTrials.gov API v2 client and add detailed
study retrieval through `GET /api/v2/studies/{nctId}`.

**Rationale**: Discovery already established the approved source and canonical
study URL. Reusing the client avoids duplicate HTTP, timeout, and error handling.
A live read-only response for `NCT05214573` confirmed the section structure needed
by this feature.

**Alternatives considered**: Downloading linked protocol PDFs, scraping study web
pages, or introducing a second source adapter is deferred.

Transient HTTP 429 and 5xx responses receive one bounded retry with a short
`Retry-After` delay. Exhausted retries remain explicit source failures with
status and retryability metadata.

## Normalized Sections

**Decision**: Extract the study record into title, status/dates, summary,
conditions, interventions, eligibility, outcomes, and sponsor sections.

**Rationale**: These sections are identifiable in the structured response and
represent useful evidence without flattening the complete, complex results tree.

**Alternatives considered**: Storing the full raw JSON as searchable text would
preserve noise and make chunk quality difficult to evaluate. Full results tables
and linked publications are deferred until the first corpus is evaluated.

## Artifact Format

**Decision**: Emit one directory with `manifest.json`, `documents.jsonl`, and
`chunks.jsonl`.

**Rationale**: JSONL keeps each document and chunk independently inspectable and
avoids rewriting one large nested JSON value. The manifest provides stage-level
status and provenance.

**Alternatives considered**: SQLite, a vector database, or Parquet adds storage and
query complexity before the corpus size requires it.

## Chunking Strategy

**Decision**: Use deterministic section, paragraph, and sentence boundaries with a
1,200-character maximum and up to 150 characters of overlap.

**Rationale**: It is cheap, explainable, and reproducible. The short default fits
the later MiniLM input limit while preserving section context.

**Alternatives considered**: LLM chunking adds cost and variability; fixed raw
character windows can split unrelated sections.

Overlap starts are aligned forward to word boundaries so chunks remain readable
and do not begin with partial words.

## Stable Identity

**Decision**: Generate document IDs from the NCT identifier and chunk IDs from
NCT identifier, section, character range, and content hash.

**Rationale**: Unchanged inputs retain stable IDs, while changed text or boundaries
produce a visible difference.

**Alternatives considered**: Sequential-only IDs are easy for humans but unstable
when sources are added, removed, or reordered.

## Build Atomicity

**Decision**: Build in a temporary sibling directory and replace the final output
directory only after a valid terminal outcome.

**Rationale**: A failed build cannot expose a partially written corpus as complete.
`partial` remains a valid explicit outcome with its failures recorded.

**Alternatives considered**: Writing files directly into the final directory can
leave a misleading half-built corpus after a process failure.

## No LLM

**Decision**: Feature 003 performs no model calls.

**Rationale**: Section extraction and chunking are deterministic data operations.
Keeping the model out reduces cost, latency, non-determinism, and test complexity.

**Alternatives considered**: Model-assisted cleanup and semantic chunking are
deferred until evaluation shows a concrete extraction or boundary problem.
