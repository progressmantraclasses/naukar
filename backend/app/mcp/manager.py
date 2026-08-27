"""
MCPManager — connects to user-configured MCP servers, discovers their tools,
and lets employees call those tools. Connections stay open for the process
lifetime via AsyncExitStack so repeated tool calls don't pay reconnect cost.
"""
import asyncio
import os
import sys
import tempfile
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp.models import MCP_TOOL_KEYWORDS, MCPServerConfig, MCPServerStatus, MCPToolInfo

log = structlog.get_logger()


@dataclass
class _Connection:
    config: MCPServerConfig
    stack: AsyncExitStack
    session: Optional[ClientSession] = None
    tools: List[MCPToolInfo] = field(default_factory=list)
    status: str = "disconnected"
    error: str = ""
    # anyio contexts (stdio_client etc.) must be entered AND exited in the
    # same task, so each connection owns a dedicated task that opens the
    # stack and waits until it is asked to close. The owner task runs on
    # the manager's private I/O loop: uvicorn --reload on Windows forces a
    # SelectorEventLoop onto the app, which cannot spawn subprocesses
    # (the stdio transport needs a Proactor loop).
    owner_task: Optional[asyncio.Task] = None
    owner_future: Optional[Any] = None
    close_event: Optional[asyncio.Event] = None
    close_requested: bool = False
    # stderr of the spawned server is captured to a temp file so connect
    # failures can show the server's own reason (missing API keys etc.)
    errlog_file: Optional[Any] = None
    errlog_path: str = ""


