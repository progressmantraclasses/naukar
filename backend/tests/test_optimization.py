import pytest

from app.core.security import _valid_id
from app.llm.context_manager import context_manager
from app.llm.gateway import AIGateway
from app.llm.pricing import pricing_registry
from app.llm.provider import LLMRequest, Message
from app.tools.deterministic import try_deterministic
from app.tools.registry import tool_registry


@pytest.mark.asyncio
async def test_arithmetic_bypasses_llm():
    assert await try_deterministic("Calculate 18291 * 391") == "7151781"
    assert await try_deterministic("Explain the calculation") is None


def test_cache_key_isolated_by_user_and_workspace():
    gateway = AIGateway()
    base = LLMRequest(messages=[Message("user", "same")], model="groq/compound")
    first = gateway._cache_key(base)
    second = gateway._cache_key(LLMRequest(messages=base.messages, model=base.model, user_id="other"))
    third = gateway._cache_key(LLMRequest(messages=base.messages, model=base.model, workspace_id="other"))
    assert len({first, second, third}) == 3


def test_context_manager_keeps_latest_message():
    request = LLMRequest(
        messages=[Message("user", "old " * 5000), Message("user", "latest")],
        model="groq/compound",
        max_tokens=1000,
    )
    prepared = context_manager.prepare(request)
    assert prepared.messages[-1].content == "latest"
    assert sum(context_manager.count_tokens(item.content) for item in prepared.messages) <= 5200


def test_pricing_registry_calculates_cost():
    assert pricing_registry.cost("openai/gpt-oss-120b", 1_000_000, 1_000_000) == pytest.approx(0.75)

@pytest.mark.asyncio
async def test_tool_permissions_and_validation():
    assert await tool_registry.execute("calculator", {"expression": "2 + 2"}) == 4
    with pytest.raises(PermissionError):
        await tool_registry.execute("file_writer", {"path": "x.txt", "content": "x"})
    with pytest.raises(ValueError):
        await tool_registry.execute("calculator", {})


def test_identity_validation_rejects_unsafe_values():
    assert _valid_id("user-1", "anonymous") == "user-1"
    assert _valid_id("../secret", "anonymous") == "anonymous"
