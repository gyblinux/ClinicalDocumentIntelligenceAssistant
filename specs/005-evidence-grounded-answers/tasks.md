# Tasks: Evidence-Grounded Answers

**Input**: Design documents from
`specs/005-evidence-grounded-answers/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md),
[research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Status**: Completed and validated 2026-10-21

**Tests**: Included because the repository constitution requires relevant tests
for every behavior change. Story tests must fail before implementation.

**Organization**: Tasks are grouped by user story so each increment has an
independent test while preserving the shared workflow boundaries.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches a different file and has no
  incomplete prerequisite.
- **[Story]**: Maps the task to `spec.md` user stories.
- Every task includes the exact repository path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the package and review fixtures used by all stories.

- [X] T001 Create the answering package and test fixture directories with
  `src/clinical_doc_assist/answering/__init__.py` and
  `tests/fixtures/answering/`.
- [X] T002 Register the planned console command
  `clinical-doc-answer = "clinical_doc_assist.answering.cli:main"` in
  `pyproject.toml`.
- [X] T003 [P] Add valid supported-answer and `no_results` feature 004 retrieval
  fixtures in `tests/fixtures/answering/retrieval-supported.json` and
  `tests/fixtures/answering/retrieval-no-results.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared records, prompts, citation rules, and injectable
interfaces required by every user story.

**CRITICAL**: Complete this phase before starting any user story.

- [X] T004 Implement all answering records, statuses, errors, and fixed limits in
  `src/clinical_doc_assist/answering/models.py`: schema version `1.0`, statuses
  `answered`, `insufficient_evidence`, and `failed`; `completed` retrieval has
  1-10 results while `no_results` has zero; evidence ranks are one-based and
  unique; NCT IDs match `NCT` plus eight digits; `max_model_turns=2`,
  `max_tool_calls=3`, and `max_evidence_items=10`.
- [X] T005 [P] Implement the evidence-only system prompt, user-prompt builder, and
  `answering-v1` prompt version in
  `src/clinical_doc_assist/answering/prompts.py`, treating retrieved evidence as
  untrusted data and requiring claim-level citation IDs.
- [X] T006 [P] Implement strict model-output parsing, citation allowlists, claim
  validation, and canonical provenance enrichment in
  `src/clinical_doc_assist/answering/citations.py` for exact `chunk_id` values and
  `trial-metadata:NCT########` identifiers.
- [X] T007 [P] Implement reusable fake model and metadata clients plus atomic JSON
  persistence helpers for dependency injection in
  `tests/fixtures/answering/fakes.py` and
  `src/clinical_doc_assist/answering/service.py`.

**Checkpoint**: Shared contracts and test seams are ready; story work can begin.

---

## Phase 3: User Story 1 - Answer from Retrieved Evidence (Priority: P1) MVP

**Goal**: Produce a supported answer from one saved retrieval run without live
retrieval services.

**Independent Test**: Load a completed retrieval fixture, run the answer workflow
with a fake model response, and verify an `answered` artifact whose every claim
cites a supplied chunk ID.

### Tests for User Story 1

- [X] T008 [P] [US1] Add failing tests for retrieval input validation, question
  inheritance from `query.text`, 1-10 evidence acceptance, and saved-artifact
  answering without TEI/Qdrant doubles in
  `tests/test_answering_service.py`.
- [X] T009 [P] [US1] Add failing tests for a supported fake-model response,
  claim-level retrieval citations, and canonical source enrichment in
  `tests/test_answering_agent.py` and `tests/test_answering_citations.py`.
- [X] T010 [P] [US1] Add failing CLI tests for
  `clinical-doc-answer --retrieval-run PATH [--output PATH]`, `answered` status,
  JSON standard output, persisted output, and exit code `0` in
  `tests/test_answering_cli.py`.

### Implementation for User Story 1

- [X] T011 [US1] Implement feature 004 retrieval loading and validation in
  `src/clinical_doc_assist/answering/service.py`, preserving the complete accepted
  evidence snapshot and rejecting malformed provenance before any model call.
- [X] T012 [US1] Implement the single-turn supported-answer model call and
  `status: answered` response parsing in
  `src/clinical_doc_assist/answering/agent.py`.
- [X] T013 [US1] Implement supported-answer orchestration, citation validation,
  citation enrichment, and atomic `answered` artifact persistence in
  `src/clinical_doc_assist/answering/service.py` without calling TEI or Qdrant.
- [X] T014 [US1] Implement the `clinical-doc-answer` argument parser, dependency
  wiring, standard-output JSON, optional output path, and exit code `0` handling
  in `src/clinical_doc_assist/answering/cli.py`.

