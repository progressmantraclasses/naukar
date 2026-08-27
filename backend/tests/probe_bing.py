"""Inspect Bing search HTML structure to build a reliable parser."""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
Q = "ncert class 10 mathematics textbook pdf"


async def main():
    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as c:
        r = await c.get("https://www.bing.com/search", params={"q": Q, "count": "10"})
        html = r.text
        print("status", r.status_code, "len", len(html))

        # candidate patterns
        patterns = {
            "h2_a": r'<h2><a[^>]+href="(https?://[^"]+)"',
            "b_algo": r'class="b_algo"',
            "cite": r'<cite[^>]*>([^<]+)</cite>',
            "any_ncert": r'https?://[^"<\s]*ncert[^"<\s]*',
        }
        for name, pat in patterns.items():
            m = re.findall(pat, html)
            print(name, "->", len(m))
            for u in m[:8]:
                print("   ", u[:120])

        # Show snippet around first b_algo if present
        i = html.find("b_algo")
        if i > 0:
            print("--- b_algo snippet ---")
            print(html[i - 100 : i + 700])


asyncio.run(main())
