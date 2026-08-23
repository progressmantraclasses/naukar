"""PostgreSQL/pgvector semantic cache for safe, non-fresh requests."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import SemanticCache
from app.memory.embeddings import EmbeddingProvider, embedding_provider


class SemanticCacheService:
    def __init__(self, provider: EmbeddingProvider = embedding_provider):
        self._provider = provider

    async def get(
        self,
        db: AsyncSession,
        text: str,
        user_id: str = "anonymous",
        workspace_id: str = "default",
        task_type: Optional[str] = None,
        time_sensitive: bool = False,
    ) -> Optional[SemanticCache]:
        if time_sensitive or not text.strip():
            return None
        embedding = await self._provider.embed(text)
        distance = SemanticCache.embedding.cosine_distance(embedding).label("distance")
        query = select(SemanticCache, distance).where(
            SemanticCache.user_id == user_id,
            SemanticCache.workspace_id == workspace_id,
            SemanticCache.time_sensitive.is_(False),
        )
        if task_type:
            query = query.where(SemanticCache.task_type == task_type)
        query = query.order_by(distance).limit(1)
        result = await db.execute(query)
        row = result.first()
        if not row:
            return None
        candidate, similarity_distance = row
        if 1.0 - float(similarity_distance) < settings.SEMANTIC_CACHE_THRESHOLD:
            return None
        return candidate

    async def put(
        self,
        db: AsyncSession,
        text: str,
        response: str,
        model: str,
        user_id: str = "anonymous",
        workspace_id: str = "default",
        task_type: Optional[str] = None,
        time_sensitive: bool = False,
    ):
        if time_sensitive or not text.strip() or not response.strip():
            return
        db.add(SemanticCache(
            user_id=user_id,
            workspace_id=workspace_id,
            input_text=text,
            response=response,
            model=model,
            task_type=task_type,
            embedding=await self._provider.embed(text),
            time_sensitive=False,
        ))


semantic_cache = SemanticCacheService()
