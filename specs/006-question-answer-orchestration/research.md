# Research: Question-to-Answer Orchestration

**Status**: Complete for plan review

## R-001: Add a Thin Composition Layer

- **Decision**: Add an `orchestration/` package that calls the existing retrieval
  and answering services directly.
- **Rationale**: The new behavior is coordination, not another retrieval or answer
  implementation. Reusing the tested services preserves citations, abstention, and
  tool restrictions.
- **Alternatives considered**:
  - Invoke both CLIs as subprocesses: harder to test, parse, and propagate errors.
  - Merge retrieval and answering code: increases coupling and removes the
    independently inspectable stage boundary.

## R-002: Require Fresh Retrieval for Every Question

- **Decision**: Each orchestration request performs a new feature 004 search using
  the exact submitted question.
- **Rationale**: Retrieval results are question-specific. Reusing a prior result
  would violate evidence relevance and make different questions appear to share
  one evidence base.
- **Alternatives considered**:
  - Reuse evidence until the collection changes: simple but unsound for new
    questions.
  - Let the answer model decide whether to retrieve: hides a required grounding
    step behind model behavior.

## R-003: Persist Retrieval Before Answering

- **Decision**: Serialize the feature 004 `RetrievalRun` to a local JSON artifact
  before invoking feature 005.
- **Rationale**: Feature 005 already accepts a retrieval artifact, and preserving
  it before model use makes retrieval failure, no-results, and later evaluation
  independently inspectable.
- **Alternatives considered**:
  - Refactor feature 005 to accept only in-memory evidence: unnecessary coupling
    for this small change.
  - Keep the retrieval only in memory: loses the controlled-stage audit trail.

## R-004: Link Artifacts with a Pipeline Record

- **Decision**: Persist a third record containing the question, stage IDs and
  paths, configuration, timing, statuses, and errors.
- **Rationale**: A single linked record makes the user-facing workflow and feature
  007 input deterministic without duplicating the full retrieval or answer files.
- **Alternatives considered**:
  - Infer links from filenames: brittle and not auditable.
  - Embed full retrieval and answer records in the pipeline record: redundant and
    risks conflicting sources of truth.

## R-005: Keep Runtime Validation and Offline Evaluation Separate

- **Decision**: Feature 006 performs runtime input/retrieval validation and relies
  on feature 005 citation validation and abstention. Feature 007 scores semantic
  quality offline from saved artifacts.
- **Rationale**: Evaluation cannot retract an answer already shown to a user.
  Pretending otherwise would give a false safety guarantee. Runtime checks should
  prevent known invalid states; evaluation should measure quality and guide the
  next version.
- **Alternatives considered**:
  - Run full feature 007 synchronously before returning: adds evaluation latency
    and conflates online serving with offline measurement.
  - Silently change or suppress saved answers during evaluation: destroys audit
    integrity.

## R-006: Keep the Prompt Layer Unchanged

- **Decision**: Feature 006 does not add or modify an LLM prompt.
- **Rationale**: The user question already becomes `query.text` in retrieval and is
  reused by feature 005's existing user-prompt builder. Orchestration requires no
  model decision.
- **Alternatives considered**:
  - Add an orchestration prompt that decides whether to retrieve: introduces
    non-determinism and unsupported tool behavior.

## R-007: Return a Pipeline JSON with Answer Summary

- **Decision**: Standard output contains the pipeline record, including answer
  claims, abstention reason or failure, and paths to full stage artifacts.
- **Rationale**: The interface remains useful to a direct user while preserving
  machine-readable linkage and avoiding a prose-only CLI contract.
- **Alternatives considered**:
  - Print only the answer text: loses provenance.
  - Print three separate JSON objects: complicates clients.

## R-008: Use Existing Local Artifact Storage

- **Decision**: Default to `artifacts/retrieval/`, `artifacts/answers/`, and
  `artifacts/pipelines/` with atomic writes and no silent overwrite.
- **Rationale**: Matches the current project pattern, remains inspectable, and
  needs no database migration.
- **Alternatives considered**:
  - Store pipeline state in a database: unnecessary for a single-user prototype.
