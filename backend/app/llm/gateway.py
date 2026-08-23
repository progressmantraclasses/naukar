"""Single controlled entry point for model calls, caching, and cost policy."""
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from dataclasses import replace
from typing import Optional

import structlog

from app.core.config import settings
from app.llm.cost_optimizer import CostOptimizer
from app.llm.provider import LLMProvider, LLMRequest, LLMResponse
from app.llm.registry import llm_registry
from app.core.redis_store import redis_store
from app.llm.context_manager import context_manager
from app.core.observability import metrics
from app.llm.token_tracker import token_tracker

log = structlog.get_logger()
_usage_session: ContextVar[object | None] = ContextVar("llm_usage_session", default=None)
_usage_user_id: ContextVar[str] = ContextVar("llm_usage_user_id", default="anonymous")


def bind_usage_session(session: object, user_id: str = "anonymous"):
    """Bind the current task's database session for usage recording."""
    _usage_user_id.set(user_id or "anonymous")
    return _usage_session.set(session)


class AIGateway:
    """Centralizes every LLM request made by the application."""

    CACHE_PREFIX = "naukar:llm:exact:v1:"

    def __init__(self, registry=llm_registry):
        self._registry = registry
        self._optimizer = CostOptimizer()

    async def generate(self, request: LLMRequest) -> LLMResponse:
        request = context_manager.prepare(request)
        decision = self._optimizer.choose(request)
        if decision.max_tokens == 0:
            raise ValueError("NO_LLM requests must be handled by a deterministic tool")

        controlled = replace(request, model=decision.model, max_tokens=decision.max_tokens)
        cache_key = self._cache_key(controlled)
        if decision.cacheable:
            cached = await self._get_cached(cache_key)
            if cached:
                cached.raw = {**(cached.raw or {}), "cache_hit": True}
                metrics.increment("llm_requests_total")
                metrics.increment("cache_hits_total")
                await self._record_usage(controlled, cached, cache_hit=True)
                log.info("llm_cache_hit", model=cached.model, task_id=request.task_id)
                # Track cache hit in token tracker
                if request.task_id:
                    step_label = self._build_step_label(request)
                    token_tracker.record(
                        task_id=request.task_id,
                        step_label=step_label,
                        model=cached.model,
                        source="cache",
                        prompt_tokens=cached.prompt_tokens,
                        completion_tokens=cached.completion_tokens,
                        cost_usd=0.0,
                        latency_ms=cached.latency_ms,
                    )
                    await self._emit_token_event(request, cached, source="cache")
                return cached
            semantic = await self._get_semantic_cache(controlled)
            if semantic:
                response = LLMResponse(
                    content=semantic.response,
                    model=semantic.model,
                    provider="semantic-cache",
                    raw={"cache_hit": True, "semantic_cache_hit": True},
                )
                metrics.increment("llm_requests_total")
                metrics.increment("cache_hits_total")
                metrics.increment("semantic_cache_hits_total")
                await self._record_usage(controlled, response, cache_hit=True)
                return response

        decision, degraded = await self._fit_budget(request, decision)

        controlled = replace(request, model=decision.model, max_tokens=decision.max_tokens)
        await self._check_rate_limit(controlled)
        provider = self._registry.get_provider(controlled.model)
        response = await provider.generate(controlled)
        metrics.increment("llm_requests_total")
        metrics.increment("llm_tokens_total", response.prompt_tokens + response.completion_tokens)
        metrics.increment("llm_cost_total", response.cost_usd)
        metrics.observe("llm_latency", response.latency_ms)
        response.raw = {**(response.raw or {}), "cache_hit": False, "budget_degraded": degraded}
        await self._record_usage(controlled, response, cache_hit=False)
        if decision.cacheable:
            await self._set_cached(cache_key, response)
            await self._set_semantic_cache(controlled, response)
        log.info(
            "llm_gateway_request",
            model=response.model,
            task_id=request.task_id,
            input_tokens=response.prompt_tokens,
            output_tokens=response.completion_tokens,
            cost_usd=response.cost_usd,
        )
        # Track in token tracker and emit WebSocket event
        if request.task_id:
            step_label = self._build_step_label(request)
            token_tracker.record(
                task_id=request.task_id,
                step_label=step_label,
                model=response.model,
                source="llm",
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cost_usd=response.cost_usd,
                latency_ms=response.latency_ms,
            )
            await self._emit_token_event(request, response, source="llm")
        return response

    async def _check_rate_limit(self, request: LLMRequest):
        user_id = request.user_id or _usage_user_id.get()
        try:
            allowed, _ = await redis_store.increment_window(
                f"naukar:ratelimit:llm:{user_id}", 60, settings.LLM_REQUESTS_PER_MINUTE
            )
            if not allowed:
                raise RuntimeError("LLM request rate limit exceeded")
        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("llm_rate_limit_unavailable", error=str(exc))

    async def _fit_budget(self, request: LLMRequest, decision):
        session = _usage_session.get()
        if session is None:
            return decision, False
        try:
            from sqlalchemy import func, select
            from app.db.models import AIUsage
            period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            spent = await session.scalar(select(func.coalesce(func.sum(AIUsage.actual_cost), 0.0)).where(
                AIUsage.user_id == (request.user_id or _usage_user_id.get()),
                AIUsage.created_at >= period_start,
            ))
            remaining = max(settings.MONTHLY_USER_BUDGET_USD - float(spent or 0.0), 0.0)
            if self._optimizer.estimate_request_cost(request, decision) <= remaining:
                return decision, False
            cheap_request = replace(request, model=settings.MODEL_FAST, max_tokens=settings.CHEAP_MAX_OUTPUT_TOKENS)
            cheap_decision = self._optimizer.choose(cheap_request)
            if self._optimizer.estimate_request_cost(cheap_request, cheap_decision) <= remaining:
                return cheap_decision, True
            raise RuntimeError("Monthly AI budget is exhausted for this user")
        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("llm_budget_check_failed", error=str(exc), task_id=request.task_id)
            return decision, False

    async def _record_usage(self, request: LLMRequest, response: LLMResponse, cache_hit: bool):
        session = _usage_session.get()
        if session is None:
            return
        try:
            from app.db.models import AIUsage
            session.add(AIUsage(
                user_id=request.user_id or _usage_user_id.get(),
                request_id=request.request_id,
                task_id=request.task_id,
                model=response.model,
                task_type=request.task_type,
                input_tokens=response.prompt_tokens,
                output_tokens=response.completion_tokens,
                cached_tokens=response.prompt_tokens if cache_hit else 0,
                estimated_cost=response.cost_usd,
                actual_cost=0.0 if cache_hit else response.cost_usd,
                cache_hit=cache_hit,
                semantic_cache_hit=bool((response.raw or {}).get("semantic_cache_hit")),
                status="cached" if cache_hit else "completed",
            ))
            await session.flush()
        except Exception as exc:
            log.warning("llm_usage_record_failed", error=str(exc), task_id=request.task_id)

    async def _get_semantic_cache(self, request: LLMRequest):
        session = _usage_session.get()
        if session is None or request.freshness_required:
            return None
        try:
            from app.memory.semantic_cache import semantic_cache
            text = self._cache_text(request)
            return await semantic_cache.get(
                session, text, request.user_id or _usage_user_id.get(),
                request.workspace_id or "default", request.task_type,
                request.freshness_required,
            )
        except Exception as exc:
            log.warning("semantic_cache_read_failed", error=str(exc), task_id=request.task_id)
            return None

    async def _set_semantic_cache(self, request: LLMRequest, response: LLMResponse):
        session = _usage_session.get()
        if session is None or request.freshness_required:
            return
        try:
            from app.memory.semantic_cache import semantic_cache
            await semantic_cache.put(
                session, self._cache_text(request), response.content, response.model,
                request.user_id or _usage_user_id.get(), request.workspace_id or "default",
                request.task_type, request.freshness_required,
            )
        except Exception as exc:
            log.warning("semantic_cache_write_failed", error=str(exc), task_id=request.task_id)

    @staticmethod
    def _cache_text(request: LLMRequest) -> str:
        return json.dumps({
            "system": request.system_prompt or "",
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }, sort_keys=True, ensure_ascii=True)

    def _cache_key(self, request: LLMRequest) -> str:
        payload = {
            "user_id": request.user_id or "anonymous",
            "workspace_id": request.workspace_id or "default",
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "system_prompt": request.system_prompt or "",
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "json_mode": request.json_mode,
            "task_type": request.task_type or "",
        }
        digest = redis_store.digest(payload)
        return f"{self.CACHE_PREFIX}{digest}"

    async def _get_redis(self):
        return await redis_store.client()

    async def _get_cached(self, key: str) -> Optional[LLMResponse]:
        try:
            value = await (await self._get_redis()).get(key)
            if not value:
                return None
            return LLMResponse(**json.loads(value))
        except Exception as exc:
            log.warning("llm_cache_read_failed", error=str(exc))
            return None

    async def _set_cached(self, key: str, response: LLMResponse):
        try:
            payload = {field: getattr(response, field) for field in (
                "content", "model", "provider", "prompt_tokens", "completion_tokens",
                "cost_usd", "latency_ms", "raw"
            )}
            await (await self._get_redis()).setex(
                key, settings.LLM_CACHE_TTL_SECONDS, json.dumps(payload, ensure_ascii=True)
            )
        except Exception as exc:
            log.warning("llm_cache_write_failed", error=str(exc))

    @staticmethod
    def _build_step_label(request: LLMRequest) -> str:
        """Build a human-readable label for the token usage entry."""
        if request.step_id:
            # Extract from messages if possible
            if request.messages:
                first_msg = request.messages[0].content[:60].split("\n")[0].strip()
                return f"Step: {first_msg}"
        if request.task_type:
            return f"{request.task_type.title()} Request"
        # Fallback: use system prompt first line
        if request.system_prompt:
            first_line = request.system_prompt.split("\n")[0][:50].strip()
            return first_line
        return "LLM Request"

    async def _emit_token_event(self, request: LLMRequest, response: LLMResponse, source: str):
        """Emit a TOKEN_USAGE event to the WebSocket."""
        try:
            from app.core.events import event_bus, Event, EventType
            summary = token_tracker.get_summary(request.task_id)
            await event_bus.publish(Event(
                event_type=EventType.TOKEN_USAGE,
                task_id=request.task_id,
                payload={
                    "step_label": self._build_step_label(request),
                    "model": response.model,
                    "source": source,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.prompt_tokens + response.completion_tokens,
                    "cost_usd": round(response.cost_usd, 6),
                    "latency_ms": response.latency_ms,
                    "cumulative_tokens": summary.total_tokens if summary else 0,
                    "cumulative_cost_usd": round(summary.total_cost_usd, 6) if summary else 0.0,
                    "cumulative_llm_calls": summary.llm_calls if summary else 0,
                    "cumulative_cache_hits": summary.cache_hits if summary else 0,
                },
            ))
        except Exception as exc:
            log.warning("token_event_emit_failed", error=str(exc))


ai_gateway = AIGateway()