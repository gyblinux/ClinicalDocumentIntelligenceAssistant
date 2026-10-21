# Tasks: Question-to-Answer Orchestration

**Input**: Design documents from
`specs/006-question-answer-orchestration/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md),
[research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Status**: Completed and validated 2026-10-21

**Tests**: Included because the repository constitution requires relevant tests.

**Organization**: Tasks are grouped by user story so each increment remains
independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable across a different file with no incomplete dependency.
- **[Story]**: Maps to the user stories in `spec.md`.
- Every task includes an exact repository path.

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the orchestration package and test fixture directories with
  `src/clinical_doc_assist/orchestration/__init__.py` and
  `tests/fixtures/orchestration/__init__.py`.
- [X] T002 Register `clinical-doc-ask = "clinical_doc_assist.orchestration.cli:main"`
  in `pyproject.toml`.
- [X] T003 [P] Add deterministic question, retrieval, and answer fixtures in
  `tests/fixtures/orchestration/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**CRITICAL**: Complete this phase before any user story.

- [X] T004 Implement `QuestionRequest`, `StageStatus`, `PipelineStatus`,
  `ArtifactReference`, `StageTiming`, `ConfigurationSnapshot`, `AnswerSummary`,
  `PipelineRun`, `PipelineOutcome`, and orchestration errors in
  `src/clinical_doc_assist/orchestration/models.py`: question and collection are
  trimmed and non-empty; limit defaults to 5 and must be 1-50; pipeline statuses
  are `answered`, `insufficient_evidence`, and `failed`; timings are non-negative;
  secrets are never persisted.
- [X] T005 [P] Create retrieval and answering service protocols plus atomic JSON
  and project-relative path helpers in
  `src/clinical_doc_assist/orchestration/service.py`.
- [X] T006 [P] Add reusable fake retrieval and answer services in
  `tests/fixtures/orchestration/fakes.py`.

**Checkpoint**: Shared records, service seams, and fixtures are ready.

---

## Phase 3: User Story 1 - Ask a Corpus-Backed Question (Priority: P1) MVP

**Goal**: Accept one question, run fresh retrieval for that exact question, invoke
feature 005, and return a linked pipeline result.

**Independent Test**: Ask a supported question with fake services and verify that
retrieval receives the exact question, the answer service receives the persisted
retrieval path, and the returned pipeline is `answered`.

### Tests for User Story 1

- [X] T007 [P] [US1] Add failing tests for request normalization, exact question
  propagation, fresh retrieval, and the completed `answered` pipeline path in
  `tests/test_orchestration_service.py`.
- [X] T008 [P] [US1] Add failing CLI tests for the positional question,
  collection, limit, pipeline JSON standard output, and exit code `0` in
  `tests/test_orchestration_cli.py`.

### Implementation for User Story 1

- [X] T009 [US1] Implement the retrieval-to-answer composition service and
  persisted-retrieval handoff in
  `src/clinical_doc_assist/orchestration/service.py`.
- [X] T010 [US1] Implement `clinical-doc-ask` argument parsing, real retrieval and
  answer service wiring, JSON output, and exit code `0` in
  `src/clinical_doc_assist/orchestration/cli.py`.

**Checkpoint**: One supported user question produces a linked answered pipeline.

---

## Phase 4: User Story 2 - Inspect the Linked Pipeline Record (Priority: P1)

**Goal**: Persist a pipeline record that links the question, both stage artifacts,
configuration, timing, and answer summary.

**Independent Test**: Run two different questions and verify unique, correctly
linked retrieval/answer/pipeline artifacts with reproducible configuration and the
correct question in every record.

### Tests for User Story 2

- [X] T011 [P] [US2] Add failing tests for artifact links, configuration snapshot,
  answer summary, stage timing, and absence of secrets in
  `tests/test_orchestration_service.py`.
- [X] T012 [P] [US2] Add failing repeated-question tests proving each invocation
  produces fresh retrieval and does not reuse prior artifacts in
  `tests/test_orchestration_service.py`.

### Implementation for User Story 2

