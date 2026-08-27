"""
File-backed persistence for user-connected MCP server configs.
Kept as JSON (not Redis) so connections survive restarts without TTLs.
"""
import json
from pathlib import Path
from typing import List

import structlog

from app.mcp.models import LEGACY_ARGS_FIXUPS, MCPServerConfig

log = structlog.get_logger()

_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mcp_servers.json"


def load_configs() -> List[MCPServerConfig]:
    try:
        if not _STORE_PATH.is_file():
            return []
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        configs = [MCPServerConfig(**item) for item in raw]
        if _heal_legacy(configs):
            save_configs(configs)
        return configs
    except Exception as exc:
        log.warning("mcp_config_load_failed", error=str(exc))
        return []


def _heal_legacy(configs: List[MCPServerConfig]) -> bool:
    """Rewrite saved configs that used preset packages which never existed."""
    changed = False
    for cfg in configs:
        fix = LEGACY_ARGS_FIXUPS.get(tuple(cfg.args))
        if fix:
            log.info("mcp_config_healed", server=cfg.name, old_args=cfg.args, new_args=fix["args"])
            cfg.command = fix["command"]
            cfg.args = list(fix["args"])
            changed = True
    return changed


def save_configs(configs: List[MCPServerConfig]):
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STORE_PATH.write_text(
            json.dumps([c.model_dump() for c in configs], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("mcp_config_save_failed", error=str(exc))
