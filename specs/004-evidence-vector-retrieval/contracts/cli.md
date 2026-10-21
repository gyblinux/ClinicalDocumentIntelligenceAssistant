# CLI Contract: `clinical-doc-retrieve`

## Index

```text
clinical-doc-retrieve index \
  --corpus DIRECTORY \
  --collection NAME \
  [--replace]
```

- `--corpus` must reference a valid feature 003 build directory.
- `--collection` selects the Qdrant collection.
- `--replace` deletes and recreates the collection before indexing.
- Without `--replace`, deterministic UUID5 points are upserted idempotently.

Successful standard output:

```json
{
  "status": "completed",
  "index_id": "index-20261021T100000Z",
  "corpus_build_id": "corpus-1b2ddb696f1140f6",
  "collection": "clinical_evidence_v1",
  "point_count": 208
}
```

## Search

```text
clinical-doc-retrieve search "QUESTION" \
  --collection NAME \
  [--limit 5] \
  [--output PATH]
```

Successful standard output is one retrieval-run JSON object. `--output` persists
the same object.

## Exit Codes

- `0`: completed or valid no-results retrieval.
- `1`: TEI, Qdrant, embedding, or indexing failure.
- `2`: invalid arguments, invalid corpus, incompatible collection, or unsafe
  local output.

## Output Separation

Standard output is reserved for the JSON result. Progress and diagnostics go to
standard error.
