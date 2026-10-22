from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.deps import SettingsDep
from app.schemas import ModelList, ModelObject

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


@router.get("/models")
async def list_models(settings: SettingsDep) -> ModelList:
    # Both families are listed because OpenAI clients discover models through
    # this endpoint; each route still enforces its own allowlist.
    ids = [*settings.models, *settings.embedding_models]
    return ModelList(data=[ModelObject(id=model) for model in ids])
