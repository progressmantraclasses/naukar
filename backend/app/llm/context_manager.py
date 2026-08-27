"""Deterministic context selection and token budgeting for LLM requests."""
from dataclasses import replace
from typing import Iterable

from app.core.config import settings
from app.llm.provider import LLMRequest, Message


class ContextManager:
    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            return len(tiktoken.get_encoding("cl100k_base").encode(text))
        except Exception:
            return max(len(text) // 4, 1)

    def prepare(self, request: LLMRequest) -> LLMRequest:
        available = max(settings.LLM_CONTEXT_TOKENS - request.max_tokens, 256)
        system = request.system_prompt or ""
        system_tokens = self.count_tokens(system)
        messages = list(request.messages)
        remaining = max(available - system_tokens, 128)

        # Tool-call conversations must stay intact: an assistant turn with
        # tool_calls and its following role:tool replies are one atomic unit.
        # The API rejects orphaned tool messages (400 invalid_request_error).
        tail: list[Message] = []
        for message in reversed(messages):
            if message.role == "tool" or (message.raw and message.raw.get("tool_calls")):
                tail.append(message)
            else:
                break
        tail.reverse()
        core = messages[: len(messages) - len(tail)]
        tail_tokens = sum(self.count_tokens(m.content) for m in tail)

        selected: list[Message] = []
        used = tail_tokens
        for message in reversed(core):
            tokens = self.count_tokens(message.content)
            if used + tokens > remaining and selected:
                break
            if used + tokens > remaining:
                content = self._truncate(message.content, remaining - used)
                selected.append(Message(role=message.role, content=content))
                break
            selected.append(message)
            used += tokens
        selected.reverse()
        return replace(request, system_prompt=system, messages=selected + tail)

    def _truncate(self, text: str, token_limit: int) -> str:
        if token_limit <= 0:
            return ""
        approximate_chars = max(token_limit * 4, 1)
        return text[-approximate_chars:]


context_manager = ContextManager()
