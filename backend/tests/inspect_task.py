"""Inspect ai_usage + tool_executions for a task id."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine as async_engine

TID = sys.argv[1] if len(sys.argv) > 1 else "4f3dd695-bce6-4741-8835-d38fda16a600"


async def main():
    async with async_engine.connect() as conn:
        r = await conn.execute(
            text(
                "SELECT model, search_used, cache_hit, semantic_cache_hit, "
                "input_tokens, output_tokens, created_at "
                "FROM ai_usage WHERE task_id=:t ORDER BY created_at"
            ),
            {"t": TID},
        )
        for row in r:
            print("USAGE", row)
        r2 = await conn.execute(
            text("SELECT * FROM tool_executions WHERE task_id=:t ORDER BY created_at"),
            {"t": TID},
        )
        rows = list(r2)
        print("TOOL_EXECUTIONS:", len(rows))
        for row in rows:
            print("TOOL", dict(row._mapping))


asyncio.run(main())
