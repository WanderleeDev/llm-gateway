from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.concurrency import ConcurrencyLimiter
from app.config import Settings
from app.errors import register_error_handlers
from app.routes import chat, models


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Factory de la aplicación. `transport` permite simular Ollama en los tests."""
    if settings is None:
        settings = Settings()
    if not settings.api_keys:
        # Falla cerrado: un gateway sin keys no debe arrancar
        raise RuntimeError("GATEWAY_API_KEYS must define at least one key")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            base_url=settings.ollama_url,
            timeout=httpx.Timeout(settings.upstream_timeout, connect=5.0),
            transport=transport,
        ) as client:
            app.state.client = client
            app.state.limiter = ConcurrencyLimiter(settings.max_concurrent, settings.queue_timeout)
            yield

    app = FastAPI(
        title="LLM Gateway",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(models.router)
    app.include_router(chat.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
