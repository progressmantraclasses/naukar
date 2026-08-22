"""
LLM Registry — single source of truth for available models and providers.
"""
from typing import Dict, Optional
from app.llm.provider import LLMProvider
from app.llm.groq_provider import GroqProvider
import structlog

log = structlog.get_logger()


class LLMRegistry:
    """
    Manages all LLM providers.
    Usage: registry.get_provider("groq/compound")
    """

    # Maps model prefixes to provider instances
    _providers: Dict[str, LLMProvider] = {}

    def __init__(self):
        self._register_defaults()

    def _register_defaults(self):
        groq = GroqProvider()
        for model in groq.available_models:
            self._providers[model] = groq
        log.info("llm_registry_initialized", providers=list(self._providers.keys()))

    def get_provider(self, model: str) -> LLMProvider:
        provider = self._providers.get(model)
        if not provider:
            # Try prefix match
            for key, p in self._providers.items():
                if model.startswith(key.split("/")[0]):
                    return p
            # Default to groq/compound
            log.warning("model_not_found_using_default", model=model)
            return self._providers["groq/compound"]
        return provider

    def register(self, model: str, provider: LLMProvider):
        self._providers[model] = provider


# Global singleton
llm_registry = LLMRegistry()
