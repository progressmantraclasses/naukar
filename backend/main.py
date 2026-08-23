"""
FastAPI Application — main entry point.
"""
import structlog
import time
from contextlib import asynccontextmanager
from sqlalchemy import text
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, init_neo4j_schema
from app.core.events import event_bus
from app.api.tasks import router as tasks_router
from app.api.ws import router as ws_router
from app.core.observability import metrics

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    log.info("naukar_starting", version=settings.APP_VERSION)

    # Enable pgvector extension BEFORE creating tables
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        log.info("pgvector_extension_enabled")
    except Exception as e:
        log.warning("pgvector_extension_skipped", error=str(e))

    # Create all PostgreSQL tables (async-native)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS "
            "user_id VARCHAR(200) NOT NULL DEFAULT 'anonymous'"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id)"
        ))
        await conn.execute(text(
            "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS "
            "user_id VARCHAR(200) NOT NULL DEFAULT 'anonymous'"
        ))
        await conn.execute(text(
            "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS "
            "workspace_id VARCHAR(200) NOT NULL DEFAULT 'default'"
        ))
        await conn.execute(text(
            "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS "
            "content_hash VARCHAR(64) NOT NULL DEFAULT ''"
        ))
        for statement in (
            "ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS semantic_cache_hit BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS rag_used BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS search_used BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS tool_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'completed'",
        ):
            await conn.execute(text(statement))
    log.info("database_tables_created")

    # Connect event bus to Redis
    try:
        await event_bus.connect()
        log.info("event_bus_connected")
    except Exception as e:
        log.warning("event_bus_redis_unavailable", error=str(e))

    # Init Neo4j schema (non-fatal if AuraDB is unavailable)
    try:
        await init_neo4j_schema()
        log.info("neo4j_schema_initialized")
    except Exception as e:
        log.warning("neo4j_schema_init_skipped", error=str(e))

    log.info("naukar_ready")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    try:
        await event_bus.disconnect()
    except Exception:
        pass
    try:
        from app.core.database import close_neo4j
        await close_neo4j()
    except Exception:
        pass
    await engine.dispose()
    log.info("naukar_shutdown")


app = FastAPI(
    title="Naukar — Autonomous AI Workforce Platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    started = time.monotonic()
    metrics.increment("requests_total")
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            metrics.increment("request_errors_total")
        return response
    finally:
        metrics.observe("request_latency", (time.monotonic() - started) * 1000)

# CORS — allow Electron renderer and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tasks_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/metrics")
async def metrics_snapshot():
    return metrics.snapshot()
