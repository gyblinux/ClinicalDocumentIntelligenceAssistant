# Changelog

All notable project changes are recorded here.

## [Unreleased]

### Added

- Initialize GitHub Spec Kit for Codex with a project constitution, baseline
  practice-project specification, and quality checklist.

### Changed

- Refocus the baseline on a small public clinical research Q&A practice project
  with evidence-grounded answers and reproducible evaluation; architecture and
  implementation remain pending.
- Document a minimal single-agent architecture review and defer multi-agent and
  infrastructure overhead until baseline results justify it.

## [0.1.0] - 2026-10-21

### Added

- Initial Python package with an OpenAI SDK client configured for DeepSeek.
- Bounded agent loop with Chat Completions tool calling and clinical documentation guardrails.
- Starter BMI and clinical-template tools.
- One-shot and interactive command-line interfaces.
- Environment-based configuration, unit tests, linting, and usage documentation.

### Security

- Keep API credentials in the ignored `.env` file instead of source control.
