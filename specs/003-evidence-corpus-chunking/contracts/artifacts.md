# Artifact Contract: Evidence Corpus

## Directory Layout

```text
<build-directory>/
|-- manifest.json
|-- documents.jsonl
`-- chunks.jsonl
```

`documents.jsonl` and `chunks.jsonl` are present only for `completed` or `partial`
builds with usable content.

## Manifest Requirements

`manifest.json` MUST include:

- `schema_version`
- `build_id`
- `status`
- `created_at`
- discovered input paths and run IDs
- deduplicated NCT IDs and contributing run IDs
- chunk settings
- document and chunk counts
- source failures
- build-level errors

Every source failure MUST include the NCT identifier, concise reason, stable
error type, optional HTTP status, and retryability indicator.

## Document Requirements

Each document record MUST include one accepted NCT identifier, source provenance,
contributing discovery run IDs, normalized sections, unavailable section names,
and a content hash.

## Chunk Requirements

Each chunk record MUST include one document identifier, one section name,
zero-based chunk order, character range, text, content hash, and source link.

Chunks MUST NOT cross document or section boundaries and MUST NOT exceed the
configured maximum character count.

## Feature 004 Handoff

Feature 004 MUST read the corpus manifest first. It may index a `completed` or
`partial` corpus with at least one chunk. It MUST reject `no_documents`, `failed`,
malformed, or zero-chunk corpora.
