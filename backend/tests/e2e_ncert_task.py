"""End-to-end: submit the NCERT download task and wait for completion."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.auth.service import create_access_token

BASE = "http://localhost:8001"


async def main():
    token = create_access_token(
        {"sub": "dev-user", "workspace_id": "default", "email": "dev@local", "role": "user"}
    )
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE}/api/tasks",
            json={"user_input": "pls find a ncert book and download it for me"},
            headers=headers,
        )
        r.raise_for_status()
        task_id = r.json()["id"]
        print("TASK_ID:", task_id)

        deadline = time.time() + 900
        status = ""
        data = {}
        while time.time() < deadline:
            await asyncio.sleep(5)
            try:
                g = await client.get(f"{BASE}/api/tasks/{task_id}", headers=headers)
                data = g.json()
            except Exception as exc:
                print("poll error:", type(exc).__name__, flush=True)
                continue
            status = data.get("status", "")
            print("status:", status, flush=True)
            if status in ("completed", "failed", "error"):
                break
        print("FINAL STATUS:", status)
        result = data.get("result") or data.get("final_result") or ""
        print("RESULT SNIPPET:")
        print(str(result)[:1500])


asyncio.run(main())
