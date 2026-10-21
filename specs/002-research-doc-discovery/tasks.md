---
description: "Implementation tasks for research document discovery"
---

# Tasks: Research Document Discovery and Screening

**Input**: Design documents from `specs/002-research-doc-discovery/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), and [contracts/cli.md](contracts/cli.md)

**Tests**: Included because deterministic validation and offline verification are
constitutional requirements.

## Phase 1: Setup

**Purpose**: Add only the dependency and command entry needed by the feature.

- [X] T001 Add `httpx` and the `clinical-doc-discover` script entry point in `pyproject.toml`
- [X] T002 Create the research package and test files: `src/clinical_doc_assist/research/__init__.py`, `src/clinical_doc_assist/research/models.py`, `src/clinical_doc_assist/research/prompts.py`, `src/clinical_doc_assist/research/clinical_trials.py`, `src/clinical_doc_assist/research/screening.py`, `src/clinical_doc_assist/research/agent.py`, `src/clinical_doc_assist/research/cli.py`, and `tests/test_research_models.py`, `tests/test_clinical_trials.py`, `tests/test_research_agent.py`, `tests/test_research_screening.py`, `tests/test_research_cli.py`

---

## Phase 2: Foundational

**Purpose**: Shared records and prompts required by every story.

- [X] T003 Write failing tests for `DiscoveryRequest`, `ResearchCandidate`, `ScreeningDecision`, and `DiscoveryRun` serialization and validation in `tests/test_research_models.py`
- [X] T004 Implement validated dataclasses and JSON serialization in `src/clinical_doc_assist/research/models.py`; enforce topic length 1-500, inclusive not-reversed dates, and limit 1-20
- [X] T005 Implement the researcher system prompt and user-prompt builder in `src/clinical_doc_assist/research/prompts.py`, including tool order, source policy, untrusted candidate text, fixed date window, and stop-before-ingestion rules

**Checkpoint**: Shared records and prompts are ready.

---

## Phase 3: User Story 1 - Discover Relevant Research Candidates (Priority: P1)

**Goal**: Return normalized, authoritative candidates from ClinicalTrials.gov.

**Independent Test**: Use a mocked HTTP response to verify the exact request
parameters, stable candidate fields, canonical source link, and explicit no-results
state without any model call.

### Tests

- [X] T006 [P] [US1] Write mocked contract tests for query/date parameters, selected response fields, candidate normalization, canonical URLs, malformed payloads, and HTTP failures in `tests/test_clinical_trials.py`

### Implementation

- [X] T007 [US1] Implement the ClinicalTrials.gov v2 adapter in `src/clinical_doc_assist/research/clinical_trials.py` using `httpx`, the verified `filter.advanced=AREA[LastUpdatePostDate]RANGE[...]` filter, and the fields listed in `data-model.md`

**Checkpoint**: Candidate discovery works independently with a mocked public source.

---

## Phase 4: User Story 2 - Use Current Time for Recency (Priority: P1)

**Goal**: Record UTC time before search and block search when the clock fails.

**Independent Test**: With fakes, verify ISO 8601 UTC output, search denial before
the clock call, search permission after it, and zero searches on clock failure.

### Tests

- [X] T008 [US2] Write tests for current-time formatting, injected clock failure, clock-before-search enforcement, and the successful transition to search in `tests/test_research_agent.py`

### Implementation

- [X] T009 [US2] Implement the `get_current_datetime` handler and an injected UTC clock in `src/clinical_doc_assist/research/agent.py`
- [X] T010 [US2] Implement the search gate in `src/clinical_doc_assist/research/agent.py`, requiring a successful clock result before the ClinicalTrials tool can run

**Checkpoint**: Current-time control works independently and introduces no network dependency.

---

## Phase 5: User Story 3 - Screen and Explain Candidates (Priority: P2)

**Goal**: Combine model reflection with deterministic screening and emit one
inspectable discovery run.

**Independent Test**: Use fake model decisions and candidate metadata to verify
accepted, rejected, and needs-review outputs, reason codes, duplicate detection,
deterministic precedence, and the CLI JSON contract.

### Tests

- [X] T011 [P] [US3] Write screening tests for `approved_source`, `within_date_window`, `unique_identifier`, `relevant_topic`, `off_topic`, `missing_identifier`, `invalid_date`, `outside_date_window`, `duplicate`, `ambiguous_metadata`, and `missing_reflection` in `tests/test_research_screening.py`
- [X] T012 [P] [US3] Write model-loop tests for candidate retention from tool output, malformed final JSON, missing decisions, deterministic rejection precedence, max-step failure, and complete run assembly in `tests/test_research_agent.py`
- [X] T013 [P] [US3] Write CLI contract tests for valid JSON, `completed`, `no_results`, argument errors, source failures, and stdout/stderr separation in `tests/test_research_cli.py`

### Implementation

- [X] T014 [US3] Implement deterministic validation and final status resolution in `src/clinical_doc_assist/research/screening.py`, ensuring model output cannot override source, date, identifier, or duplicate rejections
- [X] T015 [US3] Implement the bounded OpenAI Chat Completions tool loop and advisory reflection parsing in `src/clinical_doc_assist/research/agent.py`; retain authoritative candidates from executed tool calls and stop before ingestion
- [X] T016 [US3] Implement `clinical-doc-discover` argument validation, JSON output, and exit codes in `src/clinical_doc_assist/research/cli.py` according to `contracts/cli.md`
- [X] T017 [US3] Export the public research API from `src/clinical_doc_assist/research/__init__.py` without changing the existing provisional package interfaces

**Checkpoint**: The first feature runs end-to-end and stops after screening.

---

## Phase 6: Polish and Verification

- [X] T018 [P] Update `README.md` and `CHANGELOG.md` with the discovery command, JSON output boundary, and live-network requirement
- [X] T019 Run `pytest`, `ruff check .`, `clinical-doc-discover --help`, and the mocked quickstart scenarios in `specs/002-research-doc-discovery/quickstart.md`
- [X] T020 Review the implementation against `spec.md` and `plan.md`, remove unnecessary abstractions, and confirm no ingestion, retrieval, answering, multi-agent, database, or monitoring scope was added
- [X] T021 Apply readability refactors in `src/clinical_doc_assist/research/models.py`, `src/clinical_doc_assist/research/agent.py`, and `src/clinical_doc_assist/research/cli.py`: fix the JSON return annotation, add a typed `ToolResult`, narrow provider errors, remove the redundant exception hierarchy, and introduce status and reason-code aliases
- [X] T022 Verify readability refactors with `pytest`, Ruff lint, Ruff formatting, and editor diagnostics across the research package and its tests
- [X] T023 Add `schema_version` and `run_id` to `DiscoveryRun` serialization in `src/clinical_doc_assist/research/models.py`
- [X] T024 Add atomic `--output PATH` persistence to `src/clinical_doc_assist/research/cli.py`, writing only valid non-failed runs
- [X] T025 Add tests for artifact schema, run identity, successful output persistence, failed-run output suppression, and Unicode-safe stdout in `tests/test_research_models.py`, `tests/test_research_agent.py`, and `tests/test_research_cli.py`
- [X] T026 Update feature documentation and `.env.example` for persisted artifacts and `deepseek-flash`
- [X] T027 Run three focused live discovery requests and persist schema-versioned artifacts under `artifacts/discovery/`

---

## Dependencies and Execution Order

- T002 through T005 require T001 and T002.
- T006-T007 require the shared records from T003-T005.
- T008-T010 require T007 and the shared records.
- T011-T017 require T007 and T010.
- T018-T020 require T017.

US1 can be verified independently with a mocked HTTP client. US2 builds on the
source adapter but remains independently testable with fakes. US3 completes the
end-to-end feature.

## Parallel Opportunities

- T011, T012, and T013 use separate files and can be written in parallel after
  T010.
- T018 can proceed after the public CLI behavior is stable while T019-T020 run.

## MVP Scope

US1 and US2 together form the minimum useful collection pipeline: one approved
source and an auditable current-time gate. US3 adds the required screening and
user-visible result, so the feature is not complete until all three stories pass.

## Implementation Strategy

1. Complete setup and shared records.
2. Verify source discovery with mocks.
3. Add and enforce current-time ordering.
4. Add deterministic screening and agent integration.
5. Add the JSON CLI, run documentation, and complete offline verification.
