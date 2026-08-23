"""Configurable model pricing registry."""
import json
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ModelPricing:
    input: float
    output: float
    cached_input: float = 0.0


class PricingRegistry:
    def __init__(self):
        try:
            raw = json.loads(settings.MODEL_PRICING_JSON)
        except json.JSONDecodeError:
            raw = {}
        self._prices = {
            model: ModelPricing(
                input=float(values.get("input", 0.0)),
                output=float(values.get("output", 0.0)),
                cached_input=float(values.get("cached_input", 0.0)),
            )
            for model, values in raw.items()
        }

    def get(self, model: str) -> ModelPricing:
        return self._prices.get(model, ModelPricing(0.0, 0.0))

    def cost(self, model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
        pricing = self.get(model)
        billable_input = max(input_tokens - cached_tokens, 0)
        return (billable_input * pricing.input + cached_tokens * pricing.cached_input + output_tokens * pricing.output) / 1_000_000


pricing_registry = PricingRegistry()