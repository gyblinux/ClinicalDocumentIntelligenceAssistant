# Quickstart: Research Document Discovery

## Prerequisites

- Python 3.11 or newer
- A configured `DEEPSEEK_API_KEY`
- Network access for the live ClinicalTrials.gov request

## Install and Check

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
ruff check .
```

The test suite uses fake model responses and a mocked public-source client. It
does not make network requests or need an API key.

## Run Discovery

```powershell
clinical-doc-discover "GLP-1 cardiovascular outcomes" `
  --updated-after 2023-01-01 `
  --updated-before 2026-10-21 `
  --limit 5
```

If Windows application-control policy blocks the generated executable, use the
equivalent module command:

```powershell
python -m clinical_doc_assist.research.cli "GLP-1 cardiovascular outcomes" `
  --updated-after 2023-01-01 `
  --updated-before 2026-10-21 `
  --limit 5
```

Expected outcomes:

- `status: "completed"` with candidates separated into `accepted`, `rejected`,
  and `needs_review`.
- `status: "no_results"` when the approved source returns no matches.
- A non-zero exit and clear error when the clock or source fails.

The command stops after printing the JSON discovery run. It does not download,
parse, or ingest study documents.
