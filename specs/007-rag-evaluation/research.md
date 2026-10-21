# Research: RAG Evaluation and Answer Presentation

**Status**: Complete for plan review

## R-001: Use One Versioned JSON Case Set

- **Decision**: Keep the 20-40 evaluation cases in one checked-in JSON document
  with an explicit `set_version`.
- **Rationale**: It is readable, diffable, easy to validate, and small enough for
  the project's baseline.
- **Alternatives considered**:
  - YAML: friendlier for prose but requires an additional parser dependency.
  - One file per case: easier isolation but unnecessarily fragmented for 20-40
    cases.

## R-002: Support Saved and Generated Pipeline Inputs

- **Decision**: Evaluation can load saved feature 006 pipeline records or invoke
  the existing orchestration service to generate them.
- **Rationale**: Saved mode makes tests and reports replayable without Docker;
  generated mode measures the current system end to end.
- **Alternatives considered**:
  - Generated mode only: expensive and Docker-dependent.
  - Saved mode only: makes fresh baseline creation manual.

## R-003: Use Deterministic Baseline Metrics

- **Decision**: Compute retrieval hit@k, recall@k, MRR, citation validity/coverage,
  refusal correctness, and case-rubric key-point/forbidden-phrase checks.
- **Rationale**: These checks are transparent, cheap, and reproducible. They fit the
  small-project scope and expose retrieval-vs-generation failure attribution.
- **Alternatives considered**:
  - LLM judge on day one: adds provider variance, cost, prompt risk, and another
    system to evaluate.
  - Human review for every answer: useful but too slow for repeatable baselines.

## R-004: Treat Text Matching as a Proxy, Not Truth

- **Decision**: Record rubric limitations and require a small human-reviewed
  sample in acceptance.
- **Rationale**: Required/forbidden phrase checks can miss paraphrase and nuance;
  they must not be presented as a trust guarantee.
- **Alternatives considered**:
  - Claim deterministic checks prove faithfulness: false.
  - Add a second model verifier: deferred until measured baseline weaknesses
    justify it.

## R-005: Keep One-Variable Comparison Enforced

- **Decision**: Compare reports only when test-set/rubric versions and case IDs
  match and exactly one declared configuration value differs.
- **Rationale**: A changed chunk size, top-k, prompt, or index setting must remain
  attributable.
- **Alternatives considered**:
  - Compare unrelated runs: not reproducible or actionable.

## R-006: Render Plain Text Deterministically

- **Decision**: Default presentation is plain text generated from validated claims
  and citations without an LLM.
- **Rationale**: It is stable, portable, easy to diff, and cannot hallucinate new
  answer content.
- **Alternatives considered**:
  - Markdown first: visually richer but less portable as a default.
  - LLM-written summary: risks introducing unsupported facts.

## R-007: Use an Extractive Summary Paragraph

- **Decision**: Build the paragraph from the first existing claims in their
  recorded order, targeting 3-5 claims and at most 180 words.
- **Rationale**: This keeps the opening readable without rephrasing claims. All
  remaining claims appear in supporting detail.
- **Alternatives considered**:
  - One paragraph containing every claim: often too dense.
  - Model paraphrase: needs another grounding validation layer.

## R-008: Enforce a Hard 999-Word View Limit

- **Decision**: Reject presentation with `presentation_too_long` when complete,
  non-truncated output exceeds 999 words.
- **Rationale**: Meets the user's length decision while preserving all claims.
- **Alternatives considered**:
  - Truncate details: violates claim completeness.
  - Split pages initially: useful later but unnecessary for expected cases.

## R-009: Deduplicate Sources by Canonical Identity

- **Decision**: Number sources by first citation appearance and deduplicate by
  `source_url + nct_id`. Aggregate source sections under one marker.
- **Rationale**: The current answer has five chunk citations but only three trial
  URLs. URL-level numbering is cleaner for humans while chunk IDs remain in the
  machine artifact.
- **Alternatives considered**:
  - One marker per chunk: verbose and confusing.
  - Deduplicate by title: unstable.

## R-010: Match Per-Answer Verdicts Strictly

- **Decision**: Show a verdict only when answer, pipeline, case, suite, rubric, and
  configuration fingerprint match.
- **Rationale**: A benchmark score from another answer or suite is not evidence
  about this answer.
- **Alternatives considered**:
  - Match by question text: collisions and prompt changes make it unreliable.
  - Show aggregate score on every answer: misleading.

## R-011: Use Labels Instead of Trust Percentages

- **Decision**: Show `not independently evaluated`, pass/fail checks, and explicit
  limitations. Never derive a probability from benchmark rates.
- **Rationale**: The evaluation does not calibrate per-answer correctness.
- **Alternatives considered**:
  - `87% trustworthy`: unsupported and vulnerable to automation bias.
  - Similarity score as confidence: vector similarity is not calibrated truth.

## R-012: Validate Presentation through Invariants and Human Rubric

- **Decision**: Automated checks cover claim/citation completeness, determinism,
  status, length, and verdict matching. A small 0-2 human rubric covers directness,
  structure, clarity, and caution.
- **Rationale**: These dimensions complement each other without pretending
  readability is fully machine-decidable.
- **Alternatives considered**:
  - LLM readability judge: deferred.
  - No human check: insufficient for user-facing acceptance.
