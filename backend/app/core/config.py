"""Application configuration.

All settings are loaded from environment variables (or a local ``.env`` file)
via ``pydantic-settings``. Access settings through :func:`get_settings`, which is
cached so the environment is parsed only once per process.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    APP_NAME: str = "Agentic AI Newsletter Platform"
    APP_ENV: str = "local"  # local | staging | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # ------------------------------------------------------------------ #
    # PostgreSQL
    # ------------------------------------------------------------------ #
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ainewsletter"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"

    # Connection pool tuning
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False

    # ------------------------------------------------------------------ #
    # External providers (placeholders only - integrations are future work)
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    BEEHIIV_API_KEY: str | None = None
    LINKEDIN_CLIENT_ID: str | None = None
    LINKEDIN_CLIENT_SECRET: str | None = None
    NOTION_API_KEY: str | None = None

    # ------------------------------------------------------------------ #
    # Source collection
    # ------------------------------------------------------------------ #
    COLLECTION_TIMEOUT: float = 20.0  # seconds per HTTP request
    MAX_RETRIES: int = 3
    RSS_BATCH_SIZE: int = 25
    RESEARCH_BATCH_SIZE: int = 15
    NEWSLETTER_BATCH_SIZE: int = 15
    ENABLE_SCHEDULER: bool = True
    RESPECT_ROBOTS_TXT: bool = True

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #
    @property
    def DATABASE_URL(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()


settings = get_settings()
