"""
FastAPI Application — main entry point.
"""
import structlog
from contextlib import asynccontextmanager
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, init_neo4j_schema
from app.core.events import event_bus
from app.api.tasks import router as tasks_router
from app.api.ws import router as ws_router

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

# CORS — allow Electron renderer and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tasks_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
