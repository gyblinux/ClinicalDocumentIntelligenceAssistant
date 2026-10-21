# CLI Contract: `clinical-doc-answer`

## Command

```text
clinical-doc-answer \
  --retrieval-run PATH \
  [--output PATH]
```

There is intentionally no separate `QUESTION` argument. The question is read from
the feature 004 artifact at `query.text`.

## Input

- `--retrieval-run` is required.
- Input must be one feature 004 retrieval-run JSON object with schema version
  `1.0`.
- The retrieval status must be `completed` or `no_results`.
- A `completed` run may contain 1-10 evidence results.
- A `no_results` run must abstain without invoking the model.
- Malformed provenance, duplicate chunk IDs, unknown schema versions, or retrieval
  status `failed` are input errors.

## Output Path

The default output path is:

```text
artifacts/answers/<answer_id>.json
```

`--output` overrides that path. An explicit output path must not already exist;
the command fails with exit code `2` rather than overwriting local review data.

The same JSON object written to the file is printed to standard output.
Diagnostics and human-readable errors go to standard error.

## Successful Answer

```text
clinical-doc-answer \
  --retrieval-run artifacts/retrieval/semaglutide-cardio.json \
  --output artifacts/answers/semaglutide-cardio-answer.json
```

Expected outcome:

- Exit code `0`
- Status `answered` or `insufficient_evidence`
- One persisted answer artifact
- No evaluation scores

## Exit Codes

- `0`: the stage completed with `answered` or `insufficient_evidence`.
- `1`: valid input, but a model, tool, citation-validation, or persistence
  operation failed.
- `2`: invalid arguments, unreadable or invalid retrieval input, unsupported
  schema/status, excessive evidence, or unsafe output path.

For exit code `1`, persist a `failed` answer artifact when the retrieval question
and retrieval ID were successfully loaded. For exit code `2`, do not write an
answer artifact because the input boundary was not trustworthy.

## Service Boundary

The command does not call TEI or Qdrant. It may call:

- The configured DeepSeek-compatible model endpoint.
- The public ClinicalTrials.gov API only through the allowlisted metadata tool.

An existing retrieval artifact can therefore be answered after
`docker compose stop`.
