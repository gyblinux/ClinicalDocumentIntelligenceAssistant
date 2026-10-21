# Implementation Plan: Question-to-Answer Orchestration

**Branch**: `006-question-answer-orchestration` | **Date**: 2026-10-21 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/006-question-answer-orchestration/spec.md`

**Status**: Implemented and validated 2026-10-21

## Summary

Add one user-facing, single-question composition layer over the implemented
retrieval and answering stages. The command accepts a question, performs fresh
retrieval for that exact question, persists the retrieval artifact, invokes the
existing answer service, and writes a pipeline record linking both stage outputs.

The composition layer does not duplicate retrieval, prompting, citation
validation, abstention, or tool behavior. It also does not perform semantic
evaluation before returning an answer. Feature 005's deterministic checks remain
the runtime gate; feature 007 evaluates answer quality offline.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing `httpx`, `openai`, `python-dotenv`, and
`qdrant-client`; no new runtime framework

**Retrieval Stage**: Existing feature 004 `RetrievalService` with TEI and Qdrant

**Answer Stage**: Existing feature 005 `AnswerService`, DeepSeek client, citation
validator, and allowlisted metadata tool

**Input**: One non-empty question, collection name, and retrieval limit

**Storage**: Local JSON artifacts under `artifacts/retrieval/`,
`artifacts/answers/`, and `artifacts/pipelines/`

**Testing**: `pytest` with injected fake retrieval and answer services; Docker and
live-provider acceptance remains opt-in

**Target Platform**: Host Python CLI on Windows; TEI and Qdrant run through Docker
Desktop/WSL2

**Project Type**: Single Python package with a `clinical-doc-ask` CLI

**Performance Goals**: One question per invocation, default five retrieved
evidence items, and recorded stage/total latency without a hard provider SLA

**Constraints**: Fresh retrieval for every question, no conversation memory, no
query rewriting, no evaluation scoring, no answer mutation, and no evidence reuse
across questions

**Scale/Scope**: One user, one public corpus, one vector collection, one question,
and at most 10 evidence items passed into answering

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Public evidence only**: Questions are answered only from the public corpus
  retrieved through feature 004; no browsing or private records are introduced.
- **Evidence-grounded answers**: Feature 005 remains the only answer generator and
  retains claim-level citation validation and abstention.
- **Reproducible evaluation**: The pipeline record links the question, retrieval
  artifact, answer record, configuration, timings, and errors for feature 007.
- **Independent stages**: Feature 006 composes existing services but keeps their
  artifact outputs separately inspectable and does not perform evaluation scoring.
- **Small scope**: One composition package, one CLI, and no new agent, prompt,
  retriever, evaluator, database, or service.

No constitutional violations or exceptions are required.

## Project Structure

### Documentation

```text
specs/006-question-answer-orchestration/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- cli.md
|   |-- artifacts.md
|   `-- services.md
`-- checklists/
    `-- requirements.md
```

### Source Code

```text
src/clinical_doc_assist/orchestration/
|-- __init__.py
|-- models.py       # Question request, stage links, pipeline record, errors
|-- service.py      # Compose retrieval and answering, persist linked artifacts
`-- cli.py          # clinical-doc-ask

tests/
|-- fixtures/orchestration/
|-- test_orchestration_models.py
|-- test_orchestration_service.py
|-- test_orchestration_cli.py
`-- integration/test_orchestration_stack.py
```

**Structure Decision**: Add a small `orchestration/` package. It imports existing
retrieval and answering services through protocols rather than duplicating their
logic or executing their CLIs as subprocesses.

## Design

### Request Boundary

One request contains:

- A non-empty question.
- A non-empty collection name.
- A retrieval limit from 1-50.

The question is passed unchanged to retrieval. The answer stage reads the same
question from the persisted retrieval artifact, so the interface cannot silently
answer a different question.

### Composition Flow

```text
question request
  -> feature 004 search
  -> persist retrieval artifact
  -> feature 005 answer from that artifact
  -> persist answer record
  -> persist pipeline record linking both stages
```

The orchestration service uses injected protocols:

- Retrieval: `search_evidence(question, collection, limit) -> RetrievalRun`
- Answering: `answer(retrieval_path, output=None) -> AnswerOutcome`

This allows complete offline tests without Docker or provider calls.

