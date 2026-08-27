"""Smoke test: web search finds NCERT pdf links and the downloader saves one."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.web_searcher import smart_web_searcher
from app.tools import downloader


async def main():
    r = await smart_web_searcher.search(
        "ncert textbook pdf",
        min_sites=5,
    )
    print("SITES checked/used:", r.sites_checked, r.sites_used, "| chars:", len(r.text))
    urls = downloader.find_file_urls(r.sources, r.text)
    print("FILE URLS FOUND:", len(urls))
    for u in urls[:5]:
        print("  -", u[:110])
    assert urls, "no file urls found"
    best = downloader.rank_urls(urls, ["ncert", "mathematics"])[0]
    print("BEST:", best[:120])
    info = await downloader.download_file(best)
    print("DOWNLOADED:", info["path"], info["bytes"], "bytes")
    assert info["bytes"] > 1000
    print("ALL_DOWNLOAD_CHECKS_PASSED")


asyncio.run(main())