- [X] T013 [US2] Implement pipeline record construction, answer-summary extraction,
  configuration capture, and stage timing in
  `src/clinical_doc_assist/orchestration/models.py` and
  `src/clinical_doc_assist/orchestration/service.py`.
- [X] T014 [US2] Implement unique default artifact paths, no-overwrite checks, and
  atomic pipeline persistence in
  `src/clinical_doc_assist/orchestration/service.py`.

**Checkpoint**: Every run is inspectable and traceable to question-specific 004 and
005 artifacts.

---

## Phase 5: User Story 3 - Fail Clearly When the Pipeline Cannot Run (Priority: P2)

**Goal**: Distinguish invalid input, retrieval failure, no-results abstention,
answer failure, and output failure without fabricating an answer.

**Independent Test**: Inject each failure path and verify stage attribution,
preserved artifacts, pipeline status, and CLI exit code.

### Tests for User Story 3

- [X] T015 [P] [US3] Add failing tests for empty questions, invalid limits, unsafe
  paths, and validation before service calls in
  `tests/test_orchestration_models.py`.
- [X] T016 [P] [US3] Add failing tests for retrieval failure, no-results
  abstention, answer failure, and persistence failure in
  `tests/test_orchestration_service.py`.
- [X] T017 [P] [US3] Add failing CLI tests for exit codes `1` and `2`, concise
  standard-error diagnostics, and absence of unsupported output in
  `tests/test_orchestration_cli.py`.

### Implementation for User Story 3

- [X] T018 [US3] Implement request and output-path validation in
  `src/clinical_doc_assist/orchestration/models.py` and
  `src/clinical_doc_assist/orchestration/service.py`.
- [X] T019 [US3] Implement retrieval-failure, no-results, answer-failure, and
  artifact-persistence state transitions in
  `src/clinical_doc_assist/orchestration/service.py`.
- [X] T020 [US3] Implement CLI exit-code mapping and concise diagnostics in
  `src/clinical_doc_assist/orchestration/cli.py`.

**Checkpoint**: Every failure is attributable to a stage and no unsupported answer
is produced.

---

## Phase 6: Polish and Cross-Cutting Concerns

- [X] T021 [P] Update `README.md` and
  `specs/006-question-answer-orchestration/quickstart.md` with the implemented
  one-question workflow and feature 007 handoff.
- [X] T022 [P] Add the implemented orchestration workflow to `CHANGELOG.md`.
- [X] T023 Add an opt-in Docker integration test in
  `tests/integration/test_orchestration_stack.py`, then run
  `./.venv/Scripts/python.exe -m pytest -o addopts= -q` and
  `./.venv/Scripts/python.exe -m ruff check .`; resolve every failure.

---

## Dependencies and Execution Order

### Phase Dependencies

- Setup starts immediately.
- Foundational work depends on Setup and blocks all stories.
- User stories depend on Foundational completion.
- Polish depends on implemented user stories.

### Story Dependencies

- **US1**: Foundation only; first end-to-end increment.
- **US2**: Foundation plus US1's composition path.
- **US3**: Foundation plus US1/US2 artifact and status flow.

Because US1-US3 extend the same small service/CLI files, implement them
sequentially even where test-authoring tasks are marked `[P]`.

### Parallel Opportunities

- T003, T005, and T006 can proceed independently after T004.
- Test tasks T007/T008, T011/T012, and T015/T016/T017 are parallel within their
  stories.
- T021 and T022 can run in parallel after implementation.

---

## Implementation Strategy

### MVP

1. Complete Setup and Foundation.
2. Complete US1 to produce the first one-question pipeline.
3. Validate that question-specific retrieval and answering are linked.
4. Add US2 inspection guarantees and US3 failure handling.

### Incremental Delivery

1. Foundation -> contracts pass.
2. US1 -> direct one-question workflow.
3. US2 -> reproducible linked pipeline records.
4. US3 -> safe failure and abstention behavior.
5. Polish -> docs, changelog, tests, and optional integration.

## Notes

- No task changes feature 005's prompt or answer generation.
- No task adds conversation memory or evaluation scoring.
- Evaluation remains feature 007 and cannot modify or withdraw returned answers.
