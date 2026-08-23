"""
SmartWebSearcher — two-tier intelligent web search to reduce API costs.

Tier 1 (FREE): DuckDuckGo HTML scraping + direct URL content extraction.
               Checks at least 5 websites. No API key required.
Tier 2 (PAID): Tavily API — used only when free tier finds insufficient data.

Usage:
    result = await smart_web_searcher.search("query about X")
    if result.is_sufficient:
        # use result.text directly — no LLM call needed
    else:
        # call LLM with result.text as context
"""
import asyncio
import re
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

import httpx
import structlog

from app.core.config import settings
from app.security.validators import URLValidator, URLValidationError, PromptSanitizer

log = structlog.get_logger()

# HTML tag stripper regex
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s{3,}")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript|header|footer|nav|aside)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

# DuckDuckGo HTML endpoint (no API key, rate limit lenient)
_DDG_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

# Minimum useful text from web search to skip the LLM
_MIN_USEFUL_CHARS = 800
_MIN_SOURCES = 3


@dataclass
class WebSearchResult:
    query: str
    text: str                          # aggregated extracted text
    sources: List[dict] = field(default_factory=list)   # [{url, title, snippet}]
    sites_checked: int = 0
    sites_used: int = 0
    tier_used: str = "none"            # "ddg" | "tavily" | "none"
    latency_ms: int = 0
    estimated_tokens_saved: int = 0

    @property
    def is_sufficient(self) -> bool:
        return (
            len(self.text.strip()) >= _MIN_USEFUL_CHARS
            and self.sites_used >= _MIN_SOURCES
        )

    def to_context_block(self) -> str:
        """Format for injection into an LLM prompt."""
        if not self.text:
            return ""
        src_lines = "\n".join(
            f"  [{i+1}] {s.get('title', '')} — {s.get('url', '')}"
            for i, s in enumerate(self.sources[:8])
        )
        return (
            f"## Web Research Context\n"
            f"The following information was gathered from {self.sites_used} websites "
            f"(checked {self.sites_checked} total):\n\n"
            f"{self.text[:4000]}\n\n"
            f"Sources:\n{src_lines}\n"
        )


def _strip_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    html = _TAG_RE.sub(" ", html)
    html = _WHITESPACE_RE.sub(" ", html)
    return html.strip()


def _estimate_tokens(text: str) -> int:
    """Very rough token estimate: ~4 chars per token."""
    return len(text) // 4


async def _fetch_url_text(client: httpx.AsyncClient, url: str, timeout: int = 8) -> str:
    """Fetch a URL and return clean text content. Validates URL for SSRF before fetching."""
    try:
        # SSRF protection: validate URL before any network request
        URLValidator.validate(url, resolve_dns=False)  # fast check first
    except URLValidationError as exc:
        log.debug("url_blocked_ssrf", url=url[:80], reason=str(exc))
        return ""
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        if resp.status_code != 200:
            return ""
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct and "text/plain" not in ct:
            return ""
        # Sanitize content against prompt injection before returning
        raw = _strip_html(resp.text)[:6000]
        return raw
    except Exception as exc:
        log.debug("web_fetch_failed", url=url, error=str(exc))
        return ""


async def _ddg_search(query: str, max_results: int = 8) -> List[dict]:
    """
    DuckDuckGo HTML scraping — returns list of {url, title, snippet}.
    Completely free, no API key needed.
    """
    results = []
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
            resp = await client.post(
                _DDG_URL,
                data={"q": query, "b": "", "kl": "us-en"},
            )
            html = resp.text

            # Parse result links from DDG HTML
            # DDG wraps results in <a class="result__a" href="...">
            link_pattern = re.compile(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE,
            )
            snippet_pattern = re.compile(
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE,
            )
            links = link_pattern.findall(html)
            snippets = snippet_pattern.findall(html)

            for i, (url, title) in enumerate(links[:max_results]):
                # DDG sometimes gives relative or redirect URLs
                if url.startswith("/"):
                    continue
                snippet = _strip_html(snippets[i]) if i < len(snippets) else ""
                results.append({
                    "url": url,
                    "title": _strip_html(title)[:120],
                    "snippet": snippet[:300],
                })
    except Exception as exc:
        log.warning("ddg_search_failed", query=query[:50], error=str(exc))
    return results


