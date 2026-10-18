from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.concurrency import ConcurrencyLimiter
from app.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.client


def get_limiter(request: Request) -> ConcurrencyLimiter:
    return request.app.state.limiter


SettingsDep = Annotated[Settings, Depends(get_settings)]
ClientDep = Annotated[httpx.AsyncClient, Depends(get_client)]
LimiterDep = Annotated[ConcurrencyLimiter, Depends(get_limiter)]
