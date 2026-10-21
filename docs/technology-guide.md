# Technology Guide

This guide explains the main technologies in Clinical Doc Assist and how they fit
together. It assumes basic Python familiarity and introduces the retrieval,
agent, container, and evaluation concepts as needed.

## 1. Stack at a glance

| Technology | Role in this project | Where to look |
| --- | --- | --- |
| Python 3.11+ | Application language and CLI runtime | `src/clinical_doc_assist/` |
| Standard-library `argparse` | Stage-specific command-line interfaces | `*/cli.py` |
| Dataclasses and type hints | Explicit records and safer interfaces | `*/models.py` |
| JSON and JSONL | Versioned stage artifacts and corpus storage | `artifacts/`, corpus outputs |
| HTTPX | Direct HTTP requests to ClinicalTrials.gov and local services | `research/`, `retrieval/` |
| OpenAI Python SDK | Client transport for DeepSeek's OpenAI-compatible Chat Completions API | `config.py`, `agent.py` |
| DeepSeek Flash | Research screening and evidence-grounded answer generation | discovery and answering stages |
| ClinicalTrials.gov API | Public trial search, details, and metadata | `research/clinical_trials.py` |
| Hugging Face TEI | Serves the embedding model over HTTP | Docker Compose |
| `BAAI/bge-small-en-v1.5` | Converts text into 384-dimensional embeddings | TEI configuration |
| Qdrant | Local vector database and similarity search | `retrieval/qdrant.py` |
| Docker Compose | Starts and connects TEI and Qdrant | `compose.yml` |
| pytest | Offline, integration, and contract tests | `tests/` |
| Ruff | Linting and formatting checks | `pyproject.toml` |
| Hatchling | Python package build backend | `pyproject.toml` |
| GitHub Spec Kit | Specification, plan, task, and implementation workflow | `.specify/`, `specs/` |

## 2. How the core RAG concepts fit together

RAG means **retrieval-augmented generation**. Instead of asking a model to answer
from general memory, the application first retrieves relevant source passages and
then instructs the model to answer only from those passages.

```text
question
  -> question embedding
  -> nearest evidence chunks from the vector database
  -> prompt containing question + evidence
  -> model response with claims and citation IDs
  -> deterministic citation validation
  -> saved answer record
```

The model is still capable of mistakes, so the application validates citations and
persists enough evidence to inspect why an answer was produced.

## 3. Embeddings and vector search

An embedding model converts text into a numeric vector. Similar meanings tend to
produce nearby vectors even when the wording differs.

In this project:

1. The corpus stage creates deterministic chunks from public study sections.
2. TEI embeds each chunk with `BAAI/bge-small-en-v1.5`.
3. Embeddings and their IDs are stored in Qdrant.
4. A user query is embedded by the same model.
5. Qdrant ranks stored chunks by vector similarity.

The embedding dimension is 384. Changing the embedding model or dimension normally
requires reindexing the corpus and recording a new index manifest.

Why TEI runs in Docker:

- TEI packages the model-serving runtime.
- PyTorch and Transformers stay out of the host Python dependencies.
- The service exposes a small HTTP API.
- The model can be cached in a Docker volume.

Why Qdrant runs in Docker:

- It is free and local.
- It avoids implementing vector persistence and similarity search by hand.
- It keeps the host Python dependency small (`qdrant-client`).

## 4. Chunking and stable IDs

Chunking splits long evidence sections into searchable units. This project uses
deterministic character-based limits instead of model-generated chunk summaries.

Deterministic chunking is useful because:

- The same input creates the same chunks.
- Evaluation can refer to stable chunk IDs.
- A retrieval miss can be traced to a specific expected evidence unit.
- Reindexing does not create duplicate Qdrant points by accident.

Chunks preserve source metadata such as document ID, NCT ID, section, URL, and
content hash.

## 5. Agent and tool calling

The discovery and answering stages use bounded agents rather than free-form
multi-agent collaboration.

- The discovery agent decides when to search ClinicalTrials.gov.
- A small current-time tool gives it the date needed for recency controls.
- The answering agent can request trial metadata for allowlisted NCT IDs present
  in retrieved evidence.
- Step and tool-call limits prevent indefinite loops.

The orchestration layer itself is deterministic Python. It calls retrieval and
answering in a fixed order. This makes failures easier to locate than if the
question-to-answer flow were also controlled by an autonomous planner.

## 6. DeepSeek and the OpenAI SDK

DeepSeek exposes an API compatible with the OpenAI Chat Completions shape. The
project uses the `openai` Python package as transport, but the model is selected
through DeepSeek configuration:

