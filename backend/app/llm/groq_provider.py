"""Groq LLM provider implementation."""
import time
import asyncio
from typing import AsyncIterator, List
import structlog

from groq import AsyncGroq
from groq import APIError, APIStatusError, RateLimitError

from app.llm.provider import LLMProvider, LLMRequest, LLMResponse, Message
from app.core.config import settings
from app.llm.pricing import pricing_registry

log = structlog.get_logger()

# Internal model name mapping
_MODEL_MAP = {
    "groq/compound": settings.GROQ_COMPOUND_MODEL,
    "groq/compound-mini": settings.GROQ_COMPOUND_MINI_MODEL,
    # Direct names pass through
}

# Daily-quota fallback: when the primary model hits its TPD limit (429),
# degrade to the small OSS model, which has its own quota, instead of
# failing the whole task. NOTE: groq/compound-mini is an alias of
# openai/gpt-oss-120b and shares its quota — never use it as fallback.
_QUOTA_FALLBACK = "openai/gpt-oss-20b"


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
        max_tokens = min(request.max_tokens, settings.GROQ_MAX_OUTPUT_TOKENS)

        attempt = 0
        rate_retries = 0
        # Groq free-tier quotas rotate as rolling windows; long "try again in
        # Xm" waits are usually short rolling-window drains, so retry
        # patiently instead of failing the whole task.
        MAX_RATE_RETRIES = 10
        while attempt < settings.MAX_RETRY_ATTEMPTS:
            start = time.monotonic()
            try:
                kwargs = dict(
                    model=resolved_model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=max_tokens,
                )
                if request.json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                if request.tools:
                    kwargs["tools"] = request.tools
                    kwargs["tool_choice"] = "auto"

                response = await self._client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)

                message = response.choices[0].message
                content = message.content or ""
                tool_calls = None
                if getattr(message, "tool_calls", None):
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in message.tool_calls
                    ]
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
                    tool_calls=tool_calls,
                )

            except RateLimitError as e:
                msg = str(e)
                # Daily token quota exhausted → degrade to fallback model
                # (separate quota) rather than killing the task. The
                # downgrade does not consume a retry attempt.
                if "tokens per day" in msg:
                    fallback = _resolve_model(_QUOTA_FALLBACK)
                    if resolved_model != fallback:
                        log.warning(
                            "groq_quota_degrading",
                            model=resolved_model,
                            fallback=fallback,
                        )
                        resolved_model = fallback
                        continue
                if rate_retries >= MAX_RATE_RETRIES:
                    log.error("groq_rate_limit_error_final", error=msg, model=resolved_model)
                    raise
                rate_retries += 1
                import re
                wait_time = 2 ** min(rate_retries, 4) * 3
                match = re.search(r"try again in (\d+(\.\d+)?)s", msg)
                if match:
                    wait_time = min(float(match.group(1)) + 1, 45)
                wait_time = min(wait_time, 45)
                log.warning("groq_rate_limit_error", wait_time=wait_time, rate_retry=rate_retries, error=msg[:160])
                await asyncio.sleep(wait_time)

            except APIStatusError as e:
                if e.status_code == 413:
                    log.error("groq_payload_too_large", error=str(e), model=resolved_model)
                    raise
                attempt += 1
                if attempt >= settings.MAX_RETRY_ATTEMPTS:
                    raise
                log.warning("groq_api_status_error", status_code=e.status_code, attempt=attempt)
                await asyncio.sleep(2 ** min(attempt, 3) * 2)

            except APIError as e:
                log.error("groq_api_error", error=str(e), model=resolved_model)
                raise

  
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        resolved_model = _resolve_model(request.model)
        messages = self._build_messages(request)
        max_tokens = min(request.max_tokens, settings.GROQ_MAX_OUTPUT_TOKENS)

        stream = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        return pricing_registry.cost(model, prompt_tokens, completion_tokens)

    def _build_messages(self, request: LLMRequest) -> list:
        msgs = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            # Raw dict messages carry tool-call turns verbatim
            if m.raw:
                msgs.append(m.raw)
            else:
                msgs.append({"role": m.role, "content": m.content})
        return msgs
