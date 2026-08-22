"""
Database connections — PostgreSQL (async SQLAlchemy) + Neo4j AuraDB
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from neo4j import AsyncGraphDatabase
from app.core.config import settings
import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# PostgreSQL / pgvector
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Neo4j AuraDB
# ---------------------------------------------------------------------------
_neo4j_driver = None


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _neo4j_driver


async def close_neo4j():
    global _neo4j_driver
    if _neo4j_driver:
        await _neo4j_driver.close()
        _neo4j_driver = None


async def init_neo4j_schema():
    """Create Neo4j indexes and constraints on startup."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.task_id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (e:Employee) REQUIRE e.employee_id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT step_id IF NOT EXISTS FOR (s:TaskStep) REQUIRE s.step_id IS UNIQUE"
        )
    log.info("neo4j_schema_initialized")
