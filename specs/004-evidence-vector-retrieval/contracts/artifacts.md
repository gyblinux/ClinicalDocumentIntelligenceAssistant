# Artifact Contract: Index and Retrieval Runs

## Index Manifest

Index commands write a local JSON manifest under:

```text
artifacts/index-runs/<index_id>.json
```

It records the corpus build, chunk count, point count, TEI model and dimension,
Qdrant collection and endpoint, distance metric, replace behavior, and errors.

## Retrieval Run

Search results use one JSON object:

```json
{
  "schema_version": "1.0",
  "retrieval_id": "retrieval-20261021T100500Z",
  "created_at": "2026-10-21T10:05:00Z",
  "query": {
    "text": "What cardiovascular outcomes were reported?",
    "collection": "clinical_evidence_v1",
    "limit": 5
  },
  "tei_model": "BAAI/bge-small-en-v1.5",
  "collection": "clinical_evidence_v1",
  "results": [],
  "status": "no_results",
  "errors": []
}
```

Each result contains rank, score, chunk text, source URL, chunk ID, document ID,
NCT ID, section, and content hash.
