from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Reasoning levels that Ollama understands in reasoning_effort.
VALID_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Gateway configuration. Read from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://127.0.0.1:11434"
    gateway_api_keys: str = ""
    allowed_models: str = "qwen3.5:4b"
    #: Kept separate from allowed_models on purpose: a chat model cannot serve
    #: embeddings, and a client that discovers models through /v1/models must
    #: not be able to send either family to the wrong endpoint. Empty means
    #: /v1/embeddings rejects every model.
    allowed_embedding_models: str = ""
    max_concurrent: int = Field(default=2, ge=1)
    queue_timeout: float = Field(default=30.0, gt=0)
    upstream_timeout: float = Field(default=300.0, gt=0)
    #: Reasoning injected when the client does not specify it. Matches OpenAI, whose
    #: reasoning models think unless told otherwise, so a client that wants the fast
    #: path has to ask for it with `think: false` / `reasoning_effort: "none"`.
    #: Set it to "none" to make thinking off the default instead. Ollama leaves
    #: thinking on by itself, which is why this is injected at all.
    default_reasoning_effort: str = "medium"

    @field_validator("default_reasoning_effort")
    @classmethod
    def _validate_default_reasoning_effort(cls, value: str) -> str:
        if value not in VALID_REASONING_EFFORTS and value != "":
            raise ValueError(
                f"must be one of {', '.join(VALID_REASONING_EFFORTS)} or empty (no injection)"
            )
        return value

    @property
    def api_keys(self) -> list[str]:
        return _split_csv(self.gateway_api_keys)

    @property
    def models(self) -> list[str]:
        return _split_csv(self.allowed_models)

    @property
    def embedding_models(self) -> list[str]:
        return _split_csv(self.allowed_embedding_models)
