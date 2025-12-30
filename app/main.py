import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

# Load .env file into environment before importing settings
# This must happen before settings import to ensure ENV vars are loaded
load_dotenv()

# noqa: E402 - Imports must come after load_dotenv() to ensure .env is loaded
from app.api.router import api_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.credit_scheduler import credit_scheduler  # noqa: E402
from app.core.database import close_mongo_connection, connect_to_mongo  # noqa: E402
from app.core.error_handlers import (  # noqa: E402
    base_api_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import BaseAPIException  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.core.security import RateLimitMiddleware, add_security_headers  # noqa: E402
from app.services.email_service import email_service  # noqa: E402


# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger = logging.getLogger(__name__)

    # Validate ENCRYPTION_KEY is present - fail startup if missing
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    if not encryption_key:
        # Check if .env file exists for better error message
        env_file = Path(".env")
        env_file_exists = env_file.exists()

        error_msg = (
            "❌ APPLICATION STARTUP FAILED: ENCRYPTION_KEY environment variable is required.\n"
            f"  - .env file exists: {env_file_exists}\n"
            f"  - .env file path: {env_file.absolute()}\n"
            "  - Generate a key with: openssl rand -base64 32\n"
            "  - Add it to your .env file: ENCRYPTION_KEY=<your-generated-key>\n"
            "  - Ensure .env file is in the project root directory"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    logger.info("✅ ENCRYPTION_KEY validated")

    await connect_to_mongo()

    # Validate email service configuration
    if email_service.client is None:
        logger.error(
            "⚠️  EMAIL SERVICE NOT CONFIGURED - User registration will fail! "
            "Please set the following environment variables in production: "
            "AZURE_EMAIL_ENDPOINT, AZURE_EMAIL_ACCESS_KEY, AZURE_EMAIL_SENDER_ADDRESS. "
            "See AZURE_EMAIL_SETUP.md for configuration instructions."
        )
    else:
        logger.info("✅ Email service initialized successfully")

    # Start credit scheduler
    credit_scheduler.start()

    logger.info("OSINT Backend API started")
    yield
    # Shutdown
    credit_scheduler.shutdown()
    await close_mongo_connection()
    logger.info("OSINT Backend API shutting down")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="OSINT Backend API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add security headers middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=add_security_headers)


# Request timing middleware
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


# Client IP logging middleware
class ClientIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Store client IP in request state for logging
        client_ip = request.client.host if request.client else "unknown"
        request.state.client_ip = client_ip

        # Add client IP to logging context
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.client_ip = client_ip
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            response = await call_next(request)
            return response
        finally:
            # Restore original factory
            logging.setLogRecordFactory(old_factory)


app.add_middleware(ClientIPMiddleware)
app.add_middleware(TimingMiddleware)

# Include API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted at /static from {static_dir}")

# Add Prometheus metrics instrumentation
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, endpoint="/metrics")


# Health check endpoint
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint for deployment verification"""
    try:
        # Add MongoDB connection check if needed
        return {
            "status": "healthy",
            "service": "grosint-backend",
            "version": "1.0.0",
            "python_version": "3.12.7",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Service unhealthy: {str(e)}"
        ) from e


# Register exception handlers
app.add_exception_handler(BaseAPIException, base_api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
