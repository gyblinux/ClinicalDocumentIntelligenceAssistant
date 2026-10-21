# Tasks: RAG Evaluation and Answer Presentation

**Input**: Design documents from `specs/007-rag-evaluation/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md),
[research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Status**: Implementation complete; delegated AI-assisted readability review
passed 9/10, with independent human review and multi-source/conflicting-evidence
scenarios still unverified

**Tests**: Included because the repository constitution requires relevant tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable across a different file with no incomplete dependency.
- **[Story]**: Maps to `spec.md`.
- Every task includes an exact repository path.

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the evaluation package and test fixture directories in
  `src/clinical_doc_assist/evaluation/__init__.py` and
  `tests/fixtures/evaluation/`.
- [X] T002 Register `clinical-doc-eval` and `clinical-doc-present` entry points in
  `pyproject.toml`.
- [X] T003 [P] Add a valid 20-case evaluation set, invalid cardinality variants,
  and a complete pipeline map under `tests/fixtures/evaluation/`.
- [X] T004 [P] Add linked pipeline/retrieval/answer fixture artifacts, matching and
  mismatched verdicts, and a five-case presentation-review input under
  `tests/fixtures/evaluation/artifacts/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**CRITICAL**: Complete this phase before any story.

- [X] T005 Implement evaluation records and errors in
  `src/clinical_doc_assist/evaluation/models.py`: exactly 20-40 unique cases;
  answerability `answerable|unanswerable`; metric values; failure diagnoses; case
  results; evaluation/comparison runs; exact-match verdicts; rendered answers below
  1,000 words; summaries at most 180 words; no trust percentage fields.
- [X] T006 [P] Implement strict evaluation-set and pipeline-map loading in
  `src/clinical_doc_assist/evaluation/cases.py`, including 20-40 case boundaries,
  unique case IDs, answerable/unanswerable field rules, and one map entry per case.
- [X] T007 [P] Implement pipeline/retrieval/answer artifact loaders and canonical
  configuration fingerprints in
  `src/clinical_doc_assist/evaluation/runner.py`.
- [X] T008 [P] Add reusable pipeline, verdict, and presentation fixtures in
  `tests/fixtures/evaluation/fakes.py`.

**Checkpoint**: Shared records, validation, loaders, and fakes are ready.

---

## Phase 3: User Story 1 - Run a Fixed Baseline Evaluation (Priority: P1) MVP

**Goal**: Evaluate all fixed cases from saved or generated feature 006 pipeline
records and persist a reproducible baseline.

**Independent Test**: Run the same saved 20-case set twice and verify matching
versions, linked artifacts, case results, and comparable manifests.

### Tests for User Story 1

- [X] T009 [P] [US1] Add failing saved-mode tests for complete pipeline-map loading,
  missing/unknown case links, linked artifacts, and reproducible baseline output in
  `tests/test_evaluation_runner.py`.
- [X] T010 [P] [US1] Add failing generated-mode tests for default collection/limit,
  one feature 006 call per case, and persisted pipeline links in
  `tests/test_evaluation_runner.py`.
- [X] T011 [P] [US1] Add failing `clinical-doc-eval run` CLI tests for saved,
  generated, output paths, and exit code `0` in `tests/test_evaluation_cli.py`.

### Implementation for User Story 1

- [X] T012 [US1] Implement saved-mode evaluation and artifact-link validation in
  `src/clinical_doc_assist/evaluation/runner.py`.
- [X] T013 [US1] Implement generated-mode evaluation through an injected feature
  006 orchestration protocol in
  `src/clinical_doc_assist/evaluation/runner.py`.
- [X] T014 [US1] Implement atomic evaluation-run persistence and the `run`
  subcommand in `src/clinical_doc_assist/evaluation/runner.py` and
  `src/clinical_doc_assist/evaluation/cli.py`.

**Checkpoint**: All fixed cases produce linked, persistable baseline results.

---

## Phase 4: User Story 2 - Measure Retrieval and Answer Quality Separately (Priority: P1)

**Goal**: Compute per-case and aggregate retrieval, citation, faithfulness-proxy,
refusal, latency, usage, failure, and verdict results.

**Independent Test**: Evaluate one supported, one retrieval-miss, one
forbidden-statement, one false-answer, and one over-refusal case; verify each
failure is attributed to the correct stage.

### Tests for User Story 2

- [X] T015 [P] [US2] Add failing retrieval hit@k, recall@k, and MRR tests in
  `tests/test_evaluation_metrics.py`.
- [X] T016 [P] [US2] Add failing citation coverage, required key-point,
  forbidden-statement, refusal, failure-code, aggregate, and verdict tests in
  `tests/test_evaluation_metrics.py`.

### Implementation for User Story 2

- [X] T017 [US2] Implement normalized deterministic metrics in
  `src/clinical_doc_assist/evaluation/metrics.py`.
- [X] T018 [US2] Implement failure diagnosis, intervention mapping, aggregate
  values, and exact-key evaluation verdict generation in
  `src/clinical_doc_assist/evaluation/metrics.py`.
- [X] T019 [US2] Integrate per-case metrics, diagnoses, aggregates, and verdict
  artifacts into `src/clinical_doc_assist/evaluation/runner.py`.

**Checkpoint**: P1 MVP now reports attributable retrieval and answer metrics.

---

## Phase 5: User Story 3 - Compare One Controlled Improvement (Priority: P2)

