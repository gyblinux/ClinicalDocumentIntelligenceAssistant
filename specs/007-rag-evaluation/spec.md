# Feature Specification: RAG Evaluation and Answer Presentation

**Feature Branch**: `007-rag-evaluation`

**Created**: 2026-10-21

**Status**: Implementation and automated validation complete; delegated
AI-assisted readability review passed 9/10, with independent human review and
multi-source/conflicting-evidence scenarios still unverified

**Input**: Evaluate linked feature 006 question-to-answer pipeline records using
20-40 fixed questions, per-case and aggregate metrics, a recorded baseline, and
one controlled improvement comparison. Also render read-only, human-readable
answer views that preserve claims, citations, status, and available evaluation
evidence without implying a per-answer trust probability.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Fixed Baseline Evaluation (Priority: P1)

A user evaluates a versioned question set through the feature 006 orchestration
interface, either by producing pipeline records for each case or by loading saved
records, and receives per-case and aggregate quality results.

**Why this priority**: Reproducible measurement is required to assess the RAG
pipeline.

**Independent Test**: Run the same fixed cases and configuration twice and verify
comparable result manifests.

**Acceptance Scenarios**:

1. **Given** a valid 20-40 case evaluation set, **When** baseline evaluation runs,
   **Then** every case has one feature 006 pipeline record linking its retrieval
   and answer artifacts.
2. **Given** unchanged inputs, recorded configuration, and test set, **When**
   evaluation reruns, **Then** versions and per-case results remain comparable.

---

### User Story 2 - Measure Retrieval and Answer Quality Separately (Priority: P1)

The report separates evidence-retrieval quality from answer quality so failures
can be attributed to the correct stage.

**Why this priority**: A poor answer may result from missing evidence or poor
generation.

**Independent Test**: Include cases with expected evidence, correct answers,
incorrect citations, and unanswerable questions; verify each metric is reported
independently.

**Acceptance Scenarios**:

1. **Given** expected evidence identifiers and a retrieval artifact, **When**
   evaluation completes, **Then** retrieval relevance is reported per case and in
   aggregate.
2. **Given** a persisted answer record, **When** evaluation completes, **Then**
   citation validity, answer faithfulness, and refusal behavior are reported
   separately.

---

### User Story 3 - Compare One Controlled Improvement (Priority: P2)

A user compares the baseline against one changed retrieval setting and sees the
difference in quality, latency, and cost.

**Why this priority**: Controlled comparison demonstrates measurable improvement
without broad re-architecture.

**Independent Test**: Run baseline and candidate results that differ only by one
declared setting, then verify the report identifies that setting.

**Acceptance Scenarios**:

1. **Given** baseline and candidate configurations, **When** evaluation completes,
   **Then** the report includes both metrics and the single changed variable.
2. **Given** more than one changed variable, **When** comparison is requested,
   **Then** the run is rejected as uncontrolled.

---

### User Story 4 - Render a Human-Readable Answer View (Priority: P2)

A user opens a saved feature 006 pipeline record and receives a readable answer
view containing a concise answer, source references, status, limitations, and any
applicable evaluation result.

**Why this priority**: Structured artifacts are appropriate for evaluation but are
not an effective user-facing answer by themselves.

**Independent Test**: Render one answered artifact containing multiple claims and
verify that every claim is represented, every citation marker resolves to a
source, no new factual content appears, and the output is deterministic.

**Acceptance Scenarios**:

1. **Given** an answered pipeline and answer record, **When** the view is
   rendered, **Then** it shows a concise answer paragraph plus a numbered source
   list that preserves claim-to-source relationships.
2. **Given** no case-specific evaluation result, **When** the answer is displayed,
   **Then** the view states that semantic quality has not been independently
   evaluated and never presents a trust percentage.
3. **Given** a matching evaluation result, **When** the answer is displayed,
   **Then** the view shows the versioned pass/fail checks and suite identity
   separately from the answer.
4. **Given** an abstention or failure, **When** the view is rendered, **Then** it
   explains the outcome without displaying unsupported factual prose.

## Scope Boundaries

- Evaluation is offline and read-only with respect to feature 006 pipeline and
  answer records.
- It cannot withdraw, rewrite, or repair an answer already returned to a user.
- Runtime grounding, citation validation, abstention, and failure behavior remain
  owned by features 004 through 006.
