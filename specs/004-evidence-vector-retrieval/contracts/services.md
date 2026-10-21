# Service Contract: TEI and Qdrant

## TEI

Image:

```text
ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
```

Model:

```text
BAAI/bge-small-en-v1.5
```

Host endpoint:

```text
http://127.0.0.1:8080
```

Required operations:

- `GET /health`
- `GET /info`
- `POST /embed` with `{"inputs": ["text", ...]}`

The response MUST return one numeric vector per input with a consistent dimension.

## Qdrant

Image:

```text
qdrant/qdrant:v1.19.2
```

Host endpoint:

```text
http://127.0.0.1:6333
```

Dashboard:

```text
http://127.0.0.1:6333/dashboard
```

The application creates and manages the configured collection. Collection vectors
use Cosine distance and the configured embedding dimension.

## Compose Discovery

When the application runs on the host:

```text
TEI_URL=http://127.0.0.1:8080
QDRANT_URL=http://127.0.0.1:6333
```

When the application later runs inside the same Compose network:

```text
TEI_URL=http://embeddings:80
QDRANT_URL=http://qdrant:6333
```

Ports bind to `127.0.0.1` for the host application. Qdrant authentication is
optional locally but required if the service is exposed beyond localhost.