**Goal**: Compare compatible baseline/candidate reports with exactly one declared
configuration change.

**Independent Test**: Compare reports differing only in retrieval limit and verify
metric deltas and the changed variable; reject two-variable or mismatched case-set
comparisons.

### Tests for User Story 3

- [X] T020 [P] [US3] Add failing one-variable, mismatched-version, missing-case, and
  multi-variable comparison tests in
  `tests/test_evaluation_comparison.py`.
- [X] T021 [P] [US3] Add failing `clinical-doc-eval compare` CLI and output tests
  in `tests/test_evaluation_cli.py`.

### Implementation for User Story 3

- [X] T022 [US3] Implement configuration delta detection, compatibility checks,
  metric/latency/cost deltas, and comparison persistence in
  `src/clinical_doc_assist/evaluation/comparison.py`.
- [X] T023 [US3] Implement the `compare` subcommand in
  `src/clinical_doc_assist/evaluation/cli.py`.

**Checkpoint**: Baseline and one-variable candidate reports can be compared.

---

## Phase 6: User Story 4 - Render a Human-Readable Answer View (Priority: P2)

**Goal**: Render deterministic plain text under 1,000 words with a 180-word
extractive summary, every claim, deduplicated sources, status, and exact-match
evaluation verdict.

**Independent Test**: Render the linked fixture answer and verify plain text,
summary/word limits, complete claim coverage, stable source markers, no raw model
output, and correct evaluated/unevaluated status.

### Tests for User Story 4

- [X] T024 [P] [US4] Add failing tests for extractive summary, claim completeness,
  source first-appearance numbering, URL/NCT deduplication, and section aggregation
  in `tests/test_evaluation_presentation.py`.
- [X] T025 [P] [US4] Add failing tests for 180-word summary, 999-word total,
  explicit oversize failure, no raw model output, absent/matching/mismatched
  verdicts, abstention, and failure views in
  `tests/test_evaluation_presentation.py`.
- [X] T026 [P] [US4] Add failing `clinical-doc-present` and
  `clinical-doc-eval review` CLI tests in `tests/test_evaluation_cli.py`.

### Implementation for User Story 4

- [X] T027 [US4] Implement the deterministic source map and extractive renderer in
  `src/clinical_doc_assist/evaluation/presentation.py`.
- [X] T028 [US4] Implement exact verdict matching, word limits, plain-text
  persistence, presentation metadata, and status-specific views in
  `src/clinical_doc_assist/evaluation/presentation.py`.
- [X] T029 [US4] Implement presentation-review validation, persistence, the
  `present` subcommand, and the `review` subcommand in
  `src/clinical_doc_assist/evaluation/cli.py`.

**Checkpoint**: Saved answers can be rendered and human-reviewed without modifying
the source artifacts.

---

## Phase 7: Polish and Cross-Cutting Concerns

- [X] T030 [P] Update `README.md` and
  `specs/007-rag-evaluation/quickstart.md` with implemented commands, output
  artifacts, evaluation limitations, and presentation behavior.
- [X] T031 [P] Add evaluation and presentation to `CHANGELOG.md`.
- [X] T032 Add the opt-in Docker evaluation integration test in
  `tests/integration/test_evaluation_stack.py`, then run
  `./.venv/Scripts/python.exe -m pytest -o addopts= -q` and
  `./.venv/Scripts/python.exe -m ruff check .`; resolve every failure.
- [X] T033 Review feature 007 for readability and failure handling; consolidate
  artifact I/O, reject malformed linked artifacts and verdicts, validate metadata
  citations and comparison inputs, support Windows UTF-8 BOM JSON, and restore
  module-level presentation dispatch.
- [X] T034 Persist the project-owner-requested AI-assisted five-case readability
  review, record its 9/10 result and transparency limitations, and identify the
  missing multi-source/conflicting-evidence scenarios.

---

## Dependencies and Execution Order

### Phase Dependencies

- Setup starts immediately.
- Foundational work depends on Setup and blocks stories.
- US1 and US2 are both P1 and together form the MVP.
- US3 depends on US1/US2 report structures.
- US4 depends on US1/US2 verdict structures.
- Polish depends on all implemented stories.

### Story Dependencies

- **US1**: Foundation only; establishes case-to-pipeline evaluation.
- **US2**: Foundation plus US1 case results; adds attribution metrics.
- **US3**: US1 and US2; compares complete reports.
- **US4**: US1 and US2; renders linked artifacts and verdicts.

Service, metrics, presentation, and CLI files are shared. Implement stories
sequentially even when selected test tasks are parallel.

### Parallel Opportunities

- T003/T004, then T006/T007/T008 after T005.
- Test tasks are parallel within each story.
- T030/T031 can run in parallel after implementation.

---

## Implementation Strategy

### MVP

1. Setup and Foundation.
2. US1 saved/generated baseline.
3. US2 attribution metrics and verdicts.
4. Validate the combined P1 evaluation baseline.

### Incremental Delivery

1. Fixed cases and linked artifacts.
2. Per-stage metrics and reproducible baseline.
3. Controlled comparison.
4. Plain-text presentation and human review.
5. Documentation, integration, tests, and lint.

## Notes

- Evaluation and presentation are read-only.
- No LLM judge or automatic prompt rewriting is introduced.
- No trust percentage is persisted or displayed.
- Implementation must remain below the agreed word limits without claim loss.
