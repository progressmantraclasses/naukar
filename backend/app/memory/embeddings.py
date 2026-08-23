"""Embedding provider abstraction with a zero-cost deterministic fallback."""
import hashlib
import math
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Return a normalized embedding vector."""
        ...


class HashEmbeddingProvider(EmbeddingProvider):
    """Stable local vectorizer used until a hosted embedding provider is configured."""

    dimensions = 1536

    async def embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        words = text.lower().split()
        for index, word in enumerate(words):
            digest = hashlib.sha256(f"{index}:{word}".encode()).digest()
            position = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[position] += 1.0 if digest[4] % 2 else -1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]


embedding_provider = HashEmbeddingProvider()
