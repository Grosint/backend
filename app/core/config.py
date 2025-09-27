from __future__ import annotations

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API configuration
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "GROSINT V2"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "development_secret_key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_PATH: Path = Path("logs")
    LOG_BACKUP_COUNT: int = 30  # Keep 30 days of logs

    # Demo auth credentials (for development only)
    TEST_USER: str = "test@example.com"
    TEST_PASSWORD: str = "password"

    # MongoDB configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "osint_backend")
    MONGODB_COLLECTION_USERS: str = "users"
    MONGODB_COLLECTION_SEARCHES: str = "searches"
    MONGODB_COLLECTION_RESULTS: str = "results"

    # External API configuration
    EXTERNAL_API_TIMEOUT: int = 30
    MAX_CONCURRENT_REQUESTS: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list | str):
            return v
        raise ValueError(v)

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env file


# Create settings instance
settings = Settings()
