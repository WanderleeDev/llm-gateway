import pytest
from pydantic import ValidationError

from app.schemas import ChatCompletionRequest, EmbeddingRequest


def test_rejects_unknown_role():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(model="lfm25-8b", messages=[{"role": "robot", "content": "x"}])


def test_rejects_empty_messages():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(model="lfm25-8b", messages=[])


def test_rejects_non_positive_max_tokens():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="lfm25-8b", messages=[{"role": "user", "content": "x"}], max_tokens=0
        )


def test_upstream_payload_drops_none_and_keeps_extras():
    request = ChatCompletionRequest(
        model="lfm25-8b",
        messages=[{"role": "user", "content": "x"}],
        top_p=0.9,
    )
    payload = request.to_upstream_payload()
    assert "max_tokens" not in payload
    assert payload["top_p"] == 0.9
    assert payload["stream"] is False


def test_embedding_rejects_token_ids():
    # Ollama refuses token IDs; the schema must reject them before that.
    with pytest.raises(ValidationError):
        EmbeddingRequest(model="qwen3-embedding:0.6b", input=[[1, 2, 3]])


def test_embedding_rejects_unknown_encoding_format():
    with pytest.raises(ValidationError):
        EmbeddingRequest(model="qwen3-embedding:0.6b", input="hola", encoding_format="int8")


def test_embedding_payload_drops_none_and_keeps_extras():
    request = EmbeddingRequest(model="qwen3-embedding:0.6b", input="hola", top_k=5)
    payload = request.to_upstream_payload()
    assert "dimensions" not in payload
    assert "user" not in payload
    assert payload["encoding_format"] == "float"
    assert payload["top_k"] == 5
