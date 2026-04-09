"""
Application configuration settings.
Uses Pydantic Settings with environment variables.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "GlobalReporter API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql://ainewser:ainewser_pass@localhost:5432/ainewser"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Cache
    CACHE_TTL: int = 300  # 5 minutes

    # Background crawler (runs Scrapy in crawler-service via subprocess)
    CRAWLER_ENABLED: bool = True
    CRAWLER_INTERVAL_SECONDS: int = 3600
    CRAWLER_SPIDER: str = "bbc"
    API_BASE_URL: str = "http://127.0.0.1:8000"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
