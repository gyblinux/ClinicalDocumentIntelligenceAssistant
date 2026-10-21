# Quickstart: Evidence-Grounded Answers

**Status**: Implemented and manually accepted on 2026-10-21

**Observed result**: With no TEI or Qdrant containers running, the saved
`semaglutide-cardio.json` retrieval run produced an `answered` record with nine
claims, eight validated citations, three completed metadata lookups, and provider
usage of 4,463 input tokens and 1,596 output tokens. The live record is stored
under `artifacts/answers/` and is intentionally ignored by Git.

## Prerequisites

- A feature 004 retrieval artifact for the question to answer
- `DEEPSEEK_API_KEY` configured in the ignored `.env`
- Python environment with project dependencies
- Docker only when a retrieval artifact must be created or refreshed

The detailed JSON contract is in
[contracts/artifacts.md](contracts/artifacts.md).

## 1. Create or Reuse a Retrieval Run

If a retrieval artifact already exists for the desired question, skip to step 2.

```powershell
docker compose up -d

clinical-doc-retrieve search `
  "What did NCT07424430 aim to evaluate?" `
  --collection clinical_evidence_v1 `
  --limit 5 `
  --output artifacts/retrieval/nct07424430-goal.json
```

Stop the retrieval services to verify the stage boundary:

```powershell
docker compose stop
```

## 2. Answer from the Saved Evidence

```powershell
./.venv/Scripts/python.exe -m clinical_doc_assist.answering.cli `
  --retrieval-run artifacts/retrieval/nct07424430-goal.json `
  --output artifacts/answers/nct07424430-goal.json
```

Expected console output is one JSON answer artifact. Expected file location is
`artifacts/answers/nct07424430-goal.json`. Without `--output`, the command writes
to `artifacts/answers/<answer_id>.json`.

## 3. Inspect the Outcome

A supported answer should have:

- `status`: `answered`
- At least one `claims` entry
- At least one citation ID for every claim
- Canonical source URLs copied from the retrieval evidence
- Model and prompt versions
- Token usage when provided by the provider
- Measured latency
- The research-only disclaimer

Verify that every value in `claims[].citation_ids` appears in `citations[]`.
The same record preserves the retrieval ID and answer ID used by feature 006
orchestration and feature 007 evaluation.

## 4. Verify Abstention

Use a valid feature 004 retrieval artifact with:

```json
{
  "status": "no_results",
  "results": []
}
```

The answer workflow must produce:

- `status`: `insufficient_evidence`
- Empty `claims`
- A non-empty `reason`
- No model token usage, because the model was not called
- Exit code `0`

Run the offline tests and lint checks:

```powershell
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe -m ruff check .
```

## Manual Failure Checks

- Point `--retrieval-run` to malformed JSON: expect exit code `2` and no answer
  artifact.
- Give the fake model an unknown `chunk_id`: expect a `failed` artifact and exit
  code `1`.
- Request metadata for an NCT identifier absent from evidence: expect a rejected
  tool call.
- Stop Docker after retrieval: answering the saved artifact must still work.
