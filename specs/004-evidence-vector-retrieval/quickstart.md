# Quickstart: Evidence Embedding and Vector Retrieval

## Prerequisites

- Docker Desktop with Linux containers
- Current feature 003 corpus, such as `artifacts/corpus/glp1-pilot-v2`
- Python environment with feature 004 dependencies

## Start Services

```powershell
docker compose up -d
docker compose ps
```

The first TEI start downloads `BAAI/bge-small-en-v1.5` into the named model volume.

Health checks:

```powershell
curl.exe http://127.0.0.1:8080/health
curl.exe http://127.0.0.1:6333/healthz
```

## Index the Corpus

```powershell
clinical-doc-retrieve index `
  --corpus artifacts/corpus/glp1-pilot-v2 `
  --collection clinical_evidence_v1
```

Use `--replace` for a clean rebuild when stale points should be removed.

## Search

```powershell
clinical-doc-retrieve search `
  "What cardiovascular outcomes were reported for semaglutide?" `
  --collection clinical_evidence_v1 `
  --limit 5 `
  --output artifacts/retrieval/semaglutide-cardio.json
```

The result is ranked evidence chunks with source links. It does not generate an
answer.

See [the manual acceptance guide](../../docs/retrieval-acceptance.md) for the
complete Docker and end-to-end verification sequence.

## Test

```powershell
pytest
ruff check .
```

Default tests use fake TEI and Qdrant clients. The live Docker smoke test is
opt-in through an environment flag.

## Stop

```powershell
docker compose stop
```

`docker compose down` preserves named volumes. `docker compose down -v` deletes
the model cache and Qdrant data.
