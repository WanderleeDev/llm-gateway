from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Niveles de razonamiento que Ollama entiende en reasoning_effort.
VALID_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Configuración del gateway. Se lee de variables de entorno o de .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://127.0.0.1:11434"
    gateway_api_keys: str = ""
    allowed_models: str = "lfm25-8b"
    max_concurrent: int = Field(default=2, ge=1)
    queue_timeout: float = Field(default=30.0, gt=0)
    upstream_timeout: float = Field(default=300.0, gt=0)
    #: Razonamiento inyectado cuando el cliente no lo especifica. Ollama por
    #: defecto deja el thinking encendido y quema tokens (un prompt trivial
    #: llegó a costar 3877). "none" lo apaga; cadena vacía no inyecta nada
    #: y deja el comportamiento nativo de Ollama.
    default_reasoning_effort: str = "none"

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
