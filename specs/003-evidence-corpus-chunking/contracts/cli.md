# CLI Contract: `clinical-doc-corpus`

## Command

```text
clinical-doc-corpus build \
  --discovery-run PATH [--discovery-run PATH ...] \
  --output DIRECTORY \
  [--max-chars 1200] \
  [--overlap-chars 150]
```

`--discovery-run` is required and repeatable. `--output` must not already exist as
a non-empty directory.

## Standard Output

The command prints a short JSON summary:

```json
{
  "status": "completed",
  "build_id": "corpus-20261021T090000Z",
  "output": "artifacts/corpus/corpus-001",
  "document_count": 12,
  "chunk_count": 84,
  "source_failures": 0
}
```

Progress messages, if any, go to standard error.

## Exit Codes

- `0`: `completed` or `partial` with usable chunks.
- `3`: `no_documents`.
- `1`: `failed`.
- `2`: invalid arguments, malformed discovery input, or unsafe output path.

## Input Rules

- Every discovery artifact must use `schema_version: "1.0"`.
- Accepted decisions must contain valid `NCT` identifiers.
- Duplicate identifiers across artifacts are fetched once.
- Invalid discovery artifacts stop the build before any source retrieval.

## Artifact Rules

- A successful build creates a new output directory atomically.
- `completed` and `partial` builds contain `manifest.json`, `documents.jsonl`, and
  `chunks.jsonl`.
- `no_documents` contains a manifest with zero counts and no document/chunk files.
- `failed` does not replace an existing output directory.
