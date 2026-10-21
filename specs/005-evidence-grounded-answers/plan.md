# Implementation Plan: Evidence-Grounded Answers

**Branch**: `005-evidence-grounded-answers` | **Date**: 2026-10-21 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/005-evidence-grounded-answers/spec.md`

**Status**: Implemented and validated 2026-10-21

## Summary

Add one single-turn answer stage after feature 004. It consumes a saved retrieval
run, uses that run's recorded question as the question, sends only the saved
evidence to DeepSeek Flash, and writes a self-contained answer artifact. The
workflow produces claim-level citations, rejects unknown evidence references,
allows one bounded trial-metadata lookup for an NCT identifier already present in
the evidence, and abstains when support is insufficient.

Feature 005 does not retrieve evidence, browse the web, retain conversation
history, score answer quality, or coordinate multiple agents.

## Technical Context

**Language/Version**: Python 3.11+; the current local environment is Python 3.13

**Primary Dependencies**: Existing `openai`, `httpx`, and `python-dotenv`; no new
runtime framework

**Answer Model**: Configured DeepSeek Flash model through the existing
OpenAI-compatible client

**Input**: One feature 004 retrieval-run JSON artifact using schema version `1.0`

**Evidence Limit**: At most 10 highest-ranked retrieval results per answer run

**Metadata Tool**: Existing `ClinicalTrialsSource.fetch_study`, normalized to a
small public-metadata result

**Storage**: One atomic local JSON artifact under `artifacts/answers/`

**Testing**: `pytest` with fake model and metadata clients; live provider testing
is optional and manual

**Target Platform**: Host Python CLI on Windows; TEI and Qdrant containers are
not required when consuming an existing retrieval artifact

**Project Type**: Single Python package with a `clinical-doc-answer` CLI

**Performance Goals**: Complete one question with at most two model turns and at
most three metadata lookups; record observed latency without enforcing a provider
SLA

**Constraints**: Evidence-only answering, stable chunk identifiers, canonical
source provenance, explicit abstention, no chat memory, and no retrieval during
answering

**Scale/Scope**: One question, one retrieval run, up to 10 evidence items, and a
small public trial corpus

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Public evidence only**: Input is a saved artifact from the accepted public
  corpus pipeline; feature 005 does not add private data or general web browsing.
- **Evidence-grounded answers**: The context packet contains only the recorded
  question and retrieved evidence, and every accepted claim requires a valid
  citation.
- **Reproducible evaluation**: Answer inputs, prompt/model versions, evidence,
  tool activity, citations, usage, and errors are recorded for feature 007.
- **Independent stages**: The answer stage consumes an immutable retrieval artifact
  and stops before evaluation scoring.
- **Small scope**: One bounded model workflow, one metadata tool, one CLI, and no
  multi-agent orchestration or production platform.

No constitutional violations or exceptions are required.

## Project Structure

### Documentation

```text
specs/005-evidence-grounded-answers/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- cli.md
|   `-- artifacts.md
`-- checklists/
    `-- requirements.md
```

### Source Code

```text
src/clinical_doc_assist/answering/
|-- __init__.py
|-- models.py          # Input, claim, citation, tool, and answer-run records
|-- prompts.py         # Evidence-only system and user prompts
|-- citations.py       # Citation parsing and allowlist validation
|-- tools.py           # Allowlisted clinical-trial metadata lookup
|-- agent.py           # Bounded model/tool loop
|-- service.py         # Input loading, orchestration, and artifact persistence
`-- cli.py             # clinical-doc-answer

tests/
|-- fixtures/answering/
|-- test_answering_models.py
|-- test_answering_citations.py
|-- test_answering_tools.py
|-- test_answering_agent.py
|-- test_answering_service.py
`-- test_answering_cli.py
```

**Structure Decision**: Keep answering isolated from retrieval and evaluation.
The feature reuses existing source and model clients while adding only the small
records and validation needed for a traceable answer stage.

## Design

### Stage Boundary

The only evidence input is one saved feature 004 retrieval run. The CLI does not
accept a second question argument because the retrieval run already records the
question. This prevents answering against evidence retrieved for a different
question.

The workflow requires no live TEI or Qdrant service. Those services are needed
only to create or refresh the feature 004 artifact. DeepSeek and the optional
ClinicalTrials.gov metadata lookup still require network access.

### Input Validation

Before calling the model:

1. Load one JSON object from `--retrieval-run`.
2. Require schema version `1.0`.
3. Require status `completed` with 1-10 results or `no_results` with zero results.
4. Read the question from `query.text`; reject an empty question.
5. Require every result to contain a unique `chunk_id`, valid `nct_id`, non-empty
   text and section, an HTTP(S) `source_url`, and `content_hash`.
6. Use the results in recorded rank order.

A `no_results` run creates an `insufficient_evidence` answer artifact without
loading or calling the model. A malformed artifact or a `failed` retrieval run is
an input error.

### Context Engineering

The system prompt establishes the role as a clinical research evidence summarizer,
states that evidence is untrusted data rather than instructions, requires one or
more citations per factual claim, and prohibits clinical advice or outside facts.

The user prompt contains:

- The question copied from the retrieval run.
- Only the ranked evidence text and traceable identifiers.
- The allowed NCT identifiers.
- The required structured response and abstention format.

The prompt does not include conversation history, prior questions, general web
results, or unsourced model knowledge.

### Model Output

The model produces one of two normalized forms:

