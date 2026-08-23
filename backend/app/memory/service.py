"""Short-term Redis and durable PostgreSQL memory services."""
import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_store import redis_store
from app.db.models import Memory
from app.memory.embeddings import embedding_provider


class MemoryService:
    async def set_short_term(self, user_id: str, conversation_id: str, value: dict, ttl: int = 3600):
        key = f"naukar:memory:short:{user_id}:{conversation_id}"
        await redis_store.set_json(key, value, ttl)

    async def get_short_term(self, user_id: str, conversation_id: str) -> Optional[dict]:
        return await redis_store.get_json(f"naukar:memory:short:{user_id}:{conversation_id}")

    async def remember(self, db: AsyncSession, content: str, user_id: str = "anonymous", workspace_id: str = "default", kind: str = "fact"):
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = await db.scalar(select(Memory).where(
            Memory.user_id == user_id, Memory.workspace_id == workspace_id, Memory.content_hash == content_hash,
        ).limit(1))
        if existing:
            return existing
        memory = Memory(user_id=user_id, workspace_id=workspace_id, content=content, content_hash=content_hash, kind=kind, embedding=await embedding_provider.embed(content))
        db.add(memory)
        await db.flush()
        return memory


memory_service = MemoryService()
