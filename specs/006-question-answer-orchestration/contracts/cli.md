# CLI Contract: `clinical-doc-ask`

## Command

```text
clinical-doc-ask "QUESTION" \
  --collection NAME \
  [--limit 5] \
  [--pipeline-dir artifacts/pipelines]
```

The question is a required positional argument. It is passed unchanged to feature
004 retrieval.

## Input Rules

- Question must be non-empty after trimming.
- Collection name must be non-empty.
- Retrieval limit defaults to 5 and must be between 1 and 50.
- Retrieval services must be reachable for the command to proceed.
- Existing output files must not be overwritten silently.

## Output

Standard output is one pipeline JSON object. It includes:

- Question and requested retrieval settings
- Pipeline and stage statuses
- Linked retrieval and answer artifact paths
- Answer claims, citations, abstention reason, or failure summary
- Stage and total timing
- Recorded errors

Diagnostics go to standard error.

## Exit Codes

- `0`: pipeline ended as `answered` or `insufficient_evidence`
- `1`: valid input but retrieval, answering, or artifact persistence failed
- `2`: invalid question or arguments, unavailable configuration, or unsafe output
  path

## Service Boundary

The CLI does not implement retrieval or answer logic. It wires:

```text
feature 004 RetrievalService
feature 005 AnswerService
```

It must not call their command-line processes as subprocesses.
