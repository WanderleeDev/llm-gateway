from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.deps import SettingsDep

#: The docs render from the package directory, not the CWD, so they work
#: the same locally, in tests and inside the container.
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def render_usage(request: Request, settings: SettingsDep) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "usage.html",
        {
            "base_url": str(request.base_url),
            "models": settings.models,
            "embedding_models": settings.embedding_models,
            "default_reasoning_effort": settings.default_reasoning_effort,
            "auth_scheme": "Bearer",
        },
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, settings: SettingsDep) -> HTMLResponse:
    return render_usage(request, settings)


@router.get("/docs", response_class=HTMLResponse)
async def docs(request: Request, settings: SettingsDep) -> HTMLResponse:
    return render_usage(request, settings)
