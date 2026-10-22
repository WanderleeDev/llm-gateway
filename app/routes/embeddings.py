from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.deps import ClientDep, LimiterDep, SettingsDep
from app.errors import APIError
from app.schemas import EmbeddingRequest
from app.upstream import complete_embedding

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


@router.post("/embeddings")
async def embeddings(
    body: EmbeddingRequest,
    settings: SettingsDep,
    client: ClientDep,
    limiter: LimiterDep,
):
    # Ollama serves /v1/embeddings with the same OpenAI shape, so the gateway
    # only enforces its own allowlist and forwards the body untouched.
    if body.model not in settings.embedding_models:
        raise APIError(
            404,
            f"The model '{body.model}' does not exist",
            "invalid_request_error",
            "model_not_found",
        )

    return JSONResponse(await complete_embedding(client, body.to_upstream_payload(), limiter))
