import json
import logging
import os
import re
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings


class UTCFormatter(logging.Formatter):
    """Custom formatter that forces UTC time"""

    def formatTime(self, record, datefmt=None):
        # Convert to UTC timezone
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime("%Y-%m-%d %H:%M:%S")


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add client IP if available
        if hasattr(record, "client_ip"):
            log_entry["client_ip"] = record.client_ip

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
                "client_ip",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False)


class ClientIPFilter(logging.Filter):
    """Custom filter to add client IP to log records"""

    def filter(self, record):
        # Try to get client IP from various sources
        client_ip = "unknown"

        # Check if request object is available in the record
        if hasattr(record, "request") and hasattr(record.request, "client"):
            client_ip = record.request.client.host
        elif hasattr(record, "client_ip"):
            client_ip = record.client_ip

        record.client_ip = client_ip
        return True


def setup_logging():
    """Setup application logging with daily file rotation and console output"""
    # Ensure log directory exists
    os.makedirs(settings.LOG_PATH, exist_ok=True)

    # Create daily log file with date in filename
    current_date = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = settings.LOG_PATH / f"app-{current_date}.log"

    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper())

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Choose formatter based on environment
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        # Use JSON formatter for production (better for log aggregation)
        file_formatter = JSONFormatter()
        console_formatter = UTCFormatter(
            "%(asctime)s UTC - [%(client_ip)s] - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Use human-readable formatter for development
        utc_formatter = UTCFormatter(
            "%(asctime)s UTC - [%(client_ip)s] - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_formatter = utc_formatter
        console_formatter = utc_formatter

    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
        utc=True,  # Use UTC for rotation timing
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    file_handler.addFilter(ClientIPFilter())
    logger.addHandler(file_handler)

    # Console handler for development
    if environment == "development":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        console_handler.addFilter(ClientIPFilter())
        logger.addHandler(console_handler)

    # Reduce verbosity of some loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Reduce MongoDB/PyMongo verbosity
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.pool").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)

    logging.info("Logging configured successfully")


def sanitize_log_data(data):
    """
    Sanitize sensitive data for logging

    Args:
        data: Data to sanitize

    Returns:
        dict: Sanitized data
    """
    if not isinstance(data, dict):
        return data

    # Create a copy to avoid modifying the original
    sanitized = data.copy()

    # Patterns to match sensitive data
    email_pattern = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    token_pattern = re.compile(
        r"(Bearer\s+[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+)"
    )

    # Keys that might contain sensitive data
    sensitive_keys = [
        "password",
        "token",
        "secret",
        "key",
        "auth",
        "credential",
        "api_key",
    ]

    for key, value in sanitized.items():
        # Recursively sanitize nested dictionaries
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)

        # Mask sensitive values
        elif isinstance(value, str):
            # Check if key contains sensitive words
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "********"

            # Mask emails
            elif email_pattern.search(value):
                sanitized[key] = email_pattern.sub("***@***.***", value)

            # Mask tokens
            elif token_pattern.search(value):
                sanitized[key] = token_pattern.sub("Bearer ********", value)

    return sanitized
