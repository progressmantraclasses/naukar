"""Namespaced Redis primitives for cache, state, locks, and rate limits."""
import hashlib
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import redis.asyncio as aioredis

from app.core.config import settings


class RedisStore:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    @staticmethod
    def digest(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def get_json(self, key: str) -> Optional[dict]:
        value = await (await self.client()).get(key)
        return json.loads(value) if value else None

    async def set_json(self, key: str, value: Any, ttl: int):
        await (await self.client()).setex(key, ttl, json.dumps(value, ensure_ascii=True, default=str))

    async def increment_window(self, key: str, window_seconds: int, limit: int) -> tuple[bool, int]:
        redis = await self.client()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        return count <= limit, max(limit - count, 0)

    @asynccontextmanager
    async def lock(self, name: str, ttl: int = 60) -> AsyncIterator[bool]:
        lock = (await self.client()).lock(f"naukar:lock:{name}", timeout=ttl, blocking_timeout=5)
        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                await lock.release()

    async def close(self):
        if self._redis:
            await self._redis.aclose()
            self._redis = None


redis_store = RedisStore()