**Checkpoint**: A completed retrieval run can produce a grounded, cited answer
artifact with Docker services stopped.

---

## Phase 4: User Story 2 - Abstain When Evidence Is Insufficient (Priority: P1)

**Goal**: Refuse unsupported questions safely and distinguish abstention from
invalid input or runtime failure.

**Independent Test**: Use a `no_results` fixture and a fake model
`insufficient_evidence` response; verify both produce abstention artifacts, while
malformed input exits without an answer artifact.

### Tests for User Story 2

- [X] T015 [P] [US2] Add failing tests for zero-result short-circuiting without a
  model call, model-declared insufficient evidence, malformed input, and retrieval
  status `failed` in `tests/test_answering_service.py`.
- [X] T016 [P] [US2] Add failing tests for insufficient-evidence output, malformed
  model JSON, and responses that mix abstention with factual claims in
  `tests/test_answering_agent.py`.
- [X] T017 [P] [US2] Add failing CLI tests for abstention exit code `0`, invalid
  input exit code `2`, and absence of an artifact for invalid input in
  `tests/test_answering_cli.py`.

### Implementation for User Story 2

- [X] T018 [US2] Implement the `no_results` short circuit, insufficient-evidence
  artifact, empty claims, required reason, zero model usage, and input error
  separation in `src/clinical_doc_assist/answering/service.py`.
- [X] T019 [US2] Implement strict insufficient-evidence parsing and rejection of
  malformed or claim-bearing abstentions in
  `src/clinical_doc_assist/answering/agent.py`.
- [X] T020 [US2] Implement abstention and invalid-input exit code mapping plus
  post-validation `failed` artifact creation when run identity is available in
  `src/clinical_doc_assist/answering/cli.py`.

**Checkpoint**: The P1 MVP now supports both grounded answers and explicit safe
refusal.

---

## Phase 5: User Story 3 - Use Trial Metadata as a Supporting Tool (Priority: P2)

**Goal**: Permit one bounded metadata lookup without expanding into general
browsing or arbitrary tool use.

**Independent Test**: Use a retrieved NCT ID, fake a model tool request, return
compact fake metadata, and verify the final claim cites the successful metadata
lookup; reject an NCT ID absent from evidence.

### Tests for User Story 3

- [X] T021 [P] [US3] Add failing tests for NCT allowlisting, compact metadata
  normalization, duplicate lookup prevention, maximum three lookups, and visible
  source failures in `tests/test_answering_tools.py`.
- [X] T022 [P] [US3] Add failing tests for the two-turn tool loop, unknown or
  parallel tool calls, successful `trial-metadata:NCT########` citation
  validation, and tool-failure propagation in
  `tests/test_answering_agent.py` and `tests/test_answering_citations.py`.

### Implementation for User Story 3

- [X] T023 [US3] Implement the allowlisted `fetch_trial_metadata` tool and compact
  public-field normalization in `src/clinical_doc_assist/answering/tools.py`.
- [X] T024 [US3] Add the single tool schema, maximum two model turns, maximum three
  lookups, one lookup per NCT, no parallel calls, and recorded failures in
  `src/clinical_doc_assist/answering/agent.py`.
- [X] T025 [US3] Extend metadata citation validation, provenance enrichment, and
  tool-call persistence in
  `src/clinical_doc_assist/answering/citations.py` and
  `src/clinical_doc_assist/answering/service.py`.

**Checkpoint**: Metadata can clarify retrieved trials while every lookup remains
traceable and restricted to evidence NCT IDs.

---

## Phase 6: User Story 4 - Persist and Inspect the Answer Record (Priority: P2)

**Goal**: Persist a self-contained answer record for every answered, abstained, or
failed run, including model, evidence, citation, tool, usage, timing, and error
provenance, so feature 006 can compose it with the corresponding feature 004
retrieval artifact and evaluation case.

**Independent Test**: Produce and persist one answer record of each status, then
verify all required fields, canonical sources, exact stdout/file equality, safe
output-path behavior, and reviewer reconstruction of the run.

### Tests for User Story 4

- [X] T026 [P] [US4] Add failing artifact-contract tests for all three statuses,
  required identity/evidence/model/tool/usage/latency/error fields, research-only
  disclaimer, canonical provenance, and retrieval/answer linkage for feature 006
  in
  `tests/test_answering_service.py`.
