from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TEST_KEY


def test_lists_chat_and_embedding_models(client):
    body = client.get("/v1/models", headers=AUTH).json()
    assert body["object"] == "list"
    assert [m["id"] for m in body["data"]] == ["lfm25-8b", "qwen3.5:4b", "qwen3-embedding:0.6b"]
    assert all(m["object"] == "model" for m in body["data"])


def test_lists_only_chat_models_when_no_embedding_models_are_configured(fake_ollama):
    settings = Settings(
        _env_file=None,
        gateway_api_keys=TEST_KEY,
        allowed_models="lfm25-8b",
        allowed_embedding_models="",
    )
    with TestClient(create_app(settings, transport=fake_ollama.transport)) as c:
        body = c.get("/v1/models", headers=AUTH).json()
    assert [m["id"] for m in body["data"]] == ["lfm25-8b"]


def test_health_does_not_require_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_routes_use_openai_error_format(client):
    response = client.get("/api/tags", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "invalid_request_error"
