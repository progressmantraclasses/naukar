"""Provider-independent web search with Redis result caching."""
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.core.redis_store import redis_store


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        ...


class TavilySearchProvider(SearchProvider):
    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        key = f"naukar:search:{redis_store.digest({'query': query.strip().lower(), 'top_k': top_k})}"
        cached = await redis_store.get_json(key)
        if cached is not None:
            return cached.get("results", [])
        if not settings.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT_SECONDS) as client:
            response = await client.post("https://api.tavily.com/search", json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": min(top_k, settings.SEARCH_MAX_RESULTS),
                "include_answer": False,
            })
            response.raise_for_status()
            results = response.json().get("results", [])
        await redis_store.set_json(key, {"results": results}, settings.SEARCH_CACHE_TTL_SECONDS)
        return results


search_provider = TavilySearchProvider()
