# Research: Evidence-Grounded Answers

**Status**: Complete for plan review

## Scope

No external technology research is required. The decisions below follow the
existing feature 004 artifact contract, the current OpenAI-compatible DeepSeek
client, and the project constitution. They intentionally optimize for a small,
inspectable stage instead of a general agent framework.

## R-001: Use the Retrieval Run as the Sole Input

- **Decision**: Accept one saved feature 004 retrieval run and read the question
  from `query.text`.
- **Rationale**: The retrieval run already identifies the question that produced
  the evidence. Repeating the question as a CLI argument creates a mismatch risk
  and makes failed runs harder to reproduce.
- **Alternatives considered**:
  - Accept a separate question and retrieve again: duplicates feature 004 and
    breaks the stage boundary.
  - Accept a replacement question against saved evidence: creates an unmeasured
    query-to-evidence mismatch.

## R-002: Keep Answering Single-Turn

- **Decision**: One answer run handles one retrieval result and no conversation
  history.
- **Rationale**: The project needs a reliable RAG baseline before chat memory or
  follow-up retrieval is useful.
- **Alternatives considered**:
  - Add chat sessions now: adds state management and evaluation cases without
    helping the first baseline.
  - Pass prior answers as context: risks carrying unsupported claims forward.

## R-003: Structure Citations per Claim

- **Decision**: The model returns concise claims, and each claim names one or more
  allowed citation identifiers.
- **Rationale**: A top-level citation list cannot show which statement depends on
  which evidence. Claim-level citations make validation and later faithfulness
  review attributable without adding another agent.
- **Alternatives considered**:
  - One answer string with one citation list: simpler, but citation-to-claim
    mapping is ambiguous.
  - Parse inline citations from prose: brittle and harder to validate.

## R-004: Cap the Evidence Packet

- **Decision**: Use at most the 10 highest-ranked retrieval results.
- **Rationale**: The default retrieval run returns five results. A fixed ceiling
  prevents an artifact with 50 results from unexpectedly increasing latency and
  token cost.
- **Alternatives considered**:
  - Accept every result up to 50: unpredictable context size.
  - Add automatic reranking or summarization: speculative complexity before a
    measured retrieval problem.

## R-005: Treat Evidence as Untrusted Data

- **Decision**: Prompts place retrieved text in an evidence-data section and state
  that instructions inside evidence must not be followed.
- **Rationale**: Public documents are untrusted input and may contain misleading
  text. The role and citation rules belong in the system prompt, not in retrieved
  content.
- **Alternatives considered**:
  - Concatenate evidence into the instruction section: increases prompt-injection
    risk and blurs trust boundaries.

## R-006: Use One Application-Controlled Metadata Tool

- **Decision**: Permit `fetch_trial_metadata` only for NCT identifiers already in
  retrieved evidence, with at most three lookups per run.
- **Rationale**: Structured trial status or intervention metadata can clarify
  evidence, but unrestricted browsing or arbitrary NCT lookups would expand the
  agent's scope and attack surface.
- **Alternatives considered**:
  - Pre-fetch metadata for every trial: unnecessary calls and cost.
  - General web search: defeats the controlled public-corpus boundary.

## R-007: Validate Citation Identity, Not Semantic Entailment

- **Decision**: Application code validates citation identifiers and canonical
  provenance. Semantic faithfulness is measured by feature 006.
- **Rationale**: Deterministic code can prove that a citation exists and points to
  supplied evidence. It cannot prove that the sentence is supported without a
  separate judge or human rubric.
- **Alternatives considered**:
  - Claim that citation validation guarantees grounding: incorrect.
  - Add an LLM verifier in feature 005: adds a second model, latency, cost, and a
    prematurely complex evaluation problem.

## R-008: Make Abstention a Successful Stage Outcome

- **Decision**: Empty retrieval and model-declared insufficient evidence produce an
  `insufficient_evidence` artifact with exit code `0`. Malformed input exits `2`;
  runtime or citation-validation failure exits `1`.
- **Rationale**: A correct refusal is a successful safety behavior, not an
  infrastructure failure.
- **Alternatives considered**:
  - Use one generic failure status: hides the difference between safe abstention
    and a broken workflow.

## R-009: Preserve the Docker Boundary

- **Decision**: Feature 005 consumes a saved artifact and does not contact TEI or
  Qdrant.
- **Rationale**: The stage must be independently controllable. Docker is needed to
  create retrieval data, not to generate an answer from data that already exists.
- **Alternatives considered**:
  - Reconnect to Qdrant during answering: couples stages and makes saved-run
    reproduction dependent on live infrastructure.

## R-010: Persist a Self-Contained Answer Snapshot

- **Decision**: Copy the accepted question, evidence snapshot, citations, tool
  activity, model configuration, usage, timing, and errors into one JSON artifact.
- **Rationale**: A reviewer can diagnose an answer without reconstructing the
  environment or guessing which retrieval file was used.
- **Alternatives considered**:
  - Store only the retrieval ID and answer text: smaller, but insufficient for
    later audit and evaluation.
