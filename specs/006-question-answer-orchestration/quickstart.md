# Quickstart: Question-to-Answer Orchestration

**Status**: Implemented; offline tests and an opt-in Docker integration test cover
the composition flow

**Observed result**: The opt-in integration test passed on 2026-10-21 using the
real local TEI/Qdrant retrieval stack and a deterministic fake answering stage.
The test collection was removed and both containers were stopped afterward.

## Prerequisites

- Feature 003 corpus already indexed in feature 004
- Docker Desktop running TEI and Qdrant
- `DEEPSEEK_API_KEY` configured in the ignored `.env`
- Python project dependencies installed

## Start Retrieval Services

```bash
cd /c/Users/gybsa/repos/clinical_doc_assist
docker compose up -d
docker compose ps
```

## Ask One Question

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.orchestration.cli \
  "What did NCT07424430 aim to evaluate?" \
  --collection clinical_evidence_v1 \
  --limit 5
```

Expected standard output is one pipeline JSON record. Three artifacts should be
inspectable:

```text
artifacts/retrieval/<retrieval_id>.json
artifacts/answers/<answer_id>.json
artifacts/pipelines/<pipeline_id>.json
```

The question in both the retrieval artifact and answer record must match the
submitted question.

## Different Question

Run the command again with a different question. It must create new retrieval and
answer artifacts rather than reuse the previous ones.

## Verify Runtime Limits

- An empty question returns exit code `2`.
- Unavailable TEI or Qdrant produces a retrieval failure.
- No-results retrieval produces `insufficient_evidence` without a model call.
- Unsupported but well-cited claims may still be returned; semantic faithfulness
  is measured offline by feature 007.

## Tests

```bash
./.venv/Scripts/python.exe -m pytest -o addopts= -q
./.venv/Scripts/python.exe -m ruff check .
```

The default suite uses injected fakes and requires neither Docker nor provider
network access.

Run the opt-in Docker retrieval integration with fake answering:

```bash
RUN_DOCKER_INTEGRATION=1 ./.venv/Scripts/python.exe -m pytest \
  tests/integration/test_orchestration_stack.py
```