### Artifact Paths

Default paths:

```text
artifacts/retrieval/<retrieval_id>.json
artifacts/answers/<answer_id>.json
artifacts/pipelines/<pipeline_id>.json
```

The retrieval artifact is written atomically before answering. The answer record
is created by feature 005. The pipeline record is written after the stage outcome
is known. Existing files are never silently overwritten.

### Pipeline Status

- `answered`: retrieval completed and feature 005 returned an answer.
- `insufficient_evidence`: retrieval or answering explicitly abstained.
- `failed`: retrieval, answering, artifact persistence, or linkage failed.

Stage statuses remain visible separately from the overall pipeline status.

### Question-Specific Evidence

Every invocation creates a new retrieval run. The interface never accepts a prior
answer as context and never reuses a previous retrieval artifact. Asking the same
question again still creates a new run so timings, index state, and results remain
traceable.

### Runtime and Offline Boundaries

Runtime checks in feature 006 are limited to:

- Input validation.
- Retrieval/reporting failures.
- Feature 005 abstention and citation validation.
- Artifact persistence and consistency checks.

Feature 006 does not judge semantic faithfulness and does not retract an answer
after returning it. A separate feature 007 evaluation reads saved pipeline records
and assigns quality scores without modifying the original artifacts.

### Failure Handling

- Retrieval error: persist a failed pipeline record; do not invoke answering.
- No retrieval results: persist empty retrieval and insufficient-evidence answer
  records; no answer-model call.
- Answer model/citation failure: persist the retrieval and failed answer records;
  mark the pipeline failed.
- Pipeline artifact write failure: return a concise CLI failure and preserve
  stage artifacts that were already written.
- Invalid input or unsafe output path: fail before invoking any service.

### CLI

```text
clinical-doc-ask "QUESTION" \
  --collection clinical_evidence_v1 \
  [--limit 5] \
  [--pipeline-dir artifacts/pipelines]
```

Standard output is one pipeline JSON object. The pipeline record includes the
answer claims, abstention reason, or failure, plus links to the full retrieval and
answer records.

Exit codes:

- `0`: `answered` or `insufficient_evidence`
- `1`: valid question but retrieval, answering, or artifact persistence failed
- `2`: invalid question, arguments, configuration, or unsafe output path

### Configuration Snapshot

The pipeline record captures:

- Collection and retrieval limit
- Embedding model and embedding dimension
- Answer model and prompt version
- Retrieval ID and artifact path
- Answer ID and artifact path when created
- Timing for each stage
- Source errors and model errors

No API key or secret value is persisted.

### Feature 007 Handoff

Feature 007 uses one pipeline record per fixed evaluation case. It reads the
underlying retrieval artifact for retrieval metrics and the answer record for
answer metrics. Evaluation results reference, but never mutate, the original
answer or pipeline record.

## Testing Strategy

- Request validation and exact question propagation.
- Fresh retrieval on repeated invocations.
- Retrieval completed, no-results, and failure paths.
- Answer answered, insufficient-evidence, and failed paths.
- Pipeline record linkage and configuration snapshot.
- No answer-model call after no-results retrieval.
- No answer reuse across questions.
- Atomic stage artifact persistence and no-overwrite behavior.
- CLI JSON, exit codes, and concise diagnostics.
- Optional Docker integration with fake answering.
- Optional live acceptance with both provider and retrieval services.

## Complexity Tracking

No violations. The new package composes two tested services and adds one artifact
contract. It deliberately avoids a second prompt, retrieval implementation, model
loop, evaluator, API server, and agent framework.

## Phase Outputs

- Phase 0: [research.md](research.md)
- Phase 1: [data-model.md](data-model.md)
- Phase 1: [CLI contract](contracts/cli.md)
- Phase 1: [artifact contract](contracts/artifacts.md)
- Phase 1: [service contract](contracts/services.md)
- Phase 1: [quickstart.md](quickstart.md)

## Deferred

- Query rewriting and reranking
- Conversation history or chat sessions
- Runtime semantic-faithfulness verification
- Automatic prompt rewriting
- Evaluation scoring
- FastAPI, UI, CI, production monitoring, and multi-agent orchestration

## Next Gate

Feature 006 is complete. Feature 007 remains at its specification gate and must
proceed through its own plan and task approvals.
