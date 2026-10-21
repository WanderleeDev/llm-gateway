import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_KEY = "test-key-123"
AUTH = {"Authorization": f"Bearer {TEST_KEY}"}

CHAT_BODY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hola"},
            "finish_reason": "stop",
        }
    ],
}


class AsyncSSE(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


class FakeOllama:
    """Simula la API de Ollama. Guarda las peticiones recibidas para inspeccionarlas."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status >= 400:
            return httpx.Response(self.status, text="model crashed")
        if json.loads(request.content).get("stream"):
            # Async stream: the app client reads the upstream with aiter_raw()
            return httpx.Response(
                200,
                stream=AsyncSSE([b'data: {"choices":[{"delta":{"content":"Ho"}}]}\n\n', b"data: [DONE]\n\n"]),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(200, json=CHAT_BODY)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def last_payload(self) -> dict:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def fake_ollama() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        gateway_api_keys=TEST_KEY,
        allowed_models="lfm25-8b,qwen3.5:4b",
        max_concurrent=1,
        queue_timeout=0.5,
    )


@pytest.fixture
def client(settings: Settings, fake_ollama: FakeOllama) -> Iterator[TestClient]:
    app = create_app(settings, transport=fake_ollama.transport)
    with TestClient(app) as test_client:
        yield test_client
