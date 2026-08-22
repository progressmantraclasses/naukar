"""
Groq LLM Provider — implements LLMProvider using the Groq SDK.
Supports compound-beta and compound-beta-mini models.
"""
import time
import asyncio
from typing import AsyncIterator, List
import structlog

from groq import AsyncGroq
from groq import APIError, APIStatusError, RateLimitError

from app.llm.provider import LLMProvider, LLMRequest, LLMResponse, Message
from app.core.config import settings

log = structlog.get_logger()

# Cost per 1M tokens (USD) — approximate Groq pricing
_COST_TABLE = {
    "compound-beta": {"input": 0.90, "output": 0.90},
    "compound-beta-mini": {"input": 0.40, "output": 0.40},
    # Fallback
    "default": {"input": 0.50, "output": 0.50},
}

# Internal model name mapping
_MODEL_MAP = {
    "groq/compound": settings.GROQ_COMPOUND_MODEL,
    "groq/compound-mini": settings.GROQ_COMPOUND_MINI_MODEL,
    # Direct names pass through
}


def _resolve_model(model: str) -> str:
    return _MODEL_MAP.get(model, model)


class GroqProvider(LLMProvider):

    def __init__(self):
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def available_models(self) -> List[str]:
        return ["groq/compound", "groq/compound-mini"]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        resolved_model = _resolve_model(request.model)
        messages = self._build_messages(request)

        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            start = time.monotonic()
            try:
                kwargs = dict(
                    model=resolved_model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                if request.json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = await self._client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)

                content = response.choices[0].message.content or ""
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0
                cost = await self.estimate_cost(prompt_tokens, completion_tokens, resolved_model)

                log.debug(
                    "groq_response",
                    model=resolved_model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    attempt=attempt + 1
                )

                return LLMResponse(
                    content=content,
                    model=resolved_model,
                    provider="groq",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                )

            except RateLimitError as e:
                if attempt == settings.MAX_RETRY_ATTEMPTS - 1:
                    log.error("groq_rate_limit_error_final", error=str(e), model=resolved_model)
                    raise
                import re
                wait_time = 2 ** attempt * 5
                match = re.search(r"try again in (\d+(\.\d+)?)s", str(e))
                if match:
                    wait_time = float(match.group(1)) + 1
                log.warning("groq_rate_limit_error", wait_time=wait_time, attempt=attempt+1, error=str(e))
                await asyncio.sleep(wait_time)
                
            except APIStatusError as e:
                if e.status_code == 413:
                    log.error("groq_payload_too_large", error=str(e), model=resolved_model)
                    raise
                if attempt == settings.MAX_RETRY_ATTEMPTS - 1:
                    raise
                log.warning("groq_api_status_error", status_code=e.status_code, attempt=attempt+1)
                await asyncio.sleep(2 ** attempt * 2)

            except APIError as e:
                log.error("groq_api_error", error=str(e), model=resolved_model)
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        resolved_model = _resolve_model(request.model)
        messages = self._build_messages(request)

        stream = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        pricing = _COST_TABLE.get(model, _COST_TABLE["default"])
        return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000

    def _build_messages(self, request: LLMRequest) -> list:
        msgs = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return msgs
