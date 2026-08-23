"""Permission-aware deterministic tool registry."""
import ast
import json
import operator
from pathlib import Path
from urllib.parse import urlparse
import httpx
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from app.core.config import settings
from app.tools.search import search_provider
from app.core.redis_store import redis_store


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    permissions: tuple[str, ...]
    estimated_cost: float
    input_schema: dict[str, Any]
    execute: Callable[[dict[str, Any]], Awaitable[Any]]


async def calculate(arguments: dict[str, Any]):
    expression = str(arguments.get("expression", ""))
    tree = ast.parse(expression, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.Constant)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("Only arithmetic expressions are allowed")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return -evaluate(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in operations: return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        raise ValueError("Invalid arithmetic expression")
    return evaluate(tree.body)


async def process_json(arguments: dict[str, Any]):
    return json.loads(arguments.get("value", "null"))


async def process_text(arguments: dict[str, Any]):
    value = str(arguments.get("value", ""))
    operation = arguments.get("operation", "strip")
    return value.strip() if operation == "strip" else value.lower() if operation == "lower" else value.upper() if operation == "upper" else value


async def read_file(arguments: dict[str, Any]):
    root = Path(settings.TOOL_WORKSPACE_ROOT).resolve()
    path = (root / str(arguments.get("path", ""))).resolve()
    if root not in path.parents and path != root:
        raise PermissionError("File path is outside the configured workspace")
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if path.stat().st_size > 1_000_000:
        raise ValueError("File exceeds the 1 MB read limit")
    return path.read_text(encoding="utf-8")


async def write_file(arguments: dict[str, Any]):
    root = Path(settings.TOOL_WORKSPACE_ROOT).resolve()
    path = (root / str(arguments.get("path", ""))).resolve()
    if root not in path.parents:
        raise PermissionError("File path is outside the configured workspace")
    content = str(arguments.get("content", ""))
    if len(content.encode("utf-8")) > 1_000_000:
        raise ValueError("File exceeds the 1 MB write limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "bytes": len(content.encode("utf-8"))}


async def web_search(arguments: dict[str, Any]):
    return await search_provider.search(str(arguments.get("query", "")), int(arguments.get("top_k", 5)))


async def http_request(arguments: dict[str, Any]):
    url = str(arguments.get("url", ""))
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only valid HTTP(S) URLs are allowed")
    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        raise ValueError("Local network targets are blocked")
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.request(str(arguments.get("method", "GET")).upper(), url, json=arguments.get("json"))
        return {"status_code": response.status_code, "headers": dict(response.headers), "body": response.text[:100_000]}


class ToolRegistry:
    def __init__(self):
        self._call_counts: dict[str, int] = {}
        self._action_counts: dict[str, dict[str, int]] = {}
        common = {"type": "object", "additionalProperties": False}
        self._tools = {
            "calculator": Tool("calculator", "Evaluate safe arithmetic", ("deterministic",), 0.0, {**common, "required": ["expression"], "properties": {"expression": {"type": "string"}}}, calculate),
            "json_processor": Tool("json_processor", "Parse JSON", ("deterministic",), 0.0, {**common, "required": ["value"], "properties": {"value": {"type": "string"}}}, process_json),
            "text_processor": Tool("text_processor", "Normalize text", ("deterministic",), 0.0, {**common, "required": ["value"], "properties": {"value": {"type": "string"}, "operation": {"enum": ["strip", "lower", "upper"]}}}, process_text),
            "file_reader": Tool("file_reader", "Read a UTF-8 text file", ("file_read",), 0.0, {**common, "required": ["path"], "properties": {"path": {"type": "string"}}}, read_file),
            "http": Tool("http", "Make a bounded HTTP request", ("http",), 0.0, {**common, "required": ["url"], "properties": {"url": {"type": "string"}, "method": {"enum": ["GET", "POST"]}, "json": {"type": "object"}}}, http_request),
                    "file_writer": Tool("file_writer", "Write a UTF-8 text file in the workspace", ("file_write",), 0.0, {**common, "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}, write_file),
                    "web_search": Tool("web_search", "Search the web through the configured provider", ("web_search",), 0.01, {**common, "required": ["query"], "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 10}}}, web_search),
        }

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    async def execute(self, name: str, arguments: dict[str, Any], permission: str = "deterministic", task_id: str = "local"):
        tool = self.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: {name}")
        if permission not in tool.permissions:
            raise PermissionError(f"Permission denied for tool: {name}")
        self._validate_arguments(tool, arguments)
        self._call_counts[task_id] = self._call_counts.get(task_id, 0) + 1
        if self._call_counts[task_id] > settings.MAX_TOOL_CALLS:
            raise RuntimeError("Maximum tool calls exceeded for this task")
        action_key = redis_store.digest({"name": name, "arguments": arguments})
        actions = self._action_counts.setdefault(task_id, {})
        actions[action_key] = actions.get(action_key, 0) + 1
        if actions[action_key] > settings.MAX_REPEAT_ACTIONS:
            raise RuntimeError(f"Repeated tool action stopped: {name}")
        return await tool.execute(arguments)

    @staticmethod
    def _validate_arguments(tool: Tool, arguments: dict[str, Any]):
        required = tool.input_schema.get("required", [])
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments for {tool.name}: {', '.join(missing)}")


tool_registry = ToolRegistry()
