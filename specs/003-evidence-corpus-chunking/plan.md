# Implementation Plan: Evidence Corpus Assembly and Chunking

**Branch**: `003-evidence-corpus-chunking` | **Date**: 2026-10-21 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/003-evidence-corpus-chunking/spec.md`

## Summary

Add a local, deterministic corpus-build stage. It reads one or more versioned
discovery artifacts, deduplicates accepted NCT identifiers, fetches detailed
ClinicalTrials.gov records, normalizes selected study sections, and writes stable
documents and chunks. It stops before embeddings or vector indexing.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing `httpx`; no new runtime dependency

**Storage**: A local build directory containing `manifest.json`,
`documents.jsonl`, and `chunks.jsonl`

**Testing**: `pytest` with discovery fixtures, trimmed ClinicalTrials.gov
responses, a fake source client, and no live network

**Target Platform**: Cross-platform command line, verified on Windows PowerShell

**Project Type**: Single Python package with a new `clinical-doc-corpus` CLI

**Performance Goals**: Process the current 12 unique accepted sources in one
sequential run; no concurrency, queue, or database

**Constraints**: Public data only; no LLM chunking; deterministic output; no
embedding or retrieval work

**Scale/Scope**: A small manually controlled corpus built from one or more
discovery artifacts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Public evidence only**: Inputs are accepted feature 002 artifacts and remain
  linked to ClinicalTrials.gov provenance.
- **Evidence-grounded answers**: This feature creates citation-ready sections and
  chunks but does not answer questions.
- **Reproducible evaluation**: Stable IDs, content hashes, settings, failures, and
  input run IDs are recorded in the manifest.
- **Independent stages**: Discovery, corpus build, indexing, and answering remain
  separate commands with inspectable artifacts.
- **Small scope**: No vector database, embeddings, model calls, or new storage
  service is introduced.

No constitutional violations or exceptions are required.

## Project Structure

### Documentation

```text
specs/003-evidence-corpus-chunking/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- cli.md
|   `-- artifacts.md
`-- checklists/
    `-- requirements.md
```

### Source Code

```text
src/clinical_doc_assist/
|-- research/
|   `-- clinical_trials.py       # Extend with detailed study retrieval
`-- corpus/
    |-- __init__.py
    |-- models.py                # Document, section, chunk, and manifest records
    |-- artifacts.py             # Discovery input and corpus artifact I/O
    |-- normalize.py             # ClinicalTrials.gov section extraction
    |-- chunking.py              # Deterministic section-aware chunking
    |-- builder.py               # Stage orchestration and outcome resolution
    `-- cli.py                   # clinical-doc-corpus command

tests/
|-- fixtures/corpus/
|-- test_clinical_trials.py      # Extended for study-detail retrieval
|-- test_corpus_models.py
|-- test_corpus_artifacts.py
|-- test_corpus_normalize.py
|-- test_corpus_chunking.py
|-- test_corpus_builder.py
`-- test_corpus_cli.py
```

**Structure Decision**: Keep the new stage in a `corpus/` subpackage. Extend the
existing approved source adapter for detailed retrieval instead of creating a
second ClinicalTrials.gov HTTP client.

## Design

### Input Processing

1. Read every `--discovery-run` path.
2. Require `schema_version == "1.0"` and a non-empty `run_id`.
3. Collect accepted NCT identifiers and contributing run IDs.
4. Deduplicate identifiers while preserving deterministic source order.
5. Stop with `no_documents` if no accepted identifiers remain.

### Detailed Retrieval

Extend `ClinicalTrialsSource` with:

```text
GET https://clinicaltrials.gov/api/v2/studies/{nctId}
```

Verify that the returned record's NCT ID matches the accepted identifier.
Transport or identity failures are recorded per source; other sources continue.
HTTP 429 and transient 5xx responses receive one bounded retry, and failures
record stable error categories, status, and retryability.

### Normalization

Produce one document with named text sections:

- title and identifiers
- status and dates
- summary
- conditions
- interventions
- eligibility
- primary and secondary outcomes
- sponsor

Optional missing sections are listed in `unavailable_sections`. The implementation
does not flatten full results tables, publications, or linked PDFs in this release.

### Chunking

- Keep sections separate.
- Keep a section intact when it is at most 1,200 characters.
- Split longer sections first by paragraph and then by sentence.
- Target no more than 1,200 characters with at most 150 characters of overlap.
- Preserve character offsets within each normalized section.
- Align overlap starts to word boundaries.
- Generate stable IDs from NCT ID, section, offsets, and content hash.

### Output

Build into a temporary sibling directory and atomically rename it to `--output`
on completion. The output contains:

```text
manifest.json
documents.jsonl
chunks.jsonl
```

`manifest.json` records status, build ID, settings, contributing discovery run
IDs, source successes/failures, change information, and counts.

### Outcomes

- `completed`: every unique accepted source produced a document.
- `partial`: at least one document succeeded and at least one failed.
- `no_documents`: no accepted identifiers were available.
- `failed`: no usable documents were produced because of an operational error.

Exit codes:

- `0`: `completed` or `partial` with usable chunks.
- `3`: `no_documents`.
- `1`: `failed`.
- `2`: invalid arguments or invalid discovery artifacts.

### Testing Strategy

- Discovery artifact validation and deduplication across multiple runs.
- Detailed retrieval request and identity verification.
- Section extraction from a trimmed real API response.
- Missing sections and malformed optional fields.
- Chunk boundary, overlap, offsets, and stable IDs.
- `completed`, `partial`, `no_documents`, and `failed` builder outcomes.
- CLI output and atomic directory creation using fake sources.

## Complexity Tracking

No violations. The feature uses standard-library dataclasses, existing HTTP
support, deterministic functions, and local JSON/JSONL files.
