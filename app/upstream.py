"""Forwards requests to Ollama (its API is OpenAI-compatible under /v1/)."""

from typing import Any

import httpx
from fastapi.responses import StreamingResponse

from app.concurrency import ConcurrencyLimiter
from app.errors import APIError

CHAT_PATH = "/v1/chat/completions"
EMBEDDINGS_PATH = "/v1/embeddings"


async def _error_from_upstream(response: httpx.Response) -> APIError:
    text = (await response.aread()).decode(errors="replace")[:500]
    return APIError(response.status_code, text or "Upstream error", "api_error")


async def _complete(
    client: httpx.AsyncClient,
    path: str,
    payload: dict[str, Any],
    limiter: ConcurrencyLimiter,
) -> dict[str, Any]:
    """POST a JSON body to Ollama and return the decoded response.

    Shared by every non-streaming endpoint: they differ only in the path they
    call. The slot is held for the whole upstream call and always released,
    including when Ollama answers with an error status.
    """
    async with limiter.slot():
        try:
            response = await client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise APIError(502, "Upstream unavailable") from exc

    if response.status_code >= 400:
        raise await _error_from_upstream(response)
    return response.json()


async def complete_chat(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    limiter: ConcurrencyLimiter,
) -> dict[str, Any]:
    return await _complete(client, CHAT_PATH, payload, limiter)


async def complete_embedding(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    limiter: ConcurrencyLimiter,
) -> dict[str, Any]:
    return await _complete(client, EMBEDDINGS_PATH, payload, limiter)


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
