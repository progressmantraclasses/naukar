"""
Bounded file downloader — saves a file found via web search into the workspace.

When a task asks to "download" something, the executor picks the best direct
file URL from the search results and saves it locally, so the user receives
the actual file path instead of just a link.
"""
import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse, urljoin

import httpx
import structlog

from app.core.config import settings
from app.security.validators import URLValidator

log = structlog.get_logger()

MAX_DOWNLOAD_BYTES = 40_000_000  # 40 MB hard cap
_TIMEOUT = 90
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_FILE_EXT_RE = re.compile(r"\.(?:pdf|epub|zip|docx?|xlsx?|csv)(?:[?#]|$)", re.IGNORECASE)
_FILE_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+?\.(?:pdf|epub|zip|docx?|xlsx?|csv)(?:[?#][^\s\"'<>]*)?",
    re.IGNORECASE,
)


def has_file_ext(url: str) -> bool:
    return bool(_FILE_EXT_RE.search(url or ""))


def find_file_urls(sources: List[dict], text: str) -> List[str]:
    """Collect direct file URLs from search sources + scraped text."""
    seen = set()
    out: List[str] = []

    def add(u: str):
        u = (u or "").strip().rstrip(")")
        if u.startswith("http") and u not in seen:
            seen.add(u)
            out.append(u)

    for s in sources or []:
        if has_file_ext(s.get("url", "")):
            add(s.get("url", ""))
    for m in _FILE_URL_RE.finditer(text or ""):
        add(m.group(0))
    return out


# Site-chrome PDFs that match any "pdf" search but are never the requested
# document (browser help pages, policies, etc.).
_SPAM_TOKENS = ("cache", "chrome", "browser", "howto", "how-to", "policy")


def rank_urls(urls: List[str], hint_tokens: List[str]) -> List[str]:
    """Prefer URLs whose host/path mention task hints (e.g. 'ncert')."""
    def score(u: str) -> int:
        low = u.lower()
        s = sum(1 for t in hint_tokens if t and t in low)
        if any(tok in low for tok in _SPAM_TOKENS):
            s -= 3
        return s
    return sorted(urls, key=score, reverse=True)


_HREF_RE = re.compile(r'(?:href|src)="([^"]+)"', re.IGNORECASE)


async def discover_file_urls(sources: List[dict], max_pages: int = 3) -> List[str]:
    """
    Crawl top landing-page sources and harvest direct file links from their
    HTML. Search results often point at index pages (e.g. ncert.nic.in/textbook.php)
    that themselves contain the downloadable PDF hrefs.
    """
    found: List[str] = []
    pages = [s["url"] for s in (sources or [])
             if s.get("url", "").startswith("http") and not has_file_ext(s["url"])]
    async with httpx.AsyncClient(
        timeout=12, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    ) as client:
        for page in pages[:max_pages]:
            try:
                resp = await client.get(page)
                if resp.status_code != 200:
                    continue
                for href in _HREF_RE.findall(resp.text):
                    if not _FILE_EXT_RE.search(href):
                        continue
                    absolute = urljoin(page, href.replace("&amp;", "&"))
                    if absolute.startswith("http") and absolute not in found:
                        found.append(absolute)
            except Exception as exc:
                log.debug("landing_crawl_failed", page=page[:80], error=str(exc)[:120])
    return found


async def download_file(url: str, subdir: str = "downloads") -> dict:
    """Stream `url` into <workspace>/downloads; bounded and SSRF-checked."""
    URLValidator.validate(url, resolve_dns=False)
    root = Path(settings.TOOL_WORKSPACE_ROOT).resolve()
    dest_dir = root / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = Path(urlparse(url).path).name or "download"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
    if "." not in name:
        name += ".bin"
    dest = dest_dir / name

    written = 0
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                async for chunk in resp.aiter_bytes(65_536):
                    written += len(chunk)
                    if written > MAX_DOWNLOAD_BYTES:
                        fh.close()
                        dest.unlink(missing_ok=True)
                        raise ValueError("Download exceeds the 40 MB limit")
                    fh.write(chunk)

    log.info("file_downloaded", url=url[:100], path=str(dest), bytes=written)
    return {"path": str(dest), "bytes": written, "url": url}
