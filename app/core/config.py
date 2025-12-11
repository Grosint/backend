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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes (short-lived)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days

    # Token blocklist configuration (using MongoDB)
    # No additional configuration needed - uses existing MongoDB connection

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
    MONGODB_COLLECTION_USERS: str = "user"
    MONGODB_COLLECTION_SEARCHES: str = "searches"
    MONGODB_COLLECTION_RESULTS: str = "results"

    # External API configuration
    EXTERNAL_API_TIMEOUT: int = 30
    MAX_CONCURRENT_REQUESTS: int = 10

    # Resilience configuration
    CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", 3))
    CB_RECOVERY_TIMEOUT_SECONDS: int = int(os.getenv("CB_RECOVERY_TIMEOUT_SECONDS", 60))
    CB_HALF_OPEN_PROBE_ATTEMPTS: int = int(os.getenv("CB_HALF_OPEN_PROBE_ATTEMPTS", 1))

    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", 3))
    RETRY_INITIAL_BACKOFF_SECONDS: float = float(
        os.getenv("RETRY_INITIAL_BACKOFF_SECONDS", 0.2)
    )
    RETRY_BACKOFF_MULTIPLIER: float = float(os.getenv("RETRY_BACKOFF_MULTIPLIER", 2.0))
    RETRY_JITTER_RATIO: float = float(os.getenv("RETRY_JITTER_RATIO", 0.2))

    # RAPIDAPI KEYS
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")

    # LeakCheck API configuration
    LEAK_CHECK_API_KEY: str = os.getenv("LEAK_CHECK_API_KEY", "")

    # HLR API configuration
    HLR_API_KEY: str = os.getenv("HLR_API_KEY", "")

    # AITAN Labs API configuration
    AITAN_API_KEY: str = os.getenv("AITAN_API_KEY", "")

    # Befisc API configuration (used by AITAN service)
    BEFISC_API_KEY: str = os.getenv("BEFISC_API_KEY", "")

    # Telegram configuration (supports multiple accounts)
    # Format: TELEGRAM_API_ID_1, TELEGRAM_API_HASH_1, TELEGRAM_AUTH_MOBILE_1, etc.
    TELEGRAM_API_ID_1: str = os.getenv("TELEGRAM_API_ID_1", "")
    TELEGRAM_API_HASH_1: str = os.getenv("TELEGRAM_API_HASH_1", "")
    TELEGRAM_AUTH_MOBILE_1: str = os.getenv("TELEGRAM_AUTH_MOBILE_1", "")
    TELEGRAM_API_ID_2: str = os.getenv("TELEGRAM_API_ID_2", "")
    TELEGRAM_API_HASH_2: str = os.getenv("TELEGRAM_API_HASH_2", "")
    TELEGRAM_AUTH_MOBILE_2: str = os.getenv("TELEGRAM_AUTH_MOBILE_2", "")
    TELEGRAM_API_ID_3: str = os.getenv("TELEGRAM_API_ID_3", "")
    TELEGRAM_API_HASH_3: str = os.getenv("TELEGRAM_API_HASH_3", "")
    TELEGRAM_AUTH_MOBILE_3: str = os.getenv("TELEGRAM_AUTH_MOBILE_3", "")
    TELEGRAM_MAX_ACCOUNTS: int = int(os.getenv("TELEGRAM_MAX_ACCOUNTS", "3"))

    # Skype configuration (supports multiple accounts)
    # Format: SKYPE_USER_1, SKYPE_PASSWORD_1, etc.
    SKYPE_USER_1: str = os.getenv("SKYPE_USER_1", "")
    SKYPE_PASSWORD_1: str = os.getenv("SKYPE_PASSWORD_1", "")
    SKYPE_USER_2: str = os.getenv("SKYPE_USER_2", "")
    SKYPE_PASSWORD_2: str = os.getenv("SKYPE_PASSWORD_2", "")
    SKYPE_USER_3: str = os.getenv("SKYPE_USER_3", "")
    SKYPE_PASSWORD_3: str = os.getenv("SKYPE_PASSWORD_3", "")
    SKYPE_MAX_ACCOUNTS: int = int(os.getenv("SKYPE_MAX_ACCOUNTS", "3"))

    # Cashfree Payment Gateway configuration
    CASHFREE_APP_ID: str = os.getenv("CASHFREE_APP_ID", "")
    CASHFREE_SECRET_KEY: str = os.getenv("CASHFREE_SECRET_KEY", "")
    CASHFREE_BASE_URL: str = os.getenv(
        "CASHFREE_BASE_URL", "https://api.cashfree.com/pg"
    )
    CASHFREE_WEBHOOK_SECRET: str = os.getenv("CASHFREE_WEBHOOK_SECRET", "")
    CASHFREE_API_VERSION: str = os.getenv("CASHFREE_API_VERSION", "2023-08-01")

    # Payment configuration
    GST_RATE: float = float(os.getenv("GST_RATE", "0.18"))  # 18% GST

    # Webhook security configuration
    # WARNING: Only enable in development/testing. Never enable in production.
    WEBHOOK_SIGNATURE_BYPASS: bool = (
        os.getenv("WEBHOOK_SIGNATURE_BYPASS", "false").lower() in ("true", "1", "yes")
        and os.getenv("ENVIRONMENT", "development").lower() != "production"
    )

    # Credit scheduler configuration
    CREDIT_EXPIRY_SCHEDULER_ENABLED: bool = os.getenv(
        "CREDIT_EXPIRY_SCHEDULER_ENABLED", "true"
    ).lower() in ("true", "1", "yes")
    CREDIT_EXPIRY_SCHEDULE_HOUR: int = int(
        os.getenv("CREDIT_EXPIRY_SCHEDULE_HOUR", "2")
    )
    CREDIT_EXPIRY_SCHEDULE_MINUTE: int = int(
        os.getenv("CREDIT_EXPIRY_SCHEDULE_MINUTE", "0")
    )

    # Azure Communication Services Email configuration
    AZURE_EMAIL_ENDPOINT: str = os.getenv("AZURE_EMAIL_ENDPOINT", "")
    AZURE_EMAIL_ACCESS_KEY: str = os.getenv("AZURE_EMAIL_ACCESS_KEY", "")
    AZURE_EMAIL_SENDER_ADDRESS: str = os.getenv("AZURE_EMAIL_SENDER_ADDRESS", "")

    # Frontend URL for email links (password reset, etc.)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://your-app.com")

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
