"""
MCP server configuration models + keyword hints for automatic tool routing.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """One user-connected MCP server (stdio command or HTTP/SSE URL)."""

    id: str
    name: str
    transport: str = "stdio"  # "stdio" | "sse" | "http"
    # stdio
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    # remote
    url: str = ""
    enabled: bool = True


class MCPServerStatus(BaseModel):
    """Runtime status surfaced to the frontend."""

    id: str
    name: str
    transport: str
    status: str = "disconnected"  # disconnected | connecting | connected | error
    error: str = ""
    tools: List[str] = Field(default_factory=list)


class MCPToolInfo(BaseModel):
    """A single callable tool discovered on a connected server."""

    server_id: str
    server_name: str
    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Well-known MCP server presets (shown as one-click templates in the UI)
# ---------------------------------------------------------------------------
MCP_PRESETS: List[dict] = [
    {
        "key": "meta-ads",
        "name": "Meta Ads",
        "description": "Run & manage Facebook/Instagram ad campaigns, audiences and creatives",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "meta-ads-mcp"],
        "env_keys": ["META_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET", "META_BUSINESS_ID"],
    },
    {
        "key": "google-analytics",
        "name": "Google Analytics",
        "description": "Website traffic, audience and conversion analytics (GA4)",
        "transport": "stdio",
        "command": "pipx",
        "args": ["run", "--spec", "google-analytics-mcp", "analytics-mcp"],
        "env_keys": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_PROJECT_ID"],
    },
    {
        "key": "posthog",
        "name": "PostHog",
        "description": "Product analytics, funnels and user behavior from PostHog",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "posthog-mcp-server"],
        "env_keys": ["POSTHOG_API_KEY", "POSTHOG_HOST"],
    },
    {
        "key": "firebase",
        "name": "Firebase",
        "description": "Firestore data access for Firebase apps (queries, collections, docs)",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "firebase-mcp"],
        "env_keys": ["GOOGLE_APPLICATION_CREDENTIALS"],
    },
    {
        "key": "browser",
        "name": "Browser (Playwright)",
        "description": "Real browser automation — open pages, click, fill forms, screenshot",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
        "env_keys": [],
    },
]


# Old preset args that pointed at npm packages that never existed (404).
# Saved configs using these are healed to the real package on load.
LEGACY_ARGS_FIXUPS: Dict[tuple, dict] = {
    ("-y", "@modelcontextprotocol/meta-ads"): {
        "command": "npx", "args": ["-y", "meta-ads-mcp"],
    },
    ("-y", "@modelcontextprotocol/google-analytics"): {
        "command": "pipx",
        "args": ["run", "--spec", "google-analytics-mcp", "analytics-mcp"],
    },
    ("-y", "@posthog/mcp-server"): {
        "command": "npx", "args": ["-y", "posthog-mcp-server"],
    },
    ("-y", "firebase-tools@experimental-mcp"): {
        "command": "npx", "args": ["-y", "firebase-mcp"],
    },
}


# Keywords in a task/step that indicate which MCP tools are relevant.
# Matched against server name + tool names/descriptions (all lowercase).
MCP_TOOL_KEYWORDS: Dict[str, List[str]] = {
    "ads": ["ads", "campaign", "advertising", "meta", "facebook", "instagram", "audience", "ctr", "cpc", "roas"],
    "analytics": ["analytics", "traffic", "visitors", "conversion", "funnel", "retention", "sessions", "posthog", "firebase", "ga4", "google analytics", "website data"],
    "browser": ["browse", "open page", "screenshot", "click", "fill form", "login to site", "download", "website", "webpage", "navigate", "extract"],
}
