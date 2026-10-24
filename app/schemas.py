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
    #: Ollama's native on/off switch, declared here only so it can be translated:
    #: `/v1/chat/completions` does not know it, so forwarding it as an extra field
    #: would be silently ignored. It is a boolean on purpose — the configured model
    #: publishes `thinking.values: [false, true]`, with no named levels to choose.
    #: A client that needs a level can send `reasoning_effort` itself.
    think: bool | None = None

    def to_upstream_payload(self, default_reasoning_effort: str = "") -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        # Ollama does not know the "developer" role; it is equivalent to "system".
        for message in payload["messages"]:
            if message["role"] == "developer":
                message["role"] = "system"
        # `think` belongs to /api/chat, not to the endpoint this gateway calls, so
        # it is translated and never sent as-is. Turning thinking off is the only
        # direction that needs a field: "none" is the sole off switch on /v1.
        # Turning it on sends nothing, so the model's own default applies.
        think = payload.pop("think", None)
        if think is False:
            payload["reasoning_effort"] = "none"
        # The default only fills the gap: a client that already chose, with `think`
        # or with an explicit effort (flat or nested), keeps control.
        if (
            default_reasoning_effort
            and think is None
            and "reasoning_effort" not in payload
            and "reasoning" not in payload
        ):
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
