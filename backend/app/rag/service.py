"""PostgreSQL/pgvector retrieval with scoped metadata filtering."""
import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import DocumentChunk
from app.memory.embeddings import EmbeddingProvider, embedding_provider


class RAGService:
    def __init__(self, provider: EmbeddingProvider = embedding_provider):
        self._provider = provider

    async def ingest(self, db: AsyncSession, content: str, source: str, task_id: Optional[str] = None, user_id: str = "anonymous", workspace_id: str = "default"):
        if not content.strip():
            return None
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = await db.scalar(select(DocumentChunk).where(
            DocumentChunk.content_hash == content_hash,
            DocumentChunk.user_id == user_id,
            DocumentChunk.workspace_id == workspace_id,
        ).limit(1))
        if existing:
            return existing
        chunk = DocumentChunk(
            task_id=task_id,
            user_id=user_id,
            workspace_id=workspace_id,
            source=source,
            content=content,
            content_hash=content_hash,
            embedding=await self._provider.embed(content),
        )
        db.add(chunk)
        await db.flush()
        return chunk

    async def retrieve(
        self,
        db: AsyncSession,
        query_text: str,
        task_id: Optional[str] = None,
        top_k: Optional[int] = None,
        user_id: str = "anonymous",
        workspace_id: str = "default",
    ) -> list[DocumentChunk]:
        if not query_text.strip():
            return []
        embedding = await self._provider.embed(query_text)
        distance = DocumentChunk.embedding.cosine_distance(embedding)
        query = select(DocumentChunk).where(
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.user_id == user_id,
            DocumentChunk.workspace_id == workspace_id,
        )
        if task_id:
            query = query.where(DocumentChunk.task_id == task_id)
        return list((await db.execute(query.order_by(distance).limit(top_k or settings.RAG_TOP_K))).scalars())

    async def context(self, db: AsyncSession, query_text: str, task_id: Optional[str] = None, user_id: str = "anonymous", workspace_id: str = "default") -> str:
        chunks = await self.retrieve(db, query_text, task_id, user_id=user_id, workspace_id=workspace_id)
        return "\n\n".join(f"[Source: {chunk.source}]\n{chunk.content}" for chunk in chunks)


rag_service = RAGService()
