from tests.conftest import AUTH


def test_lists_only_allowed_models(client):
    body = client.get("/v1/models", headers=AUTH).json()
    assert body["object"] == "list"
    assert [m["id"] for m in body["data"]] == ["lfm25-8b", "qwen3.5:4b"]
    assert all(m["object"] == "model" for m in body["data"])


def test_health_does_not_require_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_routes_use_openai_error_format(client):
    response = client.get("/api/tags", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "invalid_request_error"
