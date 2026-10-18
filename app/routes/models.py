from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.deps import SettingsDep
from app.schemas import ModelList, ModelObject

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


@router.get("/models")
async def list_models(settings: SettingsDep) -> ModelList:
    return ModelList(data=[ModelObject(id=model) for model in settings.models])
