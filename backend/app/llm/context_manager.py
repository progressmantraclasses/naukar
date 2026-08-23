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
        selected: list[Message] = []
        used = 0
        for message in reversed(messages):
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
        return replace(request, system_prompt=system, messages=selected)

    def _truncate(self, text: str, token_limit: int) -> str:
        if token_limit <= 0:
            return ""
        approximate_chars = max(token_limit * 4, 1)
        return text[-approximate_chars:]


context_manager = ContextManager()
