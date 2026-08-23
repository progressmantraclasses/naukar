"""Deterministic model and token policy for cost-efficient LLM calls."""
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.llm.pricing import pricing_registry


@dataclass(frozen=True)
class CostDecision:
    model: str
    max_tokens: int
    cacheable: bool


class CostOptimizer:
    """Select the least expensive capable tier from request metadata."""

    def choose(self, request) -> CostDecision:
        tier = (request.routing_tier or "").lower()
        if tier == "no_llm":
            return CostDecision(request.model, 0, False)
        if tier == "cheap":
            model = settings.MODEL_FAST
            limit = min(request.max_tokens, settings.CHEAP_MAX_OUTPUT_TOKENS)
        elif tier == "reasoning":
            model = settings.MODEL_HEAVY
            limit = min(request.max_tokens, settings.REASONING_MAX_OUTPUT_TOKENS)
        else:
            model = request.model or settings.MODEL_SMART
            limit = min(request.max_tokens, settings.STANDARD_MAX_OUTPUT_TOKENS)
        return CostDecision(model=model, max_tokens=limit, cacheable=request.cacheable)

    def estimate_request_cost(self, request, decision: CostDecision) -> float:
        """Conservative preflight estimate used to protect the hard budget."""
        input_tokens = sum(len(message.content) for message in request.messages) // 4
        input_tokens += len(request.system_prompt or "") // 4
        pricing = pricing_registry.get(decision.model)
        input_price = pricing.input
        output_price = pricing.output
        return (input_tokens * input_price + decision.max_tokens * output_price) / 1_000_000