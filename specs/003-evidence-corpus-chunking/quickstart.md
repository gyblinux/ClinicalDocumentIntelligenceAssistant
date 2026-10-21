# Quickstart: Evidence Corpus Assembly and Chunking

## Prerequisites

- Feature 002 discovery artifacts under `artifacts/discovery/`
- Network access to ClinicalTrials.gov for detailed public records
- Existing Python virtual environment

## Build a Corpus

```powershell
clinical-doc-corpus build `
  --discovery-run artifacts/discovery/semaglutide-obesity.json `
  --discovery-run artifacts/discovery/tirzepatide-obesity.json `
  --discovery-run artifacts/discovery/glp1-mace.json `
  --output artifacts/corpus/glp1-pilot
```

If Windows application-control policy blocks the generated executable, use the
equivalent module command.

Expected completed result:

- New `artifacts/corpus/glp1-pilot/` directory
- `manifest.json`
- `documents.jsonl`
- `chunks.jsonl`
- A JSON summary containing document and chunk counts

Expected no-input result:

- Status `no_documents`
- Manifest with zero documents and chunks
- No misleading corpus files

The command stops before embeddings, vector search, retrieval, or answering.

## Verify

```powershell
pytest
ruff check .
```

Tests use frozen discovery and source-response fixtures and do not call the live
public source.
