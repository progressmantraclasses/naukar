"""Debug Bing fallback parsing for the smoke query."""
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


async def probe(q):
    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as c:
        r = await c.get("https://www.bing.com/search", params={"q": q, "count": "10"})
        print("QUERY:", q)
        print("  status", r.status_code, "len", len(r.text))
        print("  b_algo blocks:", r.text.count('class="b_algo"'))
        blocks = re.split(r'<li class="b_algo"', r.text)[1:]
        n = 0
        for block in blocks[:3]:
            hrefs = re.findall(r'href="([^"]+)"', block)
            print("   block hrefs:")
            for hh in hrefs[:8]:
                print("     ", hh[:140])
        for block in blocks[:8]:
            m = re.search(r'href="(https?://[^"]+)"', block)
            if not m:
                continue
            url = m.group(1)
            if "bing.com" in url or "microsoft.com" in url:
                continue
            n += 1
            print("   ->", url[:110])
        print("  parsed results:", n)


async def main():
    await probe("download NCERT class 10 mathematics textbook pdf")
    await probe("ncert class 10 mathematics textbook pdf")


asyncio.run(main())