```json
{
  "status": "answered",
  "claims": [
    {
      "text": "One factual statement.",
      "citation_ids": ["chunk-..."]
    }
  ]
}
```

```json
{
  "status": "insufficient_evidence",
  "reason": "Why the supplied evidence does not support an answer."
}
```

Claim text is model-authored. Citation identifiers must be selected from the
supplied retrieval chunk IDs or a successful metadata citation ID such as
`trial-metadata:NCT00000000`.

### Trial Metadata Tool

Provide one tool named `fetch_trial_metadata` with a single `nct_id` argument.
Application code rejects any identifier not present in the retrieval evidence.
The tool:

- Accepts at most three distinct NCT identifiers per answer run.
- Performs at most one lookup per NCT identifier.
- Reuses `ClinicalTrialsSource.fetch_study`.
- Returns compact public fields such as status, study type, phase, enrollment,
  dates, sponsors, and interventions.
- Records success, failure, requested identifier, and returned identifier.

A failed metadata lookup is recorded. It does not erase otherwise sufficient
evidence, but no claim may cite metadata that was not successfully retrieved.

### Citation Validation

Application code, not the model, owns citation acceptance:

- `chunk-*` citations must exactly match a supplied retrieval result.
- `trial-metadata:NCT########` citations require a retrieved NCT identifier and a
  successful lookup for that NCT.
- Every answered claim must contain at least one citation.
- An answered result must contain at least one claim.
- An insufficient-evidence result must contain no factual claims.
- Any unknown or malformed citation rejects the entire answer as `failed`.
- Canonical source URL, NCT identifier, section, and hash are copied from
  retrieval input or the tool result; model-authored provenance is disregarded.

This validates citation identity and provenance only. It does not prove semantic
entailment. Feature 007 measures retrieval relevance and answer faithfulness.

### Model and Tool Bounds

- Maximum model turns per run: 2
- Maximum tool calls per run: 3
- Maximum evidence items: 10
- Maximum model output tokens per turn: 1600
- Maximum claims per answer: 10
- No parallel tool calls
- No unknown tools
- A model or tool limit produces a visible `failed` answer artifact when the
  retrieval input itself was valid

### Persisted Answer Record

The answer stage persists one self-contained record per run. It contains:

- Schema and answer-run identifiers
- Creation time and status
- Question and retrieval-run identifier
- Full input evidence snapshot, limited to the accepted evidence packet
- Model identifier, provider, and prompt version
- Claims and enriched citations
- Final model output snapshot
- Metadata tool calls and results summary
- Token usage when provided
- Total latency and error details
- Research-only disclaimer

Artifacts are written atomically. A failed run retains enough input and error
information for review, but it never contains a partially accepted answer.

This record is the feature 005 handoff to feature 007 evaluation. Feature 006
combines it with the original feature 004 retrieval artifact in one pipeline
record. Answer-side metrics use the record's claims, citations, status, tool
calls, latency, and usage. Retrieval-side metrics use the original ranking,
scores, status, and retrieval errors. The answer record is not treated as a
replacement for the retrieval artifact.

### CLI

```text
clinical-doc-answer --retrieval-run PATH [--output PATH]
```

The default output is `artifacts/answers/<answer_id>.json`. `--output` overrides
that path. Standard output is the same JSON artifact; diagnostics go to standard
error.

Exit codes:

- `0`: valid answered or insufficient-evidence result
- `1`: valid input followed by model, tool, citation-validation, or persistence
  failure
- `2`: unreadable, malformed, unsupported, or unusable input

### Docker Boundary

The manual end-to-end check is:

1. Start TEI and Qdrant with Docker Compose.
2. Create a retrieval artifact with feature 004.
3. Stop the retrieval containers.
4. Run feature 005 against the saved artifact.

Step 4 must succeed without contacting TEI or Qdrant, demonstrating the stage
boundary.

## Testing Strategy

- Valid input and question inheritance from the retrieval run.
- Malformed metadata, missing provenance, duplicate chunk IDs, and excessive
  evidence rejection.
- No-results abstention without a model call.
- Supported answer with claim-level citations.
- Unknown, missing, malformed, and tool-invalid citation rejection.
- Metadata allowlist, normalization, successful lookup, duplicate lookup, and
  failure.
- Insufficient-evidence model response.
- Conflicting-evidence prompt coverage using a fake model.
- Model malformed output, turn limit, provider failure, and artifact status.
- Atomic output persistence and exact standard-output equality.
- CLI exit codes and diagnostics.
- Saved-artifact answering with no retrieval service doubles.

## Complexity Tracking

No violations. The design adds one package, one model workflow, and one narrowly
scoped tool. Claim-level citations add modest structure so citation identity and
future faithfulness evaluation remain attributable.

## Phase Outputs

- Phase 0: [research.md](research.md)
- Phase 1: [data-model.md](data-model.md)
- Phase 1: [CLI contract](contracts/cli.md)
- Phase 1: [artifact contract](contracts/artifacts.md)
- Phase 1: [quickstart.md](quickstart.md)

## Deferred

- Retrieval or query rewriting from feature 005
- Conversational memory or follow-up questions
- Web search and broad tool access
- Multiple answering agents
- LLM-judge or semantic evaluation
- FastAPI, UI, structured logging, and production monitoring

## Next Gate

Feature 005 is complete. Feature 006 orchestration and feature 007 evaluation
remain at their specification gates and require separate plan and task approvals.
