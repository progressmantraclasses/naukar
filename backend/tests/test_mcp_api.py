"""API smoke test: /api/mcp endpoints against a live stdio MCP server."""
import asyncio
import tempfile

from fastapi.testclient import TestClient

import main
from app.mcp.manager import mcp_manager
import app.mcp.store as store_mod
from app.mcp.store import load_configs, save_configs
import sys
from pathlib import Path

PYTHON = sys.executable
SERVER = str(Path(__file__).resolve().parent / "mcp_test_server.py")

# Sandbox the config file so the test never clobbers the user's real
# backend/data/mcp_servers.json store.
store_mod._STORE_PATH = Path(tempfile.mkdtemp(prefix="mcp-test-store-")) / "mcp_servers.json"

client = TestClient(main.app)


async def cleanup():
    await mcp_manager.shutdown()
    save_configs([])


async def main_test():
    # start clean
    save_configs([])
    await mcp_manager.shutdown()

    r = client.get("/api/mcp/presets")
    assert r.status_code == 200 and len(r.json()["presets"]) >= 5, "presets"
    print("PRESETS OK:", [p["name"] for p in r.json()["presets"]])

    r = client.get("/api/mcp/servers")
    assert r.status_code == 200 and r.json() == [], "empty list"

    r = client.post("/api/mcp/servers", json={
        "name": "Test Server",
        "transport": "stdio",
        "command": PYTHON,
        "args": [SERVER],
        "env": {"SECRET_KEY": "hidden-value"},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    print("ADDED:", data["name"], "| status:", data["status"], "| tools:", data["tools"])
    assert data["status"] == "connected" and "echo" in data["tools"]
    assert data["env"] == {"SECRET_KEY": "••••"}, "env secrets must be masked"
    server_id = data["id"]

    r = client.get("/api/mcp/tools")
    names = [t["name"] for t in r.json()["tools"]]
    print("TOOLS ENDPOINT:", names)
    assert "echo" in names and "add" in names

    r = client.delete(f"/api/mcp/servers/{server_id}")
    assert r.status_code == 200, "delete"
    assert load_configs() == [], "config removed"

    # validation check
    r = client.post("/api/mcp/servers", json={"name": "bad", "transport": "stdio"})
    assert r.status_code == 400, "missing command rejected"

    await cleanup()
    print("ALL_MCP_API_CHECKS_PASSED")


if __name__ == "__main__":
    asyncio.run(main_test())
