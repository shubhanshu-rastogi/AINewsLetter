"""Application configuration.

All settings are loaded from environment variables (or a local ``.env`` file)
via ``pydantic-settings``. Access settings through :func:`get_settings`, which is
cached so the environment is parsed only once per process.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the active environment before building the model so the matching
# .env.<environment> file is layered on top of the base .env.
_RAW_ENV = os.environ.get("APP_ENV", "local").lower()
_ENVIRONMENT = {"local": "development", "dev": "development"}.get(_RAW_ENV, _RAW_ENV)


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        # Base .env first, environment-specific file overrides it.
        env_file=(".env", f".env.{_ENVIRONMENT}"),
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
    # Relevance / categorization
    # ------------------------------------------------------------------ #
    ENABLE_LLM_CLASSIFICATION: bool = False
    LLM_PROVIDER: str = "anthropic"  # anthropic | openai
    LLM_MODEL: str = "claude-haiku-4-5-20251001"

    # ------------------------------------------------------------------ #
    # Fact checking
    # ------------------------------------------------------------------ #
    FACT_CHECK_VERIFY_URLS: bool = True
    ENABLE_LLM_FACTCHECK: bool = False
    MAX_CLAIMS_PER_ARTICLE: int = 10

    # ------------------------------------------------------------------ #
    # Newsletter writer / brand
    # ------------------------------------------------------------------ #
    NEWSLETTER_NAME: str = "AI & Quality Engineering Weekly"
    NEWSLETTER_TAGLINE: str = (
        "Practical AI insights for QA Leaders, Test Managers, Engineering Leaders, and IT Professionals."
    )
    ENABLE_LLM_WRITER: bool = False
    MIN_CONFIDENCE_FOR_PUBLISH: float = 90.0

    # ------------------------------------------------------------------ #
    # Visual generation
    # ------------------------------------------------------------------ #
    VISUAL_STORAGE_ROOT: str = "storage"
    VISUAL_BASE_URL: str = "/static"  # served root; asset rel paths begin with "visuals/"
    ENABLE_AI_IMAGES: bool = False  # off -> programmatic cover (no external image API)
    AI_IMAGE_MODEL: str = "gpt-image-1"

    # ------------------------------------------------------------------ #
    # Human review / feedback
    # ------------------------------------------------------------------ #
    NOTION_REVIEW_DATABASE_ID: str | None = None
    ENABLE_LLM_FEEDBACK: bool = False
    REVIEW_AUTH_TOKEN: str | None = None  # set to require a bearer token on review APIs

    # ------------------------------------------------------------------ #
    # Publishing
    # ------------------------------------------------------------------ #
    ENABLE_REAL_PUBLISHING: bool = False  # off -> simulated publish (no external calls)
    BEEHIIV_PUBLICATION_ID: str | None = None
    LINKEDIN_AUTHOR_URN: str | None = None
    NEWSLETTER_SUBSCRIBE_URL: str = "https://aiqeweekly.example.com/subscribe"
    MAX_PUBLISH_RETRIES: int = 3
    PUBLISH_RETRY_BASE_DELAY: float = 1.0

    # ------------------------------------------------------------------ #
    # Platform / operations
    # ------------------------------------------------------------------ #
    SERVICE_NAME: str = "ainewsletter-api"
    SECRET_KEY: str | None = None  # required in production
    DATABASE_URL_OVERRIDE: str | None = None  # explicit DSN (else derived from POSTGRES_*)

    # Redis (optional in development)
    REDIS_URL: str | None = None  # e.g. redis://localhost:6379/0
    ENABLE_REDIS: bool = False

    # Observability
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

    # Security / HTTP hardening
    CORS_ORIGINS: str = "*"  # comma-separated
    MAX_REQUEST_BYTES: int = 2_000_000  # 2 MB request body cap
    ENABLE_SECURITY_HEADERS: bool = True

    # Rate limiting (token bucket per client+route-group)
    ENABLE_RATE_LIMIT: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_BURST: int = 30

    # Idempotency
    ENABLE_IDEMPOTENCY: bool = True
    IDEMPOTENCY_TTL_SECONDS: int = 86_400

    # Database hardening
    DB_STATEMENT_TIMEOUT_MS: int = 30_000
    DB_SLOW_QUERY_MS: float = 500.0

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #
    @property
    def environment(self) -> str:
        """Normalized environment name (development|test|staging|production)."""
        env = self.APP_ENV.lower()
        return {"local": "development", "dev": "development"}.get(env, env)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate_for_environment(self) -> list[str]:
        """Return a list of missing required settings for the current environment.

        Empty list = valid. Used to fail startup fast in production.
        """
        missing: list[str] = []
        if self.environment in ("staging", "production"):
            if not self.SECRET_KEY:
                missing.append("SECRET_KEY")
            if self.POSTGRES_PASSWORD in ("", "postgres"):
                missing.append("POSTGRES_PASSWORD (insecure default)")
        if self.environment == "production":
            if self.ENABLE_REAL_PUBLISHING and not self.BEEHIIV_API_KEY:
                missing.append("BEEHIIV_API_KEY (real publishing enabled)")
            if self.CORS_ORIGINS == "*":
                missing.append("CORS_ORIGINS (wildcard not allowed in production)")
            if self.ENABLE_REDIS and not self.REDIS_URL:
                missing.append("REDIS_URL (Redis enabled)")
        return missing

    @property
    def DATABASE_URL(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver)."""
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing for the environment."""


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance, validated for the environment.

    Fails fast (raises :class:`ConfigurationError`) if required production/staging
    settings are missing, so the application never starts misconfigured.
    """
    instance = Settings()
    missing = instance.validate_for_environment()
    if missing:
        raise ConfigurationError(
            f"Missing required configuration for environment '{instance.environment}': {', '.join(missing)}"
        )
    return instance


settings = get_settings()
