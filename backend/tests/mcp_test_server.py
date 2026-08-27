"""Tiny MCP server used ONLY for testing the Naukar MCP client integration."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TestServer")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the given text back."""
    return f"echo: {text}"


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
