"""
MCP API — connect/manage external MCP tool servers (Meta Ads, Analytics, etc.)
Employees automatically use tools from connected servers.
"""
import asyncio
import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.events import Event, EventType, event_bus
from app.mcp.manager import mcp_manager
from app.mcp.models import MCP_PRESETS, MCPServerConfig
from app.mcp.store import load_configs, save_configs

log = structlog.get_logger()
router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class AddServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    transport: str = Field(default="stdio", pattern="^(stdio|sse|http)$")
    command: str = Field(default="", max_length=200)
    args: List[str] = Field(default_factory=list)
    env: dict = Field(default_factory=dict)
    url: str = Field(default="", max_length=500)
    connect_now: bool = True


class ServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    command: str = ""
    args: List[str] = []
    env: dict = {}
    url: str = ""
    enabled: bool = True
    status: str = "disconnected"
    error: str = ""
    tools: List[str] = []


def _to_response(cfg: MCPServerConfig) -> ServerResponse:
    status = mcp_manager.status_for(cfg.id)
    return ServerResponse(
        id=cfg.id,
        name=cfg.name,
        transport=cfg.transport,
        command=cfg.command,
        args=cfg.args,
        env={k: "••••" for k in cfg.env},  # never leak secret values
        url=cfg.url,
        enabled=cfg.enabled,
        status=status.status,
        error=status.error,
        tools=status.tools,
    )


async def _broadcast_status(cfg: MCPServerConfig):
    status = mcp_manager.status_for(cfg.id)
    await event_bus.publish(Event(
        event_type=EventType.MCP_SERVER_STATUS,
        task_id="*",
        payload=status.model_dump(),
    ))


@router.get("/presets")
async def list_presets():
    return {"presets": MCP_PRESETS}


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers():
    return [_to_response(cfg) for cfg in load_configs()]


@router.post("/servers", response_model=ServerResponse)
async def add_server(body: AddServerRequest):
    if body.transport == "stdio" and not body.command.strip():
        raise HTTPException(status_code=400, detail="stdio transport requires a command")
    if body.transport in ("sse", "http") and not body.url.strip():
        raise HTTPException(status_code=400, detail="sse/http transport requires a url")

    cfg = MCPServerConfig(
        id=str(uuid.uuid4()),
        name=body.name.strip(),
        transport=body.transport,
        command=body.command.strip(),
        args=[str(a) for a in body.args][:32],
        env={str(k): str(v) for k, v in body.env.items()},
        url=body.url.strip(),
    )
    configs = load_configs()
    configs.append(cfg)
    save_configs(configs)
    log.info("mcp_server_added", server=cfg.name, transport=cfg.transport)

    if body.connect_now:
        await mcp_manager.connect(cfg)
        await _broadcast_status(cfg)
    return _to_response(cfg)


@router.post("/servers/{server_id}/reconnect", response_model=ServerResponse)
async def reconnect_server(server_id: str):
    cfg = next((c for c in load_configs() if c.id == server_id), None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Server not found")
    await mcp_manager.connect(cfg)
    await _broadcast_status(cfg)
    return _to_response(cfg)


@router.delete("/servers/{server_id}")
async def remove_server(server_id: str):
    configs = load_configs()
    remaining = [c for c in configs if c.id != server_id]
    if len(remaining) == len(configs):
        raise HTTPException(status_code=404, detail="Server not found")
    save_configs(remaining)
    await mcp_manager.disconnect(server_id)
    log.info("mcp_server_removed", server_id=server_id)
    return {"ok": True}


@router.get("/tools")
async def list_tools():
    """All tools across connected servers — what employees can use."""
    return {
        "tools": [t.model_dump() for t in mcp_manager.all_tools()],
        "servers_connected": len(mcp_manager.statuses()),
    }
