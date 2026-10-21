# Research: Evidence Embedding and Vector Retrieval

## Embedding Service

**Decision**: Run Hugging Face Text Embeddings Inference in CPU Docker mode.

**Rationale**: TEI provides local embeddings, batching, health/model metadata, and
an HTTP API without installing PyTorch or Transformers in the application.

**Alternatives considered**: Host-side `sentence-transformers`, hosted embedding
APIs, or asking DeepSeek Flash to emit vectors. These add dependency, cost, or
quality problems.

## TEI Image and Model

**Decision**: Use `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9` with
`BAAI/bge-small-en-v1.5`.

**Rationale**: TEI documents `cpu-1.9` for x86_64 CPU use and supports BERT-family
models. BGE-small provides 384-dimensional vectors with a larger input limit than
MiniLM, fitting the current 1,200-character chunks.

**Alternatives considered**: `all-MiniLM-L6-v2` is smaller but may truncate longer
chunks. Exact image digests should be pinned for stricter reproducibility.

## TEI API

**Decision**: Use `POST /embed` through existing `httpx`.

**Rationale**: The native endpoint accepts one input or a batch and avoids adding
another client abstraction. Existing `GET /health` and `GET /info` support
preflight and model diagnostics.

**Alternatives considered**: The OpenAI-compatible `/v1/embeddings` endpoint also
works, but TEI’s native API has fewer compatibility assumptions.

## Vector Store

**Decision**: Use Qdrant `v1.19.2` with `qdrant-client`.

**Rationale**: Qdrant is free, persistent, payload-aware, and runs as one local
container. The client removes low-level REST request handling without introducing
an ML framework.

**Alternatives considered**: NumPy files require custom persistence; FAISS still
requires embedding services; Chroma embedding behavior is client-side by default;
PostgreSQL and larger vector systems add operational scope.

## Point Identity and Reindexing

**Decision**: Generate UUID5 point IDs from each stable feature 003 `chunk_id` and
upsert with wait enabled.

**Rationale**: Reindexing unchanged chunks updates the same points instead of
creating duplicates.

**Alternatives considered**: Random point IDs create duplicates; sequential
integer IDs are unstable when sources change.

## Collection Replacement

**Decision**: Reuse an existing collection for idempotent reindexing, with an
explicit `--replace` option for a clean rebuild.

**Rationale**: Reuse is fast and safe for unchanged chunks. `--replace` provides a
controlled way to remove stale points after corpus changes without silently
deleting a collection.

**Alternatives considered**: Always deleting was rejected as surprising; never
deleting leaves stale points after major corpus revisions.

## Local Service Discovery

**Decision**: Configure `TEI_URL` and `QDRANT_URL`; host defaults are
`http://127.0.0.1:8080` and `http://127.0.0.1:6333`.

**Rationale**: Host execution matches the current project. Compose service names
can replace localhost later if the application is containerized.

**Alternatives considered**: Hard-coded container DNS names fail when the app runs
outside Docker.

## Answer Boundary

**Decision**: Stop after ranked evidence chunks.

**Rationale**: Retrieval quality must be inspectable before adding answer
generation and citation validation.

**Alternatives considered**: Combining retrieval and answer generation in one
feature makes failures harder to attribute and increases cost.