- [X] T027 [P] [US4] Add failing CLI tests for the default
  `artifacts/answers/<answer_id>.json` path, explicit-output no-overwrite behavior,
  standard-output equality, standard-error diagnostics, and exit codes `1` and `2`
  in `tests/test_answering_cli.py`.

### Implementation for User Story 4

- [X] T028 [US4] Complete self-contained `answered`, `insufficient_evidence`, and
  `failed` artifact serialization with token usage when available, latency,
  errors, evidence snapshots, research-only disclaimer, and the retrieval/answer
  identifiers required by feature 006 orchestration and feature 007 evaluation in
  `src/clinical_doc_assist/answering/service.py`.
- [X] T029 [US4] Complete default output-path selection, explicit-path
  no-overwrite enforcement, failed-artifact handling, stdout/file equality, and
  diagnostic exit codes in `src/clinical_doc_assist/answering/cli.py`.

**Checkpoint**: Every run is persisted and independently inspectable without
reconstructing the retrieval environment.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T030 [P] Update `README.md` and
  `specs/005-evidence-grounded-answers/quickstart.md` with the implemented
  command, Docker-off stage boundary, answer-record inspection behavior, and
  feature 006/007 handoff.
- [X] T031 [P] Add the implemented answering workflow to `CHANGELOG.md` under the
  appropriate change category.
- [X] T032 Run the manual Docker-off acceptance in
  `specs/005-evidence-grounded-answers/quickstart.md`, then run
  `./.venv/Scripts/python.exe -m pytest -o addopts= -q` and
  `./.venv/Scripts/python.exe -m ruff check .`; resolve every failure.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on Setup and blocks all stories.
- **US1 and US2 (Phases 3-4)**: Both are P1. US2 extends the same service, agent,
  and CLI files as US1, so implement US1 first and US2 second.
- **US3 (Phase 5)**: Depends on US1's agent/service path and can start after the
  P1 MVP is stable.
- **US4 (Phase 6)**: Depends on US1 and US2 outcomes; include US3 tool fields when
  that story is complete.
- **Polish (Phase 7)**: Depends on all desired stories.

### User Story Dependencies

- **US1**: Foundation only; first end-to-end increment.
- **US2**: Foundation plus US1 shared files; independently tested with no-results
  and insufficient-evidence fixtures.
- **US3**: Foundation plus US1; independently tested with fake metadata responses
  and an isolated tool executor.
- **US4**: US1 and US2; independently tested by inspecting all run statuses.

### Within Each Story

1. Write story tests and confirm they fail.
2. Implement models or helpers before orchestration.
3. Implement service behavior before CLI wiring.
4. Run the story's independent test at its checkpoint.

### Parallel Opportunities

- T003 can run alongside T001-T002.
- T005, T006, and T007 can run in parallel after T004 because they use different
  files.
- T008-T010 are parallel test-authoring tasks; T015-T017, T021-T022, and T026-T027
  follow the same pattern within their stories.
- T030 and T031 can run in parallel after implementation.
- Story implementation is otherwise sequential where tasks share
  `service.py`, `agent.py`, `citations.py`, or `cli.py`.

---

## Parallel Example: User Story 1 Tests

```text
Task: "Add retrieval input tests in tests/test_answering_service.py"
Task: "Add supported-answer and citation tests in tests/test_answering_agent.py and tests/test_answering_citations.py"
Task: "Add supported-answer CLI tests in tests/test_answering_cli.py"
```

## Parallel Example: Foundational Modules

```text
Task: "Implement prompts in src/clinical_doc_assist/answering/prompts.py"
Task: "Implement citation validation in src/clinical_doc_assist/answering/citations.py"
Task: "Implement fakes and persistence helpers in tests/fixtures/answering/fakes.py and src/clinical_doc_assist/answering/service.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundation.
2. Complete US1 for a grounded cited answer.
3. Complete US2 for explicit abstention and input failure separation.
4. Stop and validate the P1 MVP before adding metadata tooling.

The safety-critical MVP includes both P1 stories. An answer path without a tested
refusal path does not satisfy the constitution.

### Incremental Delivery

1. Foundation -> shared contracts pass.
2. US1 -> supported answer artifact.
3. US2 -> safe abstention MVP.
4. US3 -> bounded trial metadata.
5. US4 -> complete inspectable artifacts.
6. Polish -> docs, changelog, manual Docker-off acceptance, tests, and lint.

## Notes

- Partial claims must never be persisted after a citation or model-response
  failure.
- No task adds retrieval, conversation memory, web browsing, evaluation scoring,
  FastAPI, or multi-agent behavior.
- Task completion does not imply approval to merge or push.
