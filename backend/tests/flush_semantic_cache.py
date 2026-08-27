"""One-off: wipe stale semantic cache entries that replay old answers."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def main():
    async with engine.begin() as conn:
        r = await conn.execute(text("DELETE FROM semantic_cache"))
        print("DELETED rows:", r.rowcount)


asyncio.run(main())
