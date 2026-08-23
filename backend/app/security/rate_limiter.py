"""
Rate Limiter — sliding window per user/IP using Redis (in-memory fallback).
"""
import time
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, Request

from app.core.security import get_identity, Identity

log = structlog.get_logger()

# In-memory fallback store when Redis is unavailable
_mem_store: dict = {}


async def _redis_client():
    try:
        from app.core.redis_store import redis_store
        r = await redis_store.client()
        return r
    except Exception:
        return None


class RateLimiter:
    """Sliding-window rate limiter as a FastAPI dependency."""

    def __init__(self, limit: int, window_seconds: int = 60, key_prefix: str = "rl"):
        self.limit = limit
        self.window = window_seconds
        self.prefix = key_prefix

    async def __call__(self, request: Request, identity: Identity = Depends(get_identity)):
        key = f"naukar:{self.prefix}:{identity.user_id}"
        count = await self._increment(key)
        if count > self.limit:
            log.warning("rate_limit_exceeded", key=key, count=count, limit=self.limit)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.limit} requests per {self.window}s.",
                headers={"Retry-After": str(self.window)},
            )

    async def _increment(self, key: str) -> int:
        r = await _redis_client()
        if r:
            try:
                pipe = r.pipeline()
                await pipe.incr(key)
                await pipe.expire(key, self.window)
                results = await pipe.execute()
                return results[0]
            except Exception:
                pass
        # In-memory fallback
        now = time.time()
        _mem_store.setdefault(key, [])
        _mem_store[key] = [t for t in _mem_store[key] if now - t < self.window]
        _mem_store[key].append(now)
        return len(_mem_store[key])


class IPRateLimiter:
    """IP-based rate limiter (for auth endpoints, no token required)."""

    def __init__(self, limit: int, window_seconds: int = 60, key_prefix: str = "ip_rl"):
        self.limit = limit
        self.window = window_seconds
        self.prefix = key_prefix

    async def __call__(self, request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"naukar:{self.prefix}:{ip}"
        # In-memory only (auth endpoints don't use Redis identity)
        now = time.time()
        _mem_store.setdefault(key, [])
        _mem_store[key] = [t for t in _mem_store[key] if now - t < self.window]
        _mem_store[key].append(now)
        count = len(_mem_store[key])
        if count > self.limit:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Max {self.limit} per {self.window}s.",
                headers={"Retry-After": str(self.window)},
            )


# Pre-built dependency instances
task_rate_limit = RateLimiter(limit=10, window_seconds=60, key_prefix="tasks")
api_rate_limit = RateLimiter(limit=120, window_seconds=60, key_prefix="api")