class MCPManager:
    """Singleton managing all connected MCP servers."""

    def __init__(self):
        self._conns: Dict[str, _Connection] = {}
        self._lock = asyncio.Lock()
        self._io_loop: Optional[asyncio.AbstractEventLoop] = None
        self._io_thread: Optional[threading.Thread] = None

    def _ensure_io_loop(self) -> asyncio.AbstractEventLoop:
        """Private event loop on a daemon thread for MCP session I/O.

        A fresh loop from the default policy is a Proactor loop on Windows,
        which supports subprocess spawning regardless of what policy the
        host server (uvicorn --reload) forced onto the app loop.
        """
        if self._io_loop is not None and self._io_loop.is_running():
            return self._io_loop
        ready = threading.Event()

        def _runner() -> None:
            # Build the loop explicitly: uvicorn --reload sets the process-
            # wide policy to Selector on Windows, and new_event_loop() would
            # inherit it. Selector loops cannot spawn subprocesses, so the
            # stdio transport needs a Proactor loop here.
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._io_loop = loop
            ready.set()
            loop.run_forever()

        self._io_thread = threading.Thread(
            target=_runner, name="mcp-io", daemon=True
        )
        self._io_thread.start()
        ready.wait(5)
        return self._io_loop

    async def _run_on_io(self, coro):
        """Run a coroutine on the private I/O loop and await it here."""
        loop = self._ensure_io_loop()
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(coro, loop)
        )

    # ── Connection lifecycle ──────────────────────────────────────────────
    async def connect(self, config: MCPServerConfig) -> MCPServerStatus:
        """Connect (or reconnect) one server and discover its tools."""
        async with self._lock:
            await self._disconnect_locked(config.id)
            conn = _Connection(
                config=config,
                stack=AsyncExitStack(),
                status="connecting",
            )
            self._conns[config.id] = conn
            # anyio contexts must be entered AND exited in the same task,
            # so a dedicated owner task on the I/O loop holds the stack.
            loop = self._ensure_io_loop()
            conn.owner_future = asyncio.run_coroutine_threadsafe(
                self._own_connection(conn), loop
            )

        # Wait until the owner task finished opening (or failed)
        while conn.status == "connecting":
            if conn.owner_future.done():
                break
            await asyncio.sleep(0.05)
        return self.status_for(config.id)

    async def _own_connection(self, conn: _Connection):
        """Owns the connection's context stack for its whole lifetime."""
        config = conn.config
        conn.owner_task = asyncio.current_task()
        conn.close_event = asyncio.Event()
        if conn.close_requested:
            conn.close_event.set()
        try:
            if config.transport == "stdio":
                env = {**os.environ, **config.env}
                params = StdioServerParameters(
                    command=config.command, args=config.args, env=env
                )
                fd, conn.errlog_path = tempfile.mkstemp(
                    prefix="mcp-stderr-", suffix=".log"
                )
                conn.errlog_file = os.fdopen(fd, "w+b")
                read, write = await conn.stack.enter_async_context(
                    stdio_client(params, errlog=conn.errlog_file)
                )
            elif config.transport in ("sse", "http"):
                if config.transport == "sse":
                    from mcp.client.sse import sse_client as remote_client
                else:
                    from mcp.client.streamable_http import streamablehttp_client as remote_client
                ctx = remote_client(config.url)
                streams = await conn.stack.enter_async_context(ctx)
                read, write = streams[0], streams[1]
            else:
                raise ValueError(f"Unknown transport: {config.transport}")

            session = await conn.stack.enter_async_context(ClientSession(read, write))
            # Generous timeouts: first run of an npx-based server downloads
            # the npm package before it can answer initialize/list_tools.
            await asyncio.wait_for(session.initialize(), timeout=180)

            listing = await asyncio.wait_for(session.list_tools(), timeout=60)
            conn.session = session
            conn.tools = [
                MCPToolInfo(
                    server_id=config.id,
                    server_name=config.name,
                    name=t.name,
                    description=(t.description or "")[:400],
                    input_schema=t.inputSchema or {},
                )
                for t in listing.tools
            ]
            conn.status = "connected"
            conn.error = ""
            log.info(
                "mcp_server_connected",
                server=config.name,
                transport=config.transport,
                tools=len(conn.tools),
            )
        except Exception as exc:
            conn.status = "error"
            # Include the exception TYPE — TimeoutError/CancelledError have
            # empty str() and would otherwise show as a blank error.
            conn.error = f"{type(exc).__name__}: {str(exc) or 'no details'}"
            # Append the server's own stderr tail — it usually says exactly
            # why it died (missing API key, bad login, ...).
            tail = ""
            if conn.errlog_file is not None:
                try:
                    conn.errlog_file.seek(0)
                    raw = conn.errlog_file.read()
                    tail = raw.decode("utf-8", "replace").strip()[-280:]
                except Exception:
                    tail = ""
            if tail:
                conn.error = f"{conn.error} | server: {tail}"
            conn.error = conn.error[:500]
            log.warning("mcp_server_connect_failed", server=config.name, error=conn.error)
            conn.close_event.set()  # nothing to keep open

        # Keep the stack open until disconnect() signals us, then close it
        # HERE — in the same task that opened it (anyio requirement).
        await conn.close_event.wait()
        try:
            await conn.stack.aclose()
        except Exception as exc:
            log.debug("mcp_stack_close_error", error=str(exc)[:150])
        if conn.errlog_file is not None:
            try:
                conn.errlog_file.close()
            except Exception:
                pass
        if conn.errlog_path:
            try:
                os.unlink(conn.errlog_path)
            except Exception:
                pass

    async def disconnect(self, server_id: str):
        async with self._lock:
            await self._disconnect_locked(server_id)

    async def shutdown(self):
        async with self._lock:
            for server_id in list(self._conns):
                await self._disconnect_locked(server_id)
        if self._io_loop is not None and self._io_loop.is_running():
            self._io_loop.call_soon_threadsafe(self._io_loop.stop)

    async def _disconnect_locked(self, server_id: str):
        conn = self._conns.pop(server_id, None)
        if not conn:
            return
        # Ask the owner task (on the I/O loop) to close the stack in its
        # own task; the event lives on the I/O loop so set it thread-safe.
        if conn.close_event is not None and self._io_loop is not None:
            self._io_loop.call_soon_threadsafe(conn.close_event.set)
        else:
            conn.close_requested = True
        if conn.owner_future is not None:
            try:
                await asyncio.wait_for(
                    asyncio.wrap_future(conn.owner_future), timeout=10
                )
            except asyncio.TimeoutError:
                if conn.owner_task is not None and self._io_loop is not None:
                    self._io_loop.call_soon_threadsafe(conn.owner_task.cancel)
            except Exception:
                pass

    # ── Introspection ─────────────────────────────────────────────────────
    def status_for(self, server_id: str) -> MCPServerStatus:
        conn = self._conns.get(server_id)
        if not conn:
            return MCPServerStatus(id=server_id, name="?", transport="stdio")
        return MCPServerStatus(
            id=conn.config.id,
            name=conn.config.name,
            transport=conn.config.transport,
            status=conn.status,
            error=conn.error,
            tools=[t.name for t in conn.tools],
        )

    def statuses(self) -> List[MCPServerStatus]:
        return [self.status_for(sid) for sid in self._conns]

    def all_tools(self) -> List[MCPToolInfo]:
        tools: List[MCPToolInfo] = []
        for conn in self._conns.values():
            if conn.status == "connected":
                tools.extend(conn.tools)
        return tools

    def relevant_tools(self, text: str, max_tools: int = 12) -> List[MCPToolInfo]:
        """
        Pick the MCP tools relevant to a task/step. If nothing matches
        keyword hints but the catalog is small, hand over everything and
        let the LLM decide.
        """
        available = self.all_tools()
        if not available:
            return []
        lowered = text.lower()

        # Categories the task cares about
        active_categories = [
            cat for cat, kws in MCP_TOOL_KEYWORDS.items()
            if any(kw in lowered for kw in kws)
        ]

        matched: List[MCPToolInfo] = []
        if active_categories:
            hint_words = {
                kw for cat in active_categories for kw in MCP_TOOL_KEYWORDS[cat]
            }
            for t in available:
                haystack = f"{t.server_name} {t.name} {t.description}".lower()
                if any(kw in haystack for kw in hint_words):
                    matched.append(t)

        if not matched:
            # No keyword signal: only hand over the whole catalog when it is
            # small enough to be cheap; otherwise stay tool-free.
            matched = available if len(available) <= 8 else []
        return matched[:max_tools]

    # ── Tool execution ────────────────────────────────────────────────────
    async def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> str:
        conn = self._conns.get(server_id)
        if not conn or conn.status != "connected" or not conn.session:
            raise RuntimeError(f"MCP server not connected: {server_id}")

        async def _invoke():
            return await asyncio.wait_for(
                conn.session.call_tool(tool_name, arguments or {}), timeout=120
            )

        result = await self._run_on_io(_invoke())
        parts: List[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        output = "\n".join(parts).strip()
        if result.isError:
            raise RuntimeError(output or "MCP tool returned an error")
        return output[:60_000]

    def find_tool(self, tool_name: str) -> Optional[MCPToolInfo]:
        """Locate a tool by name across all connected servers."""
        for t in self.all_tools():
            if t.name == tool_name:
                return t
        return None


# Global singleton
mcp_manager = MCPManager()
