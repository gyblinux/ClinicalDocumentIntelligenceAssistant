"""HTTP client for local Text Embeddings Inference."""

from __future__ import annotations

from typing import Any

import httpx

from clinical_doc_assist.retrieval.models import (
    EmbeddingInfo,
    RetrievalServiceError,
)


class TEIClient:
    """Small client for TEI health, model info, and embeddings."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        embedding_dimension: int,
        http_client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._embedding_dimension = embedding_dimension
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def health(self) -> None:
        self._get("/health")

    def info(self) -> EmbeddingInfo:
        payload = self._json_response("/info")
        if not isinstance(payload, dict):
            raise RetrievalServiceError("TEI /info response must be an object.")
        model_id = payload.get("model_id", self._model)
        max_input_length = payload.get("max_input_length")
        return EmbeddingInfo(
            model_id=str(model_id),
            dimension=self._embedding_dimension,
            max_input_length=(max_input_length if isinstance(max_input_length, int) else None),
            model_sha=(
                str(payload["model_sha"]) if isinstance(payload.get("model_sha"), str) else None
            ),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = self._json_response("/embed", method="POST", json={"inputs": texts})
        if not isinstance(payload, list) or len(payload) != len(texts):
            raise RetrievalServiceError("TEI embedding count did not match the input count.")

        vectors: list[list[float]] = []
        for value in payload:
            if not isinstance(value, list) or len(value) != self._embedding_dimension:
                raise RetrievalServiceError("TEI embedding dimension did not match configuration.")
            if not all(isinstance(number, int | float) for number in value):
                raise RetrievalServiceError("TEI returned a non-numeric embedding.")
            vectors.append([float(number) for number in value])
        return vectors

    def _get(self, path: str) -> httpx.Response:
        try:
            response = self._client.get(f"{self._base_url}{path}")
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise RetrievalServiceError(f"TEI request failed: {exc}") from exc

    def _json_response(
        self,
        path: str,
        *,
        method: str = "GET",
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                f"{self._base_url}{path}",
                json=json,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise RetrievalServiceError(f"TEI request failed: {exc}") from exc
        except ValueError as exc:
            raise RetrievalServiceError("TEI returned invalid JSON.") from exc