- Presentation is a deterministic, read-only rendering of existing claims,
  citations, statuses, and evaluation results.
- Presentation MUST NOT introduce facts, paraphrase with another model, or hide
  claim-level citations.
- A single summary paragraph is shown as the primary answer, followed by all
  claims, sources, and limitations. It does not replace the structured claims used
  for evaluation.
- Aggregate benchmark rates are system-level measures and MUST NOT be presented as
  the probability that one answer is correct.
- A web API, continuous monitoring, and automatic prompt rewriting remain outside
  this feature.

### Edge Cases

- Fewer than 20 or more than 40 evaluation cases.
- Duplicate case identifiers.
- Missing expected evidence or expected answer.
- Unanswerable cases with no expected citation.
- Conflicting or invalid citations.
- One case fails while other cases complete.
- Evaluation inputs or model settings change between runs.
- An answer has no matching evaluation case.
- An evaluation result references a different answer, suite, or rubric version.
- An answer contains many claims that would make one paragraph difficult to read.
- Duplicate citations map to the same source.
- The linked pipeline or answer artifact is malformed.
- An answer is insufficient evidence or failed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The fixed test set MUST contain 20-40 uniquely identified cases.
- **FR-002**: Each case MUST define its question, answerability, expected evidence
  or reference answer, and scoring rubric.
- **FR-003**: Unanswerable cases MUST expect an explicit abstention rather than an
  answer.
- **FR-004**: Evaluation MUST consume or produce, for every case, one feature 006
  pipeline record that links one feature 004 retrieval artifact and one feature
  005 answer record.
- **FR-005**: Retrieval relevance MUST be scored separately from answer quality.
- **FR-006**: Citation validity MUST verify that cited evidence was supplied to
  answering.
- **FR-007**: Answer faithfulness MUST be scored against fixed expected facts or a
  versioned rubric.
- **FR-008**: Refusal correctness MUST be measured for unanswerable cases.
- **FR-009**: Evaluation MUST record latency and token/cost usage when available.
- **FR-010**: The report MUST include per-case and aggregate results.
- **FR-011**: A comparison MUST change exactly one declared configuration variable
  and record both configurations.
- **FR-012**: Invalid cases or uncontrolled comparisons MUST fail clearly.
- **FR-013**: The report MUST identify the pipeline record, retrieval artifact, and
  answer record used for every case.
- **FR-014**: Evaluation MUST preserve the original pipeline and answer artifacts
  and write results separately.
- **FR-015**: Every failed case MUST record versioned failure codes and an
  actionable intervention category or a clear "no change recommended" outcome.
- **FR-016**: Presentation MUST consume a feature 006 pipeline record and its
  linked answer artifact without modifying either artifact.
- **FR-017**: Presentation MUST use only existing answer claims, reasons, status,
  citations, and evaluation results; it MUST NOT add factual content or clinical
  advice.
- **FR-018**: Every factual claim in the readable view MUST retain a citation
  marker that resolves to the canonical source from the answer record.
- **FR-019**: The default answered view MUST provide a concise answer paragraph
  followed by readable claim/source details when needed for traceability.
- **FR-020**: Presentation MUST identify `answered`, `insufficient_evidence`, and
  `failed` outcomes distinctly.
- **FR-021**: When no evaluation verdict matches the answer, pipeline, case, suite,
  rubric, and configuration identifiers, presentation MUST state that semantic
  quality was not independently evaluated.
- **FR-022**: When evaluation exists, presentation MUST show versioned check
  outcomes and MUST NOT render a trust or correctness percentage for that answer.
- **FR-023**: Presentation MUST be deterministic, versioned, and reproducible for
  the same input and renderer version.
- **FR-024**: Presentation validation MUST detect omitted claims, introduced
  claims, unresolved citation markers, and mismatched evaluation verdicts.
- **FR-025**: Presentation MUST treat normalized validated claims and citations as
  authoritative and MUST NOT display raw model output as answer content.
- **FR-026**: Every claim in the answer record MUST appear in the detail section
  of the rendered answer, even when the summary paragraph highlights only some
  claims.
- **FR-027**: The default view MUST be plain text with a complete length below
  1,000 words and an extractive summary paragraph of at most 180 words.
- **FR-028**: Source markers MUST be assigned by first citation appearance and
  deduplicated by canonical URL plus NCT identifier, with existing sections
  aggregated under one marker.