```dotenv
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

The `openai` package does not imply that an OpenAI model is being used.

The answer prompt requires structured output containing either claims with
citation IDs or an explicit insufficient-evidence response. The application then
validates that output independently.

## 7. Citation validation

A model-generated citation is not trusted by itself. The answer request receives:

- Retrieval evidence with stable chunk IDs.
- Optional metadata lookup results.

Each claim must reference one or more of those IDs. The validation layer rejects
unknown retrieval chunks and metadata citations without a successful lookup.

Evaluation rechecks citation validity and reports it separately from retrieval
quality. This separation makes it possible to distinguish:

- Correct evidence was missing.
- Evidence was present but not retrieved.
- Evidence was retrieved but cited incorrectly.
- Citations were present but required facts were missing.
- The system answered an unanswerable question.

## 8. Artifact-oriented architecture

Each stage writes JSON artifacts instead of passing hidden in-memory state.

Benefits:

- A user can inspect every stage.
- A failed downstream stage can be debugged without repeating upstream API calls.
- Saved evaluation does not require Docker or an LLM.
- Tests can use small deterministic fixtures.
- Reports can link artifact IDs and reproduce configuration.

JSON is used for structured single records. JSONL is used for corpus documents and
chunks because one record per line is easy to stream and inspect.

Atomic writes reduce the chance of a partially written artifact.

## 9. Evaluation concepts

The evaluator separates several kinds of quality:

| Metric | Beginner interpretation |
| --- | --- |
| Retrieval hit@k | Did top-k results contain at least one expected chunk? |
| Recall@k | What fraction of all expected chunks were found? |
| MRR | How high did the first expected chunk rank? |
| Citation validity | Do cited IDs resolve to authorized evidence or metadata? |
| Citation coverage | Does each factual claim have a citation? |
| Key-point coverage | Did the claims contain required reference phrases? |
| Forbidden violations | Did claims contain statements explicitly marked wrong? |
| Refusal correctness | Did the system answer answerable cases and abstain on unanswerable cases? |

The current evaluator is a transparent baseline, not a semantic judge. A low
key-point score can mean the answer is missing a fact, or that the answer phrased
the fact differently from the fixed phrase.

The comparison layer permits exactly one configuration change so an improvement can
be attributed to a controlled variable such as retrieval limit.

## 10. Presentation and trust

Presentation operates on saved, validated claims. It does not call an LLM.

This means:

- It cannot add new factual prose.
- The same artifact and renderer version produce the same text.
- All claims remain visible in supporting detail.
- Sources are numbered by first citation appearance.

The UI deliberately avoids a per-answer trust percentage. Benchmark scores are
system-level measurements and are not calibrated probabilities that a particular
answer is correct.

## 11. Docker Compose

`compose.yml` defines two localhost-only services:

| Service | Host port | Container port |
| --- | --- | --- |
| TEI embeddings | 8080 | 80 |
| Qdrant | 6333 | 6333 |

Both use named volumes for persistence. The application discovers them through
environment variables rather than Docker-specific host names because the Python
process runs on the host, outside the Compose network.

Common commands:

```bash
docker compose up -d
docker compose ps
docker compose logs -f embeddings
docker compose stop
```

## 12. Python project structure

The project uses a `src/` layout:

```text
src/clinical_doc_assist/
  research/
  corpus/
  retrieval/
  answering/
  orchestration/
  evaluation/
```

Each package owns one stage and exposes a CLI entry point from `pyproject.toml`.
Dataclasses in `models.py` define stage inputs, outputs, statuses, and validation.

The base `clinical_doc_assist` package also includes a generic starter CLI and
small configuration/tool examples. The feature-specific package commands are the
primary project workflow.

## 13. Testing and code quality

| Tool or technique | Purpose |
| --- | --- |
| pytest | Unit, contract, CLI, and integration tests |
| Fixed fixtures | Deterministic stage inputs without network calls |
| Env-gated Docker tests | Verify real TEI and Qdrant behavior when explicitly enabled |
| Ruff lint | Catch unused imports, import ordering, common bugs, and style issues |
| Ruff format | Keep formatting consistent |
| Type hints | Document interfaces and support editor feedback |
| `git diff --check` | Detect whitespace errors before commit |

The default suite is offline-first. Docker tests run only when
`RUN_DOCKER_INTEGRATION=1` is set.

## 14. Spec-Driven Development

The repository uses GitHub Spec Kit:

```text
constitution
  -> feature specification
  -> plan
  -> tasks
  -> implementation
  -> tests and changelog
```

The key repository rules are:

- Review `.specify/memory/constitution.md` before changing user-visible behavior.
- Keep ingestion, answering, and evaluation independently controlled.
- Do not advance from specification to planning or implementation without approval.
- Keep artifacts, tests, tasks, and changelog entries traceable.

## 15. Suggested learning path

If you are new to the repository, read and run it in this order:

1. [Architecture brief](architecture.md)
2. [Usage guide](usage.md)
3. Discovery tests and `research` code.
4. Corpus tests and deterministic chunking.
5. Retrieval tests, Qdrant point IDs, and TEI.
6. Answering tests, especially citation validation.
7. Orchestration models and linked pipeline records.
8. Evaluation metrics and the fixed case set.
9. Presentation invariants.
10. Spec Kit artifacts under `specs/007-rag-evaluation/`.

That order follows one evidence item from public source discovery to a readable,
evaluated answer.
