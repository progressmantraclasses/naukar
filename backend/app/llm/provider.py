"""
LLM Provider abstraction — all LLM interactions go through this interface.
New providers (OpenAI, Anthropic, etc.) plug in without touching orchestrator code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, List, Dict, Any


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw: Optional[Dict[str, Any]] = None


@dataclass
class LLMRequest:
    messages: List[Message]
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None
    json_mode: bool = False
    task_id: Optional[str] = None
    employee_id: Optional[str] = None
    step_id: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the given request."""
        ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a response token by token."""
        ...

    @abstractmethod
    async def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Estimate the cost of a call."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        ...
