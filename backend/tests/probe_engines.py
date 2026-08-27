"""Probe alternative search engines (DDG html endpoint currently returns 202 challenge)."""
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
        # Bing
        try:
            r = await c.get("https://www.bing.com/search", params={"q": Q, "count": "10"})
            print("BING status", r.status_code, "len", len(r.text))
            links = re.findall(r'<h2><a href="(https?://[^"]+)"', r.text)
            print("BING h2 links:", len(links))
            for u in links[:6]:
                print("  ", u[:110])
        except Exception as e:
            print("BING FAIL", type(e).__name__, str(e)[:120])

        # Mojeek
        try:
            r2 = await c.get("https://www.mojeek.com/search", params={"q": Q})
            print("MOJEEK status", r2.status_code, "len", len(r2.text))
            mlinks = re.findall(r'<a class="title" href="(https?://[^"]+)"', r2.text)
            print("MOJEEK links:", len(mlinks))
            for u in mlinks[:6]:
                print("  ", u[:110])
        except Exception as e:
            print("MOJEEK FAIL", type(e).__name__, str(e)[:120])

        # Startpage? (often blocked) skip. Try search.marcia? Use Brave? Try Ecosia (bing-backed)
        try:
            r3 = await c.get("https://www.ecosia.org/search", params={"q": Q})
            print("ECOSIA status", r3.status_code, "len", len(r3.text))
            elinks = re.findall(r'https?://ncert[^"<\s]+', r3.text)
            print("ECOSIA ncert-ish urls:", len(set(elinks)))
            for u in list(set(elinks))[:6]:
                print("  ", u[:110])
        except Exception as e:
            print("ECOSIA FAIL", type(e).__name__, str(e)[:120])


asyncio.run(main())
