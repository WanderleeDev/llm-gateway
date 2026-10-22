from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import AUTH, EMBEDDING_BODY, TEST_KEY

EMBEDDING_REQUEST = {"model": "qwen3-embedding:0.6b", "input": "hola"}


def make_client(allowed_embedding_models: str, fake_ollama) -> TestClient:
    settings = Settings(
        _env_file=None,
        gateway_api_keys=TEST_KEY,
        allowed_models="lfm25-8b",
        allowed_embedding_models=allowed_embedding_models,
    )
    app = create_app(settings, transport=fake_ollama.transport)
    return TestClient(app)


def test_forwards_request_and_returns_response(client, fake_ollama):
    response = client.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)

    assert response.status_code == 200
    assert response.json() == EMBEDDING_BODY
    assert fake_ollama.last_payload() == {
        "model": "qwen3-embedding:0.6b",
        "input": "hola",
        "encoding_format": "float",
    }


def test_unknown_model_returns_404(client, fake_ollama):
    response = client.post(
        "/v1/embeddings",
        json={**EMBEDDING_REQUEST, "model": "no-existe"},
        headers=AUTH,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
    assert fake_ollama.requests == []  # never reaches Ollama


def test_chat_model_is_not_accepted_for_embeddings(client, fake_ollama):
    # ALLOWED_MODELS and ALLOWED_EMBEDDING_MODELS are separate on purpose.
    response = client.post(
        "/v1/embeddings",
        json={**EMBEDDING_REQUEST, "model": "lfm25-8b"},
        headers=AUTH,
    )
    assert response.status_code == 404
    assert fake_ollama.requests == []


def test_token_ids_are_rejected_with_400(client, fake_ollama):
    # Ollama refuses token IDs; the gateway must explain it, not forward them.
    response = client.post(
        "/v1/embeddings",
        json={"model": "qwen3-embedding:0.6b", "input": [[1, 2, 3]]},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert "token IDs" in response.json()["error"]["message"]
    assert fake_ollama.requests == []


def test_list_input_is_forwarded(client, fake_ollama):
    client.post(
        "/v1/embeddings",
        json={"model": "qwen3-embedding:0.6b", "input": ["hola", "chau"]},
        headers=AUTH,
    )
    assert fake_ollama.last_payload()["input"] == ["hola", "chau"]


def test_dimensions_is_forwarded(client, fake_ollama):
    # Ollama honours Matryoshka truncation and returns the requested width.
    client.post(
        "/v1/embeddings",
        json={**EMBEDDING_REQUEST, "dimensions": 256},
        headers=AUTH,
    )
    assert fake_ollama.last_payload()["dimensions"] == 256


def test_omitted_optional_fields_are_not_forwarded(client, fake_ollama):
    client.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)
    assert "dimensions" not in fake_ollama.last_payload()
    assert "user" not in fake_ollama.last_payload()


def test_upstream_error_keeps_status_and_openai_format(client, fake_ollama):
    fake_ollama.status = 500
    response = client.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)
    assert response.status_code == 500
    assert response.json()["error"]["type"] == "api_error"


def test_slot_is_released_after_upstream_error(client, fake_ollama):
    # max_concurrent=1 in the fixture: if the error does not release the slot,
    # the next request would get a 429.
    fake_ollama.status = 500
    client.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)

    fake_ollama.status = 200
    response = client.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)
    assert response.status_code == 200


def test_embeddings_require_auth(client):
    response = client.post("/v1/embeddings", json=EMBEDDING_REQUEST)
    assert response.status_code == 401


def test_no_embedding_models_configured_rejects_everything(fake_ollama):
    with make_client("", fake_ollama) as c:
        response = c.post("/v1/embeddings", json=EMBEDDING_REQUEST, headers=AUTH)
    assert response.status_code == 404
    assert fake_ollama.requests == []
