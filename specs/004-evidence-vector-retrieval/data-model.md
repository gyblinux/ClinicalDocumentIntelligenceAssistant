# Data Model: Evidence Embedding and Vector Retrieval

## RetrievalConfig

| Field | Type | Rule |
| --- | --- | --- |
| `tei_url` | URL | Defaults to `http://127.0.0.1:8080` |
| `tei_model` | string | Defaults to `BAAI/bge-small-en-v1.5` |
| `embedding_dimension` | integer | Defaults to `384` |
| `tei_batch_size` | integer | Defaults to `32`; must be positive |
| `qdrant_url` | URL | Defaults to `http://127.0.0.1:6333` |
| `qdrant_api_key` | string or null | Loaded from environment when configured |

## CorpusInput

| Field | Type | Rule |
| --- | --- | --- |
| `path` | path | Feature 003 build directory |
| `schema_version` | string | Must equal `1.0` |
| `build_id` | string | Required |
| `status` | enum | Must be `completed` or `partial` |
| `chunk_count` | integer | Must be greater than zero and match JSONL |
| `documents` | EvidenceDocument array | Loaded from `documents.jsonl` |
| `chunks` | EvidenceChunk array | Loaded from `chunks.jsonl` |

## EmbeddingInfo

| Field | Type | Rule |
| --- | --- | --- |
| `model_id` | string | Reported by TEI |
| `dimension` | integer | Must equal configured dimension |
| `max_input_length` | integer or null | Recorded from TEI when available |

## IndexManifest

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `index_id` | string | Unique local index-run identifier |
| `created_at` | ISO 8601 string | Run completion time |
| `corpus_build_id` | string | Feature 003 build used |
| `corpus_status` | string | `completed` or `partial` |
| `chunk_count` | integer | Input chunks |
| `point_count` | integer | Successfully upserted points |
| `tei_model` | string | Effective model |
| `embedding_dimension` | integer | Effective dimension |
| `qdrant_url` | URL | Service endpoint summary |
| `collection` | string | Qdrant collection |
| `distance` | string | Fixed `Cosine` |
| `replace_requested` | boolean | Whether collection was recreated |
| `errors` | string array | Visible failures |

## RetrievalQuery

| Field | Type | Rule |
| --- | --- | --- |
| `text` | string | Required and non-empty |
| `collection` | string | Required |
| `limit` | integer | Defaults to 5; range 1-50 |

## RetrievalResult

| Field | Type | Rule |
| --- | --- | --- |
| `rank` | integer | One-based rank |
| `score` | number | Qdrant cosine score |
| `chunk_id` | string | Original feature 003 chunk |
| `document_id` | string | Parent document |
| `nct_id` | string | Source identifier |
| `section` | string | Parent section |
| `text` | string | Exact chunk text |
| `source_url` | string | Citation source |
| `content_hash` | string | Chunk hash |

## RetrievalRun

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Fixed `1.0` |
| `retrieval_id` | string | Unique run identifier |
| `created_at` | ISO 8601 string | Query time |
| `query` | RetrievalQuery | Original request |
| `tei_model` | string | Embedding model |
| `collection` | string | Queried collection |
| `results` | RetrievalResult array | Ranked evidence |
| `status` | enum | `completed`, `no_results`, or `failed` |
| `errors` | string array | Visible failures |

## Qdrant Point ID

Use UUID5 with a fixed project namespace and the feature 003 `chunk_id` as the
name. The same chunk always maps to the same Qdrant point ID.

## State Transitions

```text
corpus_validated -> services_ready -> chunks_embedded -> points_upserted -> indexed
corpus_validated -> rejected
services_ready -> failed
indexed -> searched -> completed | no_results
```
