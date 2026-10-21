"""Forwards requests to Ollama (its API is OpenAI-compatible under /v1/)."""

from typing import Any

import httpx
from fastapi.responses import StreamingResponse

from app.concurrency import ConcurrencyLimiter
from app.errors import APIError

CHAT_PATH = "/v1/chat/completions"


async def _error_from_upstream(response: httpx.Response) -> APIError:
    text = (await response.aread()).decode(errors="replace")[:500]
    return APIError(response.status_code, text or "Upstream error", "api_error")


async def complete_chat(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    limiter: ConcurrencyLimiter,
) -> dict[str, Any]:
    async with limiter.slot():
        try:
            response = await client.post(CHAT_PATH, json=payload)
        except httpx.HTTPError as exc:
            raise APIError(502, "Upstream unavailable") from exc

    if response.status_code >= 400:
        raise await _error_from_upstream(response)
    return response.json()


async def stream_chat(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    limiter: ConcurrencyLimiter,
) -> StreamingResponse:
    # The slot is released when the stream ends, not when the response is returned.
    await limiter.acquire()
    try:
        upstream = await client.send(
            client.build_request("POST", CHAT_PATH, json=payload),
            stream=True,
        )
    except httpx.HTTPError as exc:
        limiter.release()
        raise APIError(502, "Upstream unavailable") from exc

    if upstream.status_code >= 400:
        error = await _error_from_upstream(upstream)
        await upstream.aclose()
        limiter.release()
        raise error

    async def body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            limiter.release()

    return StreamingResponse(body(), media_type="text/event-stream")
