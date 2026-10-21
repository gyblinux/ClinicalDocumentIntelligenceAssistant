# Documentation

Start with the document that matches your task:

| Document | Use it for |
| --- | --- |
| [Architecture brief](architecture.md) | Current system boundaries, data flow, modules, artifacts, controls, and limitations |
| [Usage guide](usage.md) | Setup, environment configuration, every CLI stage, evaluation, presentation, tests, and troubleshooting |
| [Technology guide](technology-guide.md) | Beginner-to-intermediate explanations of RAG, embeddings, TEI, Qdrant, agents, artifacts, and tooling |
| [Retrieval acceptance](retrieval-acceptance.md) | Manual Docker, indexing, search, and idempotency verification |
| [Evaluation baseline](evaluation-baseline.md) | Initial fixed-suite metrics, failure attribution, and readability review |

## Recommended reading order

1. Read the repository [README](../README.md) for the short project overview.
2. Read the [architecture brief](architecture.md) to understand how the stages
   connect.
3. Follow the [usage guide](usage.md) to run the staged workflow or one-command demo.
4. Use the [technology guide](technology-guide.md) when a term or service is new.
5. Open the relevant feature specification under [`specs/`](../specs/) when
   changing behavior.

The architecture brief is the maintained current-system description. The
[architecture decision record](../specs/001-clinical-documentation-agent/architecture-review.md)
explains why the small pipeline was chosen and why more complex options were
deferred.
