from __future__ import annotations

import httpx
import pytest

from clinical_doc_assist.retrieval.models import RetrievalServiceError
from clinical_doc_assist.retrieval.tei import TEIClient


def test_tei_health_info_and_batch_embedding() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, text="ok")
        if request.url.path == "/info":
            return httpx.Response(
                200,
                json={
                    "model_id": "test-model",
                    "model_sha": "abc123",
                    "max_input_length": 512,
                },
            )
        return httpx.Response(200, json=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    client = TEIClient(
        base_url="http://tei.test",
        model="test-model",
        embedding_dimension=3,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.health()
    info = client.info()
    vectors = client.embed(["one", "two"])

    assert info.model_id == "test-model"
    assert info.model_sha == "abc123"
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert requests[-1].url.path == "/embed"


def test_tei_rejects_dimension_mismatch_and_service_errors() -> None:
    bad_vector_client = TEIClient(
        base_url="http://tei.test",
        model="test-model",
        embedding_dimension=3,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[[0.1, 0.2]]))
        ),
    )
    with pytest.raises(RetrievalServiceError, match="dimension"):
        bad_vector_client.embed(["one"])

    unavailable_client = TEIClient(
        base_url="http://tei.test",
        model="test-model",
        embedding_dimension=3,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"error": "down"}))
        ),
    )
    with pytest.raises(RetrievalServiceError, match="TEI"):
        unavailable_client.health()
