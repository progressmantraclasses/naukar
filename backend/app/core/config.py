"""
Naukar — Autonomous AI Workforce Platform
Application Configuration
"""
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Naukar"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://naukar:naukar_secret@localhost:5432/naukar_db"
    DATABASE_SYNC_URL: str = "postgresql://naukar:naukar_secret@localhost:5432/naukar_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Neo4j AuraDB
    NEO4J_URI: str = "neo4j+s://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # LLM
    GROQ_API_KEY: str = ""

    # Model names (Groq)
    GROQ_COMPOUND_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_COMPOUND_MINI_MODEL: str = "llama-3.1-8b-instant"

    # Available models for routing
    MODEL_FAST: str = "groq/compound-mini"
    MODEL_SMART: str = "groq/compound"
    MODEL_HEAVY: str = "groq/compound"

    # Task limits
    MAX_TASK_COST_USD: float = 5.0
    DEFAULT_QUALITY_THRESHOLD: float = 0.80
    MAX_RETRY_ATTEMPTS: int = 3
    MAX_EMPLOYEES_PER_TASK: int = 12
    GROQ_MAX_OUTPUT_TOKENS: int = 1800
    CHEAP_MAX_OUTPUT_TOKENS: int = 900
    STANDARD_MAX_OUTPUT_TOKENS: int = 1800
    REASONING_MAX_OUTPUT_TOKENS: int = 2600
    LLM_CACHE_TTL_SECONDS: int = 86400
    MONTHLY_USER_BUDGET_USD: float = 10.0
    SEMANTIC_CACHE_THRESHOLD: float = 0.92
    LLM_CONTEXT_TOKENS: int = 6000
    RAG_TOP_K: int = 5
    TAVILY_API_KEY: str = ""
    SEARCH_MAX_RESULTS: int = 5
    SEARCH_TIMEOUT_SECONDS: int = 20
    SEARCH_CACHE_TTL_SECONDS: int = 3600
    LLM_REQUESTS_PER_MINUTE: int = 60
    TOOL_WORKSPACE_ROOT: str = "."
    MAX_STEPS: int = 12
    MAX_TOOL_CALLS: int = 20
    MAX_REPEAT_ACTIONS: int = 2
    MAX_RUNTIME_SECONDS: int = 900
    TASK_QUEUE_MODE: str = "background"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    MODEL_PRICING_JSON: str = '{"groq/compound-mini":{"input":0.075,"output":0.30,"cached_input":0.0},"openai/gpt-oss-120b":{"input":0.15,"output":0.60,"cached_input":0.0}}'

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    # ── Authentication & JWT ────────────────────────────────────────────────
    AUTH_REQUIRED: bool = True
    # A strong random secret; override in .env for production
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # Legacy single-token auth (kept for backward compat, unused when AUTH_REQUIRED=True)
    AUTH_TOKEN: str = ""
    AUTH_DEFAULT_USER_ID: str = "anonymous"
    AUTH_DEFAULT_WORKSPACE_ID: str = "default"

    # ── Rate Limiting ───────────────────────────────────────────────────────
    RATE_LIMIT_TASKS_PER_MINUTE: int = 10
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_API_PER_MINUTE: int = 120


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

