from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import AUTH, CHAT_BODY, TEST_KEY

CHAT_REQUEST = {
    "model": "lfm25-8b",
    "messages": [{"role": "user", "content": "Hola"}],
    "max_tokens": 64,
}


def test_forwards_request_and_returns_response(client, fake_ollama):
    response = client.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)

    assert response.status_code == 200
    assert response.json() == CHAT_BODY
    sent = fake_ollama.last_payload()
    assert sent["model"] == "lfm25-8b"
    assert sent["max_tokens"] == 64


def test_unknown_model_returns_404(client, fake_ollama):
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT_REQUEST, "model": "no-existe"},
        headers=AUTH,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
    assert fake_ollama.requests == []  # nunca llega a Ollama


def test_empty_messages_is_a_400(client):
    response = client.post(
        "/v1/chat/completions",
        json={"model": "lfm25-8b", "messages": []},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_developer_role_is_sent_as_system(client, fake_ollama):
    client.post(
        "/v1/chat/completions",
        json={
            "model": "lfm25-8b",
            "messages": [
                {"role": "developer", "content": "Sé breve"},
                {"role": "user", "content": "Hola"},
            ],
        },
        headers=AUTH,
    )
    assert fake_ollama.last_payload()["messages"][0]["role"] == "system"


def test_tools_and_extra_parameters_are_forwarded(client, fake_ollama):
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object"}}}]
    client.post(
        "/v1/chat/completions",
        json={**CHAT_REQUEST, "tools": tools, "temperature": 0.2, "tool_choice": "auto"},
        headers=AUTH,
    )
    sent = fake_ollama.last_payload()
    assert sent["tools"] == tools
    assert sent["temperature"] == 0.2
    assert sent["tool_choice"] == "auto"


def test_tool_result_round_trip_is_forwarded(client, fake_ollama):
    messages = [
        {"role": "user", "content": "¿Qué tiempo hace en Madrid?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "get_weather", "arguments": "{\"city\": \"Madrid\"}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "18 C, despejado"},
    ]
    client.post("/v1/chat/completions", json={"model": "lfm25-8b", "messages": messages}, headers=AUTH)

    sent_messages = fake_ollama.last_payload()["messages"]
    assert sent_messages[1]["tool_calls"][0]["id"] == "call_1"
    assert sent_messages[2]["tool_call_id"] == "call_1"


def test_streaming_passes_through_sse(client, fake_ollama):
    response = client.post(
        "/v1/chat/completions",
        json={**CHAT_REQUEST, "stream": True},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in response.text


def test_upstream_error_keeps_status_and_openai_format(client, fake_ollama):
    fake_ollama.status = 500
    response = client.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)
    assert response.status_code == 500
    assert response.json()["error"]["type"] == "api_error"


def test_slot_is_released_after_upstream_error(client, fake_ollama):
    # max_concurrent=1 en el fixture: si el error no libera el slot,
    # la siguiente petición daría 429.
    fake_ollama.status = 500
    client.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)

    fake_ollama.status = 200
    response = client.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)
    assert response.status_code == 200


def test_slot_is_released_after_stream(client, fake_ollama):
    client.post("/v1/chat/completions", json={**CHAT_REQUEST, "stream": True}, headers=AUTH)
    response = client.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)
    assert response.status_code == 200


def make_client(default_reasoning_effort: str, fake_ollama) -> TestClient:
    settings = Settings(
        _env_file=None,
        gateway_api_keys=TEST_KEY,
        allowed_models="lfm25-8b",
        default_reasoning_effort=default_reasoning_effort,
    )
    app = create_app(settings, transport=fake_ollama.transport)
    return TestClient(app)


def test_default_reasoning_effort_injected_when_client_omits_it(fake_ollama):
    # Sin especificarlo, Ollama deja el thinking encendido: un prompt trivial
    # llegó a costar 3877 tokens. El default del gateway lo cierra.
    with make_client("none", fake_ollama) as c:
        c.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)
    assert fake_ollama.last_payload()["reasoning_effort"] == "none"


def test_client_reasoning_effort_wins_over_default(fake_ollama):
    with make_client("none", fake_ollama) as c:
        c.post("/v1/chat/completions", json={**CHAT_REQUEST, "reasoning_effort": "high"}, headers=AUTH)
    assert fake_ollama.last_payload()["reasoning_effort"] == "high"


def test_empty_default_injects_nothing(fake_ollama):
    # DEFAULT_REASONING_EFFORT="" restaura el comportamiento nativo de Ollama.
    with make_client("", fake_ollama) as c:
        c.post("/v1/chat/completions", json=CHAT_REQUEST, headers=AUTH)
    assert "reasoning_effort" not in fake_ollama.last_payload()
