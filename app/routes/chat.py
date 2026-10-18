from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.deps import ClientDep, LimiterDep, SettingsDep
from app.errors import APIError
from app.schemas import ChatCompletionRequest
from app.upstream import complete_chat, stream_chat

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    settings: SettingsDep,
    client: ClientDep,
    limiter: LimiterDep,
):
    if body.model not in settings.models:
        raise APIError(
            404,
            f"The model '{body.model}' does not exist",
            "invalid_request_error",
            "model_not_found",
        )

    payload = body.to_upstream_payload(settings.default_reasoning_effort)
    if body.stream:
        return await stream_chat(client, payload, limiter)
    return JSONResponse(await complete_chat(client, payload, limiter))
