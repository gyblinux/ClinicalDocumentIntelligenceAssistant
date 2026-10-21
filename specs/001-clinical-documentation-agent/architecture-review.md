# Architecture Review: Public Clinical Research Q&A

**Status**: Reviewed for fit; delivered through approved feature slices

**Specification**: [spec.md](spec.md)

**First feature**: [Research Document Discovery and Screening](../002-research-doc-discovery/spec.md)

**Next feature**: [Evidence Corpus Assembly and Chunking](../003-evidence-corpus-chunking/spec.md)

**Follow-on feature**: [Evidence Embedding and Vector Retrieval](../004-evidence-vector-retrieval/spec.md)

**Answer feature**: [Evidence-Grounded Answers](../005-evidence-grounded-answers/spec.md)

**Orchestration feature**: [Question-to-Answer Orchestration](../006-question-answer-orchestration/spec.md)

**Evaluation feature**: [Reproducible RAG Evaluation](../007-rag-evaluation/spec.md)

## Verdict

The proposed pipeline is directionally sound for this practice project:

```text
public documents -> extracted text + metadata -> chunks + retrieval index
-> retrieved evidence -> grounded answer + citations -> evaluation report
```

The smallest suitable baseline is one coordinated pipeline with one
question-answering agent. Multi-agent collaboration is not justified yet. It adds
coordination cost, latency, token use, non-determinism, and harder failure
attribution before the project has measured a concrete need.

The first feature slice is narrower than full ingestion: one agent discovers
candidates from ClinicalTrials.gov, uses the current-time capability, and returns
screened records. PDF parsing remains deferred, while retrieval, question
answering, and evaluation are separate downstream stages.

Feature 003 converts accepted records into normalized evidence documents and
deterministic chunks. Feature 004 indexes those chunks and returns ranked evidence
with source provenance.

Feature 005 provides the implemented single-turn answering stage. Feature 006 now
provides the implemented question-to-answer composition layer, and feature 007
will evaluate the resulting pipeline records. None adds multi-agent behavior;
feature 007 still requires its own approved plan and tasks.

Feature 006 accepts each user question, performs fresh retrieval, invokes
answering, and links the resulting artifacts. Feature 007 evaluates each fixed case
from the pipeline record plus its underlying retrieval and answer artifacts,
preserving attribution between retrieval and answer-generation failures.

## Stage Assessment

| Stage | Keep in the baseline | Defer until evidence justifies it |
| --- | --- | --- |
| Document ingestion | A small curated corpus of PDF and text files, source URL, minimal metadata, and a document manifest | Web crawling, broad format support, OCR, automatic metadata enrichment, and continuous ingestion |
| Chunking and retrieval | Simple deterministic chunking, local embeddings, local vector search, and source/page metadata | Hosted vector databases, hybrid search, reranking, query routing, and multiple indexes |
| LLM application | One evidence-grounded answer path, retrieval as its only required tool, citations checked against retrieved evidence, and an insufficient-evidence response | Broad tool access, autonomous planning, specialist agent teams, and multiple LLM calls per question |
| Evaluation and monitoring | Fixed test set, per-case and aggregate results, citation validity, retrieval checks, and latency/cost recorded per run | Always-on dashboards, APM infrastructure, alerting, and expensive judge ensembles |

## Essential Controls

1. **Stage entry points**: Fine-grained stages must exchange versioned local
   artifacts. A user can inspect an artifact and stop before the next stage.
2. **Run manifest**: Record corpus version, chunking settings, embedding model,
   prompt version, answer model, test-set version, and timestamp.
3. **Inspectable artifacts**: Preserve the document list, extracted metadata,
   chunks, retrieval hits, answers with citations, and evaluation report.
4. **Citation validity**: Treat a citation as valid only when it resolves to a
   retrieved chunk; do not rely solely on the model to produce trustworthy
   references.
5. **Visible failures**: Reject unreadable documents, missing evidence, malformed
   evaluation cases, and partial runs without presenting them as successful.
6. **Evaluation split**: Assess retrieval separately from answer quality so a bad
   answer can be attributed to missing evidence or poor generation.

## Recommended Minimal Metrics

- **Retrieval**: At least one relevant source retrieved and, if practical,
  relevant-source recall for the top results.
- **Answer grounding**: Every cited source was actually retrieved, and unsupported
  questions receive an insufficient-evidence response.
- **Answer quality**: A fixed case-level rubric with expected key points and a
  small human-reviewed sample.
- **Operational**: Average latency, total model cost, and failures per evaluation
  run.

An LLM judge can be added later as a secondary metric, with a versioned rubric.
It should not replace fixed test cases, citation checks, or human spot checks.

## Overhead to Avoid Initially

- **Multi-agent orchestration**: Defer until a specific bottleneck such as query
  reformulation, evidence verification, or synthesis has a separate measurable
  evaluation.
- **Vector database operations**: A local index is sufficient for a small curated
  corpus.
- **Monitoring platform**: A saved evaluation report is enough before there are
  real users or continuous traffic.
- **General tool framework**: Retrieval is the only tool needed to test the core
  question-answering hypothesis.
- **Advanced retrieval**: Add hybrid search or reranking only after retrieval
  metrics show a specific weakness.
- **Complex ingestion**: Add OCR or crawlers only if the chosen corpus requires
  them.

## Decision Gate

This review endorses the architecture with the deferred items above. The project
has implemented features 002 through 004 as bounded slices. Each later feature
still requires its own approved plan, task breakdown, and implementation gate.
