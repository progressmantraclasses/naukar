"""
Naukar — Autonomous AI Workforce Platform
Application Configuration
"""
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
    GROQ_COMPOUND_MODEL: str = "openai/gpt-oss-120b"
    GROQ_COMPOUND_MINI_MODEL: str = "groq/compound-mini"

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

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
