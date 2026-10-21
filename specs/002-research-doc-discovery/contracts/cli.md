# CLI Contract: `clinical-doc-discover`

## Command

```text
clinical-doc-discover TOPIC \
  --updated-after YYYY-MM-DD \
  --updated-before YYYY-MM-DD \
  [--limit 1..20] \
  [--output PATH]
```

`--updated-after` and `--updated-before` are required. The date window is
inclusive. `--limit` defaults to 5. `--output` writes the same JSON run to a file
after a valid `completed` or `no_results` result; failed runs do not leave a
successful artifact.

## Standard Output

Successful discovery writes one JSON object:

```json
{
  "schema_version": "1.0",
  "run_id": "20261021T073000Z-glp1-cardio",
  "status": "completed",
  "request": {
    "topic": "GLP-1 cardiovascular outcomes",
    "updated_after": "2023-01-01",
    "updated_before": "2026-10-21",
    "limit": 5
  },
  "current_time": "2026-10-21T07:30:00Z",
  "searches": [
    {
      "query": "GLP-1 cardiovascular outcomes",
      "updated_after": "2023-01-01",
      "updated_before": "2026-10-21",
      "result_count": 0
    }
  ],
  "accepted": [],
  "rejected": [],
  "needs_review": [],
  "errors": []
}
```

A valid request with no source matches returns `status: "no_results"`.

## Errors

- Argument/configuration errors: exit code `2`, message on standard error.
- Clock, source, parsing, or agent failures: exit code `1`, message on standard
  error.
- Completed or no-results runs: exit code `0`.

The command MUST not write progress text to standard output because standard
output is the JSON run record.

When `--output` is provided, the file MUST contain the same JSON object emitted
to standard output and MUST be written only after the run reaches a valid final
status.
