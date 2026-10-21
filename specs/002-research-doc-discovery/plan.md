# Implementation Plan: Research Document Discovery and Screening

**Branch**: `002-research-doc-discovery` | **Date**: 2026-10-21 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/002-research-doc-discovery/spec.md`

## Summary

Add a small command-line research collector. A single model-backed research agent
uses two tools: current time and ClinicalTrials.gov search. The application
records authoritative tool output, asks the model to reflect on candidate
relevance, applies deterministic source/date/duplicate checks, and prints one
structured discovery run. The feature stops before document ingestion.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `openai` for the existing Chat Completions provider,
`httpx` for the public ClinicalTrials.gov API, and `python-dotenv` for settings

**Storage**: None; the complete run is emitted as JSON to standard output

**Testing**: `pytest` with fake model responses and `httpx.MockTransport`; no live
model or network

**Target Platform**: Cross-platform command-line application, verified on Windows
PowerShell

**Project Type**: Single Python package with a CLI

**Performance Goals**: One source request with at most 20 candidates, bounded by
the existing model step limit; no crawling, batching, or concurrency

**Constraints**: Public data only; no PHI; no source failure presented as an empty
success; no network in automated tests

**Scale/Scope**: One user, one query, one approved source, and one result page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Public evidence only**: The only source adapter is ClinicalTrials.gov.
- **Evidence-grounded answers**: This feature does not answer questions yet. It
  preserves source provenance for the later answering stage.
- **Reproducible evaluation**: Every result includes the request, current time,
  search queries, and screening decisions.
- **Independent stages**: The command ends after discovery and screening.
- **Small scope**: One agent, two tools, one source, and one command; no
  multi-agent framework, database, or monitoring stack.

No constitutional violations or exceptions are required.

## Project Structure

### Documentation

```text
specs/002-research-doc-discovery/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- cli.md
`-- checklists/
    `-- requirements.md
```

### Source Code

```text
src/clinical_doc_assist/research/
|-- __init__.py
|-- models.py           # Request, candidate, decision, and run records
|-- prompts.py          # System and user prompt builders
|-- clinical_trials.py  # Approved source adapter and response normalization
|-- screening.py        # Deterministic checks and final status resolution
|-- agent.py            # Bounded tool-calling research agent
`-- cli.py              # clinical-doc-discover command

tests/
|-- test_clinical_trials.py
|-- test_research_agent.py
|-- test_research_screening.py
`-- test_research_cli.py
```

**Structure Decision**: Keep the feature in a `research/` subpackage so the
existing provisional scaffold remains untouched. Each module has one narrow role
and can be tested without the other stages.

## Design

### Discovery Flow

1. Validate the topic, inclusive date window, and candidate limit.
2. Run one bounded model/tool loop with the system and user prompts.
3. Require `get_current_datetime` before allowing `search_clinical_trials`.
4. Normalize ClinicalTrials.gov records into candidates and retain the
   authoritative tool response.
5. Ask the model to classify candidates against the topic and source policy.
6. Apply deterministic source, date, metadata, and duplicate checks.
7. Resolve model decisions with deterministic rejection as the higher authority.
8. Emit a complete JSON discovery run and stop before ingestion.

### Source Adapter

Use `GET https://clinicaltrials.gov/api/v2/studies` with:

- `query.term` for the topic
- `filter.advanced=AREA[LastUpdatePostDate]RANGE[after,before]`
- `pageSize` for the requested limit
- `fields` for only the metadata needed by this feature
- `sort=LastUpdatePostDate:desc` so truncated results keep the newest records

The adapter normalizes each record to a stable candidate, canonical
`https://clinicaltrials.gov/study/<NCT_ID>` URL, and a short evidence snippet.

### Screening Rules

- Reject missing identifiers, invalid dates, dates outside the window, unexpected
  sources, and duplicate identifiers.
- Accept a valid, unique, in-window candidate only when the model marks it
  relevant.
- Use `needs_review` when model output is missing, ambiguous, or uncertain.
- Never let model output override a deterministic rejection.

### Testing Strategy

- Contract tests verify the ClinicalTrials.gov request and response mapping.
- Screening tests cover every reason code and precedence rule.
- Agent tests use a fake client to verify clock-before-search enforcement and
  bounded tool calling.
- CLI tests verify JSON output and failure exit codes without live services.

## Complexity Tracking

No violations. The implementation uses the existing provider integration, one
public HTTP adapter, standard-library dataclasses, and one command entry point.