class SmartWebSearcher:
    """
    Two-tier web searcher.
    Always tries free DuckDuckGo + content scraping first (>=5 sites).
    Falls back to Tavily only if insufficient content found.
    Caches results in Redis.
    """

    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        """Lazy Redis client."""
        if self._redis is None:
            try:
                from app.core.redis_store import redis_store
                self._redis = await redis_store.client()
            except Exception:
                self._redis = None
        return self._redis

    async def _get_cached(self, key: str) -> Optional[dict]:
        try:
            r = await self._get_redis()
            if r:
                val = await r.get(key)
                if val:
                    return json.loads(val)
        except Exception:
            pass
        return None

    async def _set_cached(self, key: str, data: dict):
        try:
            r = await self._get_redis()
            if r:
                await r.setex(key, self.CACHE_TTL, json.dumps(data))
        except Exception:
            pass

    def _cache_key(self, query: str) -> str:
        h = hashlib.md5(query.strip().lower().encode()).hexdigest()
        return f"naukar:websearch:v2:{h}"

    async def search(
        self,
        query: str,
        min_sites: int = 5,
        task_id: Optional[str] = None,
    ) -> WebSearchResult:
        """
        Search the web for `query`. Checks at least `min_sites` pages.
        Returns WebSearchResult with aggregated text and metadata.
        """
        start = time.monotonic()
        cache_key = self._cache_key(query)

        # Check cache first
        cached = await self._get_cached(cache_key)
        if cached:
            log.info("web_search_cache_hit", query=query[:50])
            r = WebSearchResult(**cached)
            r.latency_ms = int((time.monotonic() - start) * 1000)
            return r

        # ── Tier 1: DuckDuckGo + URL scraping ─────────────────────────────
        ddg_results = await _ddg_search(query, max_results=max(min_sites + 3, 8))
        log.info("ddg_results_found", count=len(ddg_results), query=query[:50])

        extracted_texts: List[str] = []
        used_sources: List[dict] = []

        if ddg_results:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=12) as client:
                tasks = [
                    _fetch_url_text(client, r["url"])
                    for r in ddg_results[:min_sites + 2]
                ]
                fetched = await asyncio.gather(*tasks, return_exceptions=True)

            for i, text in enumerate(fetched):
                if isinstance(text, Exception) or not text:
                    continue
                if len(text.strip()) > 200:
                    extracted_texts.append(text[:2000])
                    used_sources.append(ddg_results[i])

        sites_checked = len(ddg_results)
        sites_used = len(used_sources)
        aggregated = "\n\n---\n\n".join(extracted_texts)

        result = WebSearchResult(
            query=query,
            text=aggregated,
            sources=used_sources,
            sites_checked=sites_checked,
            sites_used=sites_used,
            tier_used="ddg",
            latency_ms=int((time.monotonic() - start) * 1000),
            estimated_tokens_saved=_estimate_tokens(aggregated) if aggregated else 0,
        )

        # ── Tier 2: Tavily fallback if DDG insufficient ────────────────────
        if not result.is_sufficient and settings.TAVILY_API_KEY:
            log.info(
                "web_search_tavily_fallback",
                reason=f"DDG gave {sites_used} sites/{len(aggregated)} chars",
                query=query[:50],
            )
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.TAVILY_API_KEY,
                            "query": query,
                            "max_results": min(min_sites + 2, settings.SEARCH_MAX_RESULTS),
                            "include_answer": True,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                tavily_results = data.get("results", [])
                tavily_answer = data.get("answer", "")
                tavily_text_parts = [tavily_answer] if tavily_answer else []

                for tr in tavily_results:
                    content = tr.get("content", "")
                    if content:
                        tavily_text_parts.append(content[:1500])
                        used_sources.append({
                            "url": tr.get("url", ""),
                            "title": tr.get("title", ""),
                            "snippet": content[:200],
                        })

                full_tavily = "\n\n".join(tavily_text_parts)
                # Merge both tiers
                combined = (aggregated + "\n\n" + full_tavily).strip()
                result = WebSearchResult(
                    query=query,
                    text=combined,
                    sources=used_sources,
                    sites_checked=sites_checked + len(tavily_results),
                    sites_used=sites_used + len(tavily_results),
                    tier_used="tavily",
                    latency_ms=int((time.monotonic() - start) * 1000),
                    estimated_tokens_saved=_estimate_tokens(combined),
                )
            except Exception as exc:
                log.warning("tavily_fallback_failed", error=str(exc))

        log.info(
            "web_search_complete",
            query=query[:50],
            tier=result.tier_used,
            sites_checked=result.sites_checked,
            sites_used=result.sites_used,
            chars=len(result.text),
            sufficient=result.is_sufficient,
            latency_ms=result.latency_ms,
        )

        # Cache result
        await self._set_cached(cache_key, {
            "query": result.query,
            "text": result.text,
            "sources": result.sources,
            "sites_checked": result.sites_checked,
            "sites_used": result.sites_used,
            "tier_used": result.tier_used,
            "latency_ms": result.latency_ms,
            "estimated_tokens_saved": result.estimated_tokens_saved,
        })

        return result

    async def emit_event(self, task_id: str, result: WebSearchResult, step_label: str = ""):
        """Emit a WEB_SEARCH_RESULT event for the frontend."""
        try:
            from app.core.events import event_bus, Event, EventType
            await event_bus.publish(Event(
                event_type=EventType.WEB_SEARCH_RESULT,
                task_id=task_id,
                payload={
                    "query": result.query[:100],
                    "step_label": step_label,
                    "tier_used": result.tier_used,
                    "sites_checked": result.sites_checked,
                    "sites_used": result.sites_used,
                    "is_sufficient": result.is_sufficient,
                    "estimated_tokens_saved": result.estimated_tokens_saved,
                    "latency_ms": result.latency_ms,
                    "sources": result.sources[:6],
                },
            ))
        except Exception as exc:
            log.warning("web_search_event_emit_failed", error=str(exc))


# Global singleton
smart_web_searcher = SmartWebSearcher()
