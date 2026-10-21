# Clinical Doc Assist Constitution

## Core Principles

### I. Public Evidence Only (NON-NEGOTIABLE)

The project uses publicly available clinical research documents. It MUST NOT use
private patient records or protected health information. It is a small practice
project, not a clinical decision-support product.

### II. Evidence-Grounded Answers (NON-NEGOTIABLE)

Answers MUST be based on retrieved evidence from the ingested documents. Each
answer MUST identify the supporting source material. When the available evidence
is insufficient, the system MUST say so rather than inventing an answer.

### III. Reproducible Evaluation (NON-NEGOTIABLE)

Answer quality MUST be evaluated with a fixed, reproducible test set. Re-running
the evaluation with unchanged inputs MUST produce comparable results, and changes
to the test set or inputs MUST be visible.

### IV. Independent, Controlled Stages

Document ingestion, question answering, and evaluation MUST be separately
controllable. The user MUST be able to inspect the output of one stage before
deciding whether to continue to the next.

### V. Specification First, Architecture Later

The specification defines WHAT the practice project does and WHY. Architecture,
implementation details, and task breakdown MUST remain open until the user
provides and approves them. New work stays small and avoids speculative features.

## Scope Boundaries

- The initial scope is deliberately small: one public research corpus, questions
  answered from retrieved evidence, and one reproducible evaluation workflow.
- Document sources, supported formats, retrieval approach, answer-quality metric,
  user interface, storage, and model choices are deferred to planning.
- The existing source tree is provisional and does not constitute architectural
  approval.

## Development Workflow

1. Review this constitution and update the feature specification.
2. Stop for user review of the specification.
3. Accept the user's architecture and implementation direction.
4. Use `$speckit-plan` and stop for plan approval.
5. Use `$speckit-tasks` and stop for task approval.
6. Use `$speckit-implement` only after the prior stages are accepted.

Each change MUST include relevant tests or evaluation checks and a concise
`CHANGELOG.md` entry for the eventual push.

## Governance

Repository instructions in `AGENTS.md` are mandatory and must not weaken this
constitution. Amendments require a documented rationale and an updated version.
Constitution versions follow semantic versioning: MAJOR for incompatible
principle changes, MINOR for new or expanded governance, and PATCH for
clarifications. The user controls approval between all SDD stages.

**Version**: 2.0.0 | **Ratified**: 2026-10-21 | **Last Amended**: 2026-10-21
