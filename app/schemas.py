from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class EmbeddingRequest(BaseModel):
    # extra="allow": Ollama ignores unknown parameters, so anything the client
    # sends beyond this schema still reaches the upstream untouched.
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    # OpenAI also accepts token IDs here; Ollama's /v1/embeddings does not, so
    # they are rejected below with an explicit message instead of being
    # forwarded to an upstream that would refuse them anyway.
    input: str | list[str]
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int | None = Field(default=None, ge=1)
    user: str | None = None

    @field_validator("input", mode="before")
    @classmethod
    def _reject_token_ids(cls, value: Any) -> Any:
        # mode="before": the type union below would reject token IDs with a
        # generic message before this validator ever ran.
        if isinstance(value, list) and any(not isinstance(item, str) for item in value):
            raise ValueError("must be a string or a list of strings; token IDs are not supported")
        return value

    def to_upstream_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


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
