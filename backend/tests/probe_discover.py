"""Probe: search 'ncert pdf' and harvest direct file URLs from landing pages."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.web_searcher import smart_web_searcher
from app.tools.downloader import find_file_urls, discover_file_urls, rank_urls


async def main():
    result = await smart_web_searcher.search("ncert class 10 maths textbook pdf", min_sites=5)
    print("sites:", result.sites_checked, "used:", result.sites_used, "tier:", result.tier_used)
    for s in result.sources[:8]:
        print(" -", s["url"][:100])
    urls = find_file_urls(result.sources, result.text)
    print("direct file urls:", len(urls))
    if not urls:
        urls = await discover_file_urls(result.sources)
        print("discovered from landing pages:", len(urls))
        for u in urls[:8]:
            print(" *", u[:110])
    hints = ["ncert", "maths", "class"]
    ranked = rank_urls(urls, hints)
    print("top ranked:", ranked[:3] if ranked else "NONE")


asyncio.run(main())
