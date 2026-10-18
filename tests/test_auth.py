import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import AUTH, TEST_KEY


def test_valid_key_is_accepted(client):
    assert client.get("/v1/models", headers=AUTH).status_code == 200


def test_missing_header_returns_openai_error(client):
    response = client.get("/v1/models")
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["type"] == "authentication_error"
    assert error["code"] == "invalid_api_key"


def test_wrong_key_is_rejected(client):
    response = client.get("/v1/models", headers={"Authorization": "Bearer otra-clave"})
    assert response.status_code == 401


@pytest.mark.parametrize("header", [f"Basic {TEST_KEY}", "Bearer", f"Token {TEST_KEY}"])
def test_non_bearer_schemes_are_rejected(client, header):
    assert client.get("/v1/models", headers={"Authorization": header}).status_code == 401


def test_x_api_key_header_is_not_accepted(client):
    # OpenAI solo usa Bearer; no ampliamos la superficie de autenticación
    assert client.get("/v1/models", headers={"X-API-Key": TEST_KEY}).status_code == 401


def test_app_refuses_to_start_without_keys():
    settings = Settings(_env_file=None, gateway_api_keys="")
    with pytest.raises(RuntimeError):
        create_app(settings)
