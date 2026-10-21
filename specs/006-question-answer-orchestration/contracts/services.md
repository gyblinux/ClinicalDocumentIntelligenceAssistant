# Service Contract: Orchestration Composition

## Retrieval Dependency

```text
search_evidence(
  question,
  collection,
  limit
) -> RetrievalRun
```

Requirements:

- The exact normalized question is used.
- The returned run records that same question in `query.text`.
- Retrieval is attempted for every orchestration request.

## Answering Dependency

```text
answer(
  retrieval_path,
  output_path=None
) -> AnswerOutcome
```

Requirements:

- The persisted retrieval artifact is the only evidence input.
- Feature 005 remains responsible for citation validation, abstention, metadata
  tool restrictions, and failed answer artifacts.

## Orchestration Service

```text
ask(QuestionRequest) -> PipelineOutcome
```

The service:

1. Validates the request.
2. Calls retrieval.
3. Persists the retrieval artifact.
4. Calls answering with that path.
5. Builds and persists the pipeline record.

The service accepts injected retrieval, answering, clock, timing, identifier, and
artifact-writer dependencies so unit tests require no Docker or network.

## Error Contract

- Retrieval service failures are recorded as retrieval-stage failures.
- No-results retrieval proceeds to feature 005 and records abstention.
- Answer service failures preserve the retrieval artifact.
- Input/path errors do not invoke either stage.
- Stage and pipeline artifacts are written atomically.
