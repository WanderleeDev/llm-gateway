import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.errors import APIError


class ConcurrencyLimiter:
    """Limita cuántas generaciones van a Ollama a la vez.

    Las peticiones extra esperan hasta queue_timeout segundos y luego reciben 429.
    """

    def __init__(self, limit: int, queue_timeout: float) -> None:
        self._semaphore = asyncio.Semaphore(limit)
        self._queue_timeout = queue_timeout

    async def acquire(self) -> None:
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._queue_timeout)
        except TimeoutError as exc:
            raise APIError(
                429, "Server is busy, please retry.", "rate_limit_error", "rate_limit_exceeded"
            ) from exc

    def release(self) -> None:
        self._semaphore.release()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self.acquire()
        try:
            yield
        finally:
            self.release()
