import asyncio

import pytest

from app.concurrency import ConcurrencyLimiter
from app.errors import APIError


def test_rejects_with_429_when_queue_wait_expires():
    async def scenario():
        limiter = ConcurrencyLimiter(limit=1, queue_timeout=0.05)
        await limiter.acquire()
        with pytest.raises(APIError) as exc:
            await limiter.acquire()
        assert exc.value.status_code == 429
        assert exc.value.code == "rate_limit_exceeded"
        limiter.release()

    asyncio.run(scenario())


def test_slot_context_manager_releases_on_exception():
    async def scenario():
        limiter = ConcurrencyLimiter(limit=1, queue_timeout=0.05)
        with pytest.raises(RuntimeError):
            async with limiter.slot():
                raise RuntimeError("fallo")
        async with limiter.slot():
            pass

    asyncio.run(scenario())
