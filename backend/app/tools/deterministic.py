"""Small deterministic dispatcher for requests that need no LLM reasoning."""
import re
from typing import Optional

from app.tools.registry import tool_registry


_CALCULATION = re.compile(r"^\s*(?:calculate|compute|what\s+is)\s+([0-9\s().+*/%\-]+)\??\s*$", re.IGNORECASE)


async def try_deterministic(user_input: str) -> Optional[str]:
    match = _CALCULATION.match(user_input)
    if not match:
        return None
    value = await tool_registry.execute("calculator", {"expression": match.group(1)}, task_id="deterministic")
    return f"{value:g}" if isinstance(value, float) else str(value)
