from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    # extra="allow": parameters such as temperature, tool_choice or top_p
    # are forwarded to Ollama without declaring them one by one.
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    max_tokens: int | None = Field(default=None, ge=1)
    tools: list[dict[str, Any]] | None = None

    def to_upstream_payload(self, default_reasoning_effort: str = "") -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        # Ollama does not know the "developer" role; it is equivalent to "system".
        for message in payload["messages"]:
            if message["role"] == "developer":
                message["role"] = "system"
        # The default only fills the gap: if the client already sent
        # reasoning_effort (declared or via extra), its value wins.
        if default_reasoning_effort and "reasoning_effort" not in payload:
            payload["reasoning_effort"] = default_reasoning_effort
        return payload


class ErrorBody(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "ollama"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]
