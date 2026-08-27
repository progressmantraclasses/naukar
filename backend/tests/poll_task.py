"""Poll an existing task until terminal state, with retry on transient errors."""
import asyncio
import sys

import httpx

from app.auth.service import create_access_token

BASE = "http://localhost:8001"


async def main():
    task_id = sys.argv[1]
    token = create_access_token({
        "sub": "dev-user",
        "workspace_id": "default",
        "email": "dev@local",
        "role": "user",
    })
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        for _ in range(120):
            try:
                r = await client.get(f"{BASE}/api/tasks/{task_id}", headers=headers)
                data = r.json()
            except Exception as exc:
                print("poll error:", type(exc).__name__, flush=True)
                await asyncio.sleep(5)
                continue
            status = data.get("status")
            print("status:", status, flush=True)
            if status in ("completed", "failed", "cancelled"):
                result = data.get("result") or ""
                print("=== RESULT ===")
                print(result[:3000])
                break
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
