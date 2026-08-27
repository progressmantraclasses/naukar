"""Mark zombie 'executing' tasks as failed so they stop blocking the UI."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update
from app.core.database import engine
from app.db import models as db_models


async def main():
    async with engine.begin() as conn:
        r = await conn.execute(
            update(db_models.Task)
            .where(db_models.Task.status == "executing")
            .values(status="failed", error_message="stale: server restarted mid-run")
        )
        print("marked failed:", r.rowcount)


asyncio.run(main())
