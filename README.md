# Clinical Doc Assist

Clinical Doc Assist is a small, early-stage practice project for:

1. Ingesting publicly available clinical research documents.
2. Answering questions from retrieved evidence.
3. Evaluating answer quality with a reproducible test set.

This is a learning project, not a clinical-use system. Architecture and
implementation decisions are intentionally deferred.

## Current State

The repository has a Spec Kit baseline and a provisional code scaffold. The
specification defines the project scope only; the existing source code is not an
approved architecture.

A high-level single-agent pipeline has been proposed and reviewed in the
[architecture review](specs/001-clinical-documentation-agent/architecture-review.md).
Multi-agent orchestration and operational infrastructure are deferred. This is
not yet an approved plan.

## Spec-Driven Development

The project advances through explicit, reviewable gates:

1. Review the [constitution](.specify/memory/constitution.md) and
   [baseline specification](specs/001-clinical-documentation-agent/spec.md).
2. Provide and approve the architecture and implementation direction.
3. Run `$speckit-plan`, then review the plan.
4. Run `$speckit-tasks`, then review the tasks.
5. Run `$speckit-implement` only after approval.

Ingestion, question answering, and evaluation must remain independently
controllable and inspectable at every stage.

See [CHANGELOG.md](CHANGELOG.md) for notable changes.
