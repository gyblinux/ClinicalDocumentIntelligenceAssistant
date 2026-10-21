# Retrieval Manual Acceptance Guide

**Status**: Completed by the project owner on 2026-10-21

**Observed result**: TEI and Qdrant integration passed; the
`clinical_evidence_v1` collection contained 208 indexed chunks, and the sample
retrieval run completed with five ranked evidence results.

This guide verifies the feature 004 TEI and Qdrant integration end to end.

## Prerequisites

- Docker Desktop running Linux containers
- Feature 003 corpus at `artifacts/corpus/glp1-pilot-v2`
- Retrieval settings appended to the ignored `.env` file

Do not replace an existing `.env` that contains the DeepSeek credential. Add:

```dotenv
TEI_URL=http://127.0.0.1:8080
TEI_MODEL=BAAI/bge-small-en-v1.5
TEI_EMBEDDING_DIMENSION=384
TEI_BATCH_SIZE=32
QDRANT_URL=http://127.0.0.1:6333
QDRANT_API_KEY=
```

## Start and Verify Services

From Git Bash:

```bash
cd /path/to/clinical_doc_assist
docker compose pull
docker compose up -d
docker compose ps
```

The first TEI start downloads `BAAI/bge-small-en-v1.5`.

```bash
docker compose logs -f embeddings
```

In another terminal:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/info
curl http://127.0.0.1:6333/healthz
curl http://127.0.0.1:6333/readyz
```

TEI `/info` must report `BAAI/bge-small-en-v1.5`.

## Run the Integration Test

```bash
RUN_DOCKER_INTEGRATION=1 ./.venv/Scripts/python.exe -m pytest \
  tests/integration/test_retrieval_stack.py
```

Expected result: one test passes.

## Index the Accepted Corpus

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.retrieval.cli index \
  --corpus artifacts/corpus/glp1-pilot-v2 \
  --collection clinical_evidence_v1 \
  --replace
```

Expected summary:

- `status: "completed"`
- `chunk_count: 208`
- `point_count: 208`
- One manifest under `artifacts/index-runs/`

## Retrieve Evidence

```bash
./.venv/Scripts/python.exe -m clinical_doc_assist.retrieval.cli search \
  "What cardiovascular outcomes were reported for semaglutide?" \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output artifacts/retrieval/semaglutide-cardio.json
```

Acceptance criteria:

- `status` is `completed`
- At most five results are returned
- Ranks start at one
- Every result includes chunk text, score, NCT ID, and source URL
- Standard output equals the persisted retrieval-run JSON

## Verify Idempotent Reindexing

Run the index command again without `--replace`. The collection must remain at
208 points rather than doubling.

Inspect:

```text
http://127.0.0.1:6333/dashboard
```

## Stop

```bash
docker compose stop
```

`docker compose down` preserves named volumes. `docker compose down -v` deletes
the model cache and Qdrant data.
