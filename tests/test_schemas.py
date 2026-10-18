import pytest
from pydantic import ValidationError

from app.schemas import ChatCompletionRequest


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
