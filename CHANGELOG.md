# Changelog

All notable project changes are recorded here.

## [Unreleased]

### Added

- Initialize GitHub Spec Kit for Codex with a project constitution, baseline
  practice-project specification, and quality checklist.
- Define the first feature as single-source research discovery with current-time
  context, deterministic screening, and a stop before document ingestion.
- Add the `clinical-doc-discover` prototype with a bounded research agent,
  ClinicalTrials.gov search, deterministic screening, and JSON run output.
- Add the `clinical-doc-corpus` prototype with detailed source retrieval,
  normalized evidence documents, deterministic chunks, and local manifests.
- Add local TEI/Qdrant indexing and evidence retrieval with deterministic point
  IDs, index manifests, and citation-ready search results.
- Add a reproducible manual acceptance guide for Docker-backed retrieval.
- Add the `clinical-doc-answer` stage for single-turn evidence-grounded answers,
  claim-level citation validation, allowlisted trial metadata, safe abstention,
  persisted answer records for feature 006 evaluation, and a passing live
  Docker-off acceptance.
- Define a refined single-turn evidence-answering scope, approved plan, and task
  list; preserve the preliminary evaluation scope; and record an ignored
  requirements-gap baseline for final comparison. Define the paired
  retrieval/answer artifact handoff from feature 005 to feature 006.
- Define persisted discovery artifacts, empty-input handling, multi-run
  deduplication for feature 003, and baseline retrieval scope for feature 004.

### Changed

- Improve corpus chunk boundaries, transient source retries, structured source
  failures, and concise filesystem error handling.
- Persist discovery runs as schema-versioned JSON artifacts for feature 003 and
  keep console output safe for non-UTF-8 Windows terminals.
- Refocus the baseline on a small public clinical research Q&A practice project
  with evidence-grounded answers and reproducible evaluation; architecture and
  implementation remain pending.
- Document a minimal single-agent architecture review and defer multi-agent and
  infrastructure overhead until baseline results justify it.
- Clarify the research agent's typing and error boundaries for more readable,
  maintainable tool-call orchestration.

## [0.1.0] - 2026-10-21

### Added

- Initial Python package with an OpenAI SDK client configured for DeepSeek.
- Bounded agent loop with Chat Completions tool calling and clinical documentation guardrails.
- Starter BMI and clinical-template tools.
- One-shot and interactive command-line interfaces.
- Environment-based configuration, unit tests, linting, and usage documentation.

### Security

- Keep API credentials in the ignored `.env` file instead of source control.
