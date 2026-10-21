# Feature Specification: Reproducible RAG Evaluation

**Feature Branch**: `007-rag-evaluation`

**Created**: 2026-10-21

**Status**: Draft - preliminary

**Input**: Evaluate linked feature 006 question-to-answer pipeline records using
20-40 fixed questions, per-case and aggregate metrics, a recorded baseline, and
one controlled improvement comparison.

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

## Scope Boundaries

- Evaluation is offline and read-only with respect to feature 006 pipeline and
  answer records.
- It cannot withdraw, rewrite, or repair an answer already returned to a user.
- Runtime grounding, citation validation, abstention, and failure behavior remain
  owned by features 004 through 006.
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

## Assumptions

- Features 004, 005, and 006 are available.
- Feature 006 pipeline records are the evaluation entrypoint and link the
  underlying retrieval and answer artifacts.
- The feature 005 answer record is the answer-side evaluation input; the paired
  feature 004 artifact remains necessary for retrieval scoring and diagnostics.
- Evaluation is an offline quality-measurement stage; it does not protect the
  already-returned answer from defects discovered afterward.
- The initial test set remains in the 20-40 case range.
- Deterministic checks and a small human-reviewed rubric are used before adding an
  LLM judge.
- One retrieval configuration setting is compared at a time; the exact setting is
  chosen during planning.
- A web API, CI, and final demonstration remain separate engineering scope.
