"""Live test: connect MCPManager to a real stdio MCP server and call tools."""
import asyncio
import sys
from pathlib import Path

from app.mcp.manager import mcp_manager
from app.mcp.models import MCPServerConfig

PYTHON = sys.executable
SERVER = str(Path(__file__).resolve().parent / "mcp_test_server.py")


async def main():
    cfg = MCPServerConfig(
        id="test-server",
        name="Test Server",
        transport="stdio",
        command=PYTHON,
        args=[SERVER],
    )

    status = await mcp_manager.connect(cfg)
    print("STATUS:", status.status, "| TOOLS:", status.tools, "| ERROR:", status.error)
    assert status.status == "connected", f"connect failed: {status.error}"
    assert "echo" in status.tools and "add" in status.tools

    # Tool execution
    out1 = await mcp_manager.call_tool("test-server", "echo", {"text": "hello naukar"})
    print("ECHO OUT:", out1)
    assert out1 == "echo: hello naukar"

    out2 = await mcp_manager.call_tool("test-server", "add", {"a": 20, "b": 22})
    print("ADD OUT:", out2)
    assert out2.strip() == "42"

    # Relevance matching — 'analytics' keyword should fall back sensibly
    rel = mcp_manager.relevant_tools("analyze our meta ads campaign audience")
    print("RELEVANT TOOLS (small catalog fallback):", [t.name for t in rel])
    assert len(rel) > 0  # catalog <= 8 → full catalog handed over

    # Executor schema building
    from app.employees.executor import EmployeeExecutor
    schemas = EmployeeExecutor._build_tool_schemas(mcp_manager.all_tools())
    print("SCHEMAS:", [s["function"]["name"] for s in schemas])
    assert schemas and schemas[0]["type"] == "function"

    await mcp_manager.disconnect("test-server")
    print("ALL_MCP_CHECKS_PASSED")


if __name__ == "__main__":
    asyncio.run(main())