- **FR-029**: If complete, non-truncated content cannot fit below 1,000 words,
  presentation MUST fail explicitly rather than omit or truncate claims.
- **FR-030**: Human readability review MUST cover five representative rendered
  cases using a versioned 0-2 rubric and persist the reviewer scores.

### Key Entities

- **Evaluation Case**: Fixed question, answerability, expected evidence,
  reference facts, and rubric.
- **Evaluation Pipeline Input**: One case's feature 006 pipeline record and the
  linked feature 004 and feature 005 artifacts.
- **Evaluation Set**: Versioned collection of 20-40 cases.
- **Metric Result**: Retrieval, citation, faithfulness, refusal, latency, or cost
  score for a case.
- **Evaluation Run**: Test-set version, pipeline/retrieval/answer artifact links,
  corpus/index/model/prompt configuration, per-case results, aggregates, and
  errors.
- **Comparison Run**: Baseline and candidate configurations with one changed
  variable.
- **Failure Diagnosis**: Versioned failure codes, affected stage, and suggested
  intervention category for a failed case.
- **Presentation Request**: One pipeline record, renderer version, and display
  format.
- **Rendered Answer**: Deterministic human-readable answer paragraph, claim/source
  references, status, limitations, and optional evaluation verdict.
- **Evaluation Verdict**: Versioned per-case checks linked to pipeline and answer
  identifiers; not a generalized trust probability.
- **Presentation Review**: Versioned human readability scores and notes for a
  representative sample of rendered answers.

## Success Criteria *(mandatory)*

- **SC-001**: All 20-40 fixed cases produce a recorded result or explicit case
  failure.
- **SC-002**: The report provides retrieval relevance, citation validity,
  faithfulness, and refusal metrics separately.
- **SC-003**: Unanswerable-case refusal behavior is measured independently.
- **SC-004**: Every comparison identifies exactly one changed variable.
- **SC-005**: Baseline metrics, latency, and available token/cost data are
  preserved for later comparison.
- **SC-006**: Two runs with unchanged versions and inputs produce comparable
  reports.
- **SC-007**: Every evaluated case identifies exactly one feature 006 pipeline
  record and its matching retrieval and answer artifacts.
- **SC-008**: Evaluation never modifies or withdraws the original answer.
- **SC-009**: Every failed case has a reproducible diagnosis and recommended
  intervention category.
- **SC-010**: The same pipeline artifact and renderer version produce identical
  readable output.
- **SC-011**: Every factual claim in a rendered answer retains its validated
  source mapping.
- **SC-012**: Presentation introduces zero new factual claims.
- **SC-013**: Answers without a matching evaluation show an explicit
  "not independently evaluated" status.
- **SC-014**: No rendered answer presents a system benchmark rate or evaluation
  score as a per-answer trust percentage.
- **SC-015**: Abstained and failed artifacts never render unsupported factual
  answer prose.
- **SC-016**: Every rendered factual statement originates from a validated claim,
  and every validated claim is represented in the rendered detail section.
- **SC-017**: Every accepted presentation is plain text, below 1,000 words, and
  has a summary paragraph of at most 180 words.
- **SC-018**: Every source marker is stable and resolves to one canonical
  URL/NCT source group.
- **SC-019**: Every human readability review contains five cases and meets an
  aggregate score of at least 8/10 with no zero for citation clarity or caution.

## Assumptions

- Features 004, 005, and 006 are available.
- Feature 006 pipeline records are the evaluation entrypoint and link the
  underlying retrieval and answer artifacts.
- The feature 005 answer record is the answer-side evaluation input; the paired
  feature 004 artifact remains necessary for retrieval scoring and diagnostics.
- Evaluation is an offline quality-measurement stage; it does not protect the
  already-returned answer from defects discovered afterward.
- Presentation is derived from saved artifacts and is optional to evaluation.
- A per-answer evaluation verdict is shown only when the case, suite, rubric, and
  artifact identifiers match.
- Human readability may be reviewed with a small rubric; it is not converted into
  a trust percentage.
- Raw model output remains audit metadata and is not an authoritative source for
  user-facing answer text.
- The initial test set remains in the 20-40 case range.
- Deterministic checks and a small human-reviewed rubric are used before adding an
  LLM judge.
- One retrieval configuration setting is compared at a time; the exact setting is
  chosen during planning.
- A web API, CI, and final demonstration remain separate engineering scope.
