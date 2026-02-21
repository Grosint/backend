# GROSINT Backend – Technical Specification

**Version:** 1.0
**Last Updated:** February 2025
**Purpose:** Complete technical specification for developers and LLMs to understand the project architecture, tools, flows, and standards.

---

## Table of Contents

1. [Part A: Human-Readable Specification](#part-a-human-readable-technical-specification)
   - [Project Overview](#1-project-overview)
   - [Architecture & Request Flow](#2-architecture--request-flow)
   - [Core Tool Usage Matrix](#3-core-tool-usage-matrix)
   - [Asynchrony & Parallelism](#4-asynchrony--parallelism)
   - [Database Layer](#5-database-layer)
   - [API Structure](#6-api-structure)
   - [Authentication Flow](#7-authentication-flow)
   - [Exception Handling](#8-exception-handling)
   - [Resilience Patterns](#9-resilience-patterns)
   - [Secondary Tools (Dev/Quality)](#10-secondary-tools-devquality)
   - [Logging](#11-logging)
   - [Monitoring & Metrics](#12-monitoring--metrics)
   - [Configuration](#13-configuration)
   - [Services & Adapters](#14-services--adapters)
   - [Excluded External Packages](#15-excluded-external-packages)
2. [Part B: LLM-Optimized Reference](#part-b-llm-optimized-technical-reference)

---

# Part A: Human-Readable Technical Specification

## 1. Project Overview

**GROSINT Backend** is a Python-based OSINT (Open Source Intelligence) API built with FastAPI. It provides multi-type search capabilities (email, phone, domain, vehicle, IP, bank account, IMEI, virtual number/email, verify ID), user management with JWT authentication, billing (plans, subscriptions, credits), optional link tracking ("Seeker"), and payment integration (Cashfree).

### Run Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Key Features

- **Search Types:** Email, Domain, Phone, Vehicle (RC/FastTag/Chassis), IP Lookup, IMEI, Virtual Number, Virtual Email, Bank Account, Verify ID, Username
- **User Management:** Signup, login, OTP verification, organization support, role-based access (admin, org_admin, user, org_user)
- **Billing:** Plans, subscriptions, credits, credit expiry (scheduled), Cashfree payments
- **Seeker:** Link tracking with geolocation, device info, short URLs, anonymization
- **Security:** JWT access/refresh tokens, token blocklist, rate limiting, PII masking in logs

---

## 2. Architecture & Request Flow

### Startup Sequence

```
1. load_dotenv(.env) – from project root
2. Validate ENCRYPTION_KEY – fail startup if missing
3. Validate MONGODB_URL – fail startup if missing
4. connect_to_mongo() – Motor AsyncIOMotorClient
5. migrate_user_indexes() – drop legacy unique indexes if needed
6. init_beanie() – register all document models
7. initialize_collection_indexes() – TTL for email_otps
8. Validate Azure email service config (log warning if missing)
9. credit_scheduler.start() – APScheduler
10. Log "OSINT Backend API started"
```

### Request Flow (Inbound)

```
Client → CORS Middleware → RateLimitMiddleware → add_security_headers
      → ClientIPMiddleware → TimingMiddleware → Router
      → Auth Dependency (if protected) → Endpoint → Service/Orchestrator
      → Beanie/MongoDB or ResilientHttpClient → Response
```

### Shutdown Sequence

```
1. credit_scheduler.shutdown()
2. close_mongo_connection()
3. Log shutdown
```

### Middleware Order (outermost first)

| Order | Middleware | Purpose |
|-------|------------|---------|
| 1 | CORS | Allow configured origins |
| 2 | RateLimitMiddleware | Per-IP rate limiting (default 60/min) |
| 3 | add_security_headers | Security headers (X-Content-Type-Options, etc.) |
| 4 | ClientIPMiddleware | Store client IP in request.state, set logging context |
| 5 | TimingMiddleware | Add X-Process-Time header |

---

## 3. Core Tool Usage Matrix

| Tool | File(s) | Usage |
|------|---------|-------|
| **Beanie** | `database.py`, `models/*.py` (user, history, search, result, plan, payment, subscription, credit, credit_txn, organization, seeker), `search.py`, `history.py`, `seeker_service.py`, `api/endpoints/*.py` | `init_beanie`, `Document`, `Indexed`, `Insert`, `Replace`, `Update`, `before_event`, `PydanticObjectId`, `find_one`, `find`, `insert_one`, `update_one` |
| **PyMongo** | `database.py`, `infrastructure/blocklist.py`, `infrastructure/email_otp.py`, `models/user.py`, `models/seeker.py`, `seeker_service.py` | `pymongo.ASCENDING`, `pymongo.errors.ConnectionFailure`, `pymongo.errors.DuplicateKeyError`, `IndexModel`, `collection.create_index`, `insert_one`, `find_one`, `delete_one` |
| **Motor** | `database.py` | `AsyncIOMotorClient` – async MongoDB driver (from `motor.motor_asyncio`) |
| **Pydantic** | `config.py`, `schemas/*.py`, `models/*.py`, `utils/validators.py` | `BaseModel`, `BaseSettings`, `Field`, `field_validator`, `field_serializer`, `ConfigDict`, `pydantic_settings.BaseSettings` |
| **PyJWT** | `core/security.py`, `utils/jwt.py` | `jwt.encode`, `jwt.decode`, `PyJWTError` – access/refresh token creation and verification with issuer/audience checks |
| **passlib (bcrypt)** | `core/security.py` | `CryptContext`, `verify_password`, `get_password_hash` – password hashing and verification |
| **cryptography** | `utils/encryption.py`, `models/history.py` | `AESGCM`, `PBKDF2HMAC` – encrypt/decrypt `History.results` and `flattenedResults` at rest |

### Beanie Document Models

| Model | Collection | Key Fields |
|-------|------------|------------|
| User | users | email, phone, password, userType, features, isVerified, isEmailOtpVerified |
| Organization | orgs | orgName, orgAdminId |
| History | history | userId, queryType, queryInput, results (encrypted), flattenedResults (encrypted), metadata |
| Search | searches | user_id, search_type, status, query |
| Result | results | search_id, source, data |
| Plan | plans | name, credits, price |
| Payment | payments | order_id, user_id, amount, status |
| Subscription | subscriptions | user_id, plan_id, status |
| Credit | credits | user_id, amount, expiry, status |
| CreditTxn | credit_txn | user_id, amount, type |
| SeekerLink | seeker_links | short_code, template |
| SeekerResult | seeker_results | link_id, ip, device info |

---

## 4. Asynchrony & Parallelism

### Async Pattern

- **FastAPI endpoints:** All use `async def`
- **Database:** Motor (async) + Beanie (async)
- **HTTP client:** `httpx.AsyncClient` wrapped by `ResilientHttpClient`

### Parallel Execution (`asyncio.gather`)

Used to run multiple external lookups or adapter calls concurrently:

| Location | Purpose |
|----------|---------|
| `search_orchestrator.py` | Parallel adapter execution for search types |
| `phone_lookup_orchestrator.py` | Parallel phone lookups (Skype, etc.) |
| `email_lookup_orchestrator.py` | Parallel email lookups |
| `lightweight_orchestrator.py` | Parallel simple lookups |
| `befisc_service.py`, `aitan/phone.py`, `aitan/vehicle.py` | Parallel API calls within adapters |
| `social_media_adapter.py`, `security_adapter.py`, `domain_adapter.py` | Parallel sub-lookups |
| `admin/phone_lookup.py`, `admin/email_lookup.py`, `admin/befisc_service.py` | Admin parallel lookups |
| `ignorant_service.py`, `ghunt_service.py` | Internal parallel tasks |

**Pattern:** `results = await asyncio.gather(*tasks, return_exceptions=True)` – exceptions are captured, not raised.

### Timeouts (`asyncio.wait_for`)

- **`telegram_service.py`:** `asyncio.wait_for(client.connect(), timeout=...)` and similar for operations – prevents indefinite blocking on Telegram API.

### Concurrency Limiting (`asyncio.Semaphore`)

- **`resilience.py` – ConcurrencyLimiter:** `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` – default 10 concurrent external HTTP requests.
- Used by `ResilientHttpClient` to avoid overwhelming external APIs.

### Background Tasks

- **APScheduler** (`credit_scheduler.py`): `AsyncIOScheduler` with a cron job at **02:00 UTC** to expire credits (`expire_credits_task`).
- Started in lifespan, stopped on shutdown.

---

## 5. Database Layer

### Database Access Rules

| Layer | Tool | Collections | Rule |
|-------|------|-------------|------|
| Domain entities | Beanie ODM | `users`, `organizations`, `histories`, `searches`, `results`, `plans`, `payments`, `subscriptions`, `credits`, `credit_transactions`, `seeker_links`, `seeker_results` | Use Beanie models only. No raw PyMongo. |
| Infrastructure | PyMongo (raw) | `blocked_tokens`, `email_otps` | Use raw driver only. No Beanie models. |

**Rule:** Never use `database.users.find_one()` etc. for Beanie collections. Never add Beanie models for `blocked_tokens`/`email_otps` without explicit justification. Constants: `BEANIE_COLLECTIONS`, `INFRA_COLLECTIONS` in `app/core/database.py`.

### Beanie-Managed Collections

- `users`, `organizations`, `histories`, `searches`, `results`, `plans`, `payments`, `subscriptions`, `credits`, `credit_transactions`, `seeker_links`, `seeker_results`

### Raw PyMongo Collections (Infrastructure)

| Collection | Purpose | Module | Indexes |
|------------|---------|--------|---------|
| `email_otps` | OTP storage for email verification | `app/infrastructure/email_otp.py` | TTL on `expires_at` |
| `blocked_tokens` | JWT blocklist for logout | `app/infrastructure/blocklist.py` | TTL on `expires_at`, unique on `jti` |

### Encryption

- `History.results` and `History.flattenedResults` are encrypted at rest via `@before_event` hooks and `get_encryption()`.
- Requires `ENCRYPTION_KEY` at startup.

---

## 6. API Structure

### Framework

- **FastAPI** with prefix `/api` (`settings.API_V1_STR`)

### Routers

| Prefix | Tags | Module |
|--------|------|--------|
| `/api/auth` | Authentication | auth.py |
| `/api/user` | User | user.py |
| `/api/history` | History | history.py |
| `/api/search` | Search | search.py |
| `/api/admin/debug` | Admin Debug | admin/ |
| `/api/plans` | Plans | plan.py |
| `/api/payments` | Payments | payment.py |
| `/api/subscriptions` | Subscriptions | subscription.py |
| `/api/credits` | Credits | credit.py |
| `/api/seeker` | Seeker | seeker.py |

### Non-API Routes

| Route | Purpose |
|-------|---------|
| `/` | Basic connectivity |
| `/api/health` | Health check |
| `/metrics` | Prometheus metrics |
| `/l/{short_code}` | Short URL redirect to seeker page |
| `/seeker/{link_id}/{template}` | Seeker tracking page (HTML) |
| `/static` | Static files |

### Response Schemas

- `SuccessResponse[T]` – success with data
- `ErrorResponse` – error with `error_code`, `details`
- `ValidationErrorResponse` – validation failures with field-level details
- `PaginatedResponse[T]` – with `PaginationMeta`

---

## 7. Authentication Flow

### JWT

- **Access token:** 15 min, HS256, claims: `sub`, `email`, `type`, `jti`, `iss`, `aud`, `iat`, `exp`, `nbf`
- **Refresh token:** 7 days
- **Libraries:** `app/utils/jwt.py` (JWTManager) and `app/core/security.py`

### Flow

1. **Login** (`POST /api/auth/login`): Credentials → `AuthService.login()` → bcrypt verify → `JWTManager.create_access_token` / `create_refresh_token` → return tokens
2. **Refresh** (`POST /api/auth/refresh`): Refresh token → `verify_refresh_token` → new access token
3. **Logout** (`POST /api/auth/logout`): JTI → `add_token_to_blocklist` (MongoDB `blocked_tokens`) → token invalidated
4. **Protected routes:** `Depends(get_current_user_token)` or `Depends(get_current_user)` – blocklist check + `verify_access_token` → `TokenData` or `User`

### Auth Dependencies

| Dependency | Purpose |
|------------|---------|
| `get_authorization_header` | Extract Bearer token |
| `get_current_user_token` | Blocklist + verify → `TokenData` |
| `get_current_user` | `TokenData` → load `User` from DB |
| `require_admin` | `UserType.ADMIN` |
| `require_org_admin` | `UserType.ORG_ADMIN` |
| `require_user_type(*types)` | Role-based factory |
| `require_feature(feature)` | Feature flag (e.g. "mobile360") |

---

## 8. Exception Handling

### Custom Exceptions (`app/core/exceptions.py`)

| Exception | Error Code | Status |
|-----------|------------|--------|
| BaseAPIException | (custom) | (custom) |
| ValidationException | VALIDATION_ERROR | 422 |
| NotFoundException | NOT_FOUND | 404 |
| ConflictException | CONFLICT | 409 |
| AuthenticationException | AUTHENTICATION_ERROR | 401 |
| UnauthorizedException | UNAUTHORIZED | 401 |
| AuthorizationException | AUTHORIZATION_ERROR | 403 |
| BusinessLogicException | BUSINESS_LOGIC_ERROR | 400 |
| DatabaseException | DATABASE_ERROR | 500 |
| ExternalServiceException | EXTERNAL_SERVICE_ERROR | 502 |

### Global Handlers

- `BaseAPIException` → `base_api_exception_handler` → `ErrorResponse`
- `RequestValidationError` → `validation_exception_handler` → `ValidationErrorResponse`
- `HTTPException` → `http_exception_handler` → `ErrorResponse`
- `Exception` → `general_exception_handler` → 500 with generic message

---

## 9. Resilience Patterns

### Rate Limiting (Incoming Requests)

**Purpose:** Limit how many requests clients can send to your API (protect your backend from abuse).

| Type | Location | Scope | Config | Notes |
|------|----------|-------|--------|-------|
| **Global** | `core/security.py` – `RateLimitMiddleware` | All incoming requests, per-IP | `RATE_LIMIT_PER_MINUTE` (default 60) | Sliding 60s window, in-memory store; returns HTTP 429 when exceeded; adds `X-RateLimit-Limit`, `X-RateLimit-Remaining` headers |
| **Seeker public** | `api/endpoints/seeker.py` – `_check_seeker_rate_limit()` | Public seeker endpoints (info/result) only | `SEEKER_PUBLIC_RATE_LIMIT_PER_MINUTE` (default 20) | Lower limit for unauthenticated public endpoints |

**Production note:** In-memory store; use Redis or similar for distributed deployments.

### Circuit Breaker (`resilience.py`)

**Purpose:** Protect your backend when external APIs fail – stops making requests to failing external services to avoid cascading failures.

- **Direction:** Outgoing (your backend → external APIs), not incoming.
- **Scope:** Per key (e.g. `circuit_key="truecaller_api"`, `"cashfree_api"`) or host extracted from URL.
- **States:** closed, open, half-open
- **Config:** `CB_FAILURE_THRESHOLD`, `CB_RECOVERY_TIMEOUT_SECONDS`, `CB_HALF_OPEN_PROBE_ATTEMPTS`
- **Used by:** `ResilientHttpClient` – all external HTTP calls via adapters (phone lookup, payment, etc.)

### Retry Policy (`resilience.py`)

- **Config:** `RETRY_MAX_ATTEMPTS`, `RETRY_INITIAL_BACKOFF_SECONDS`, `RETRY_BACKOFF_MULTIPLIER`, `RETRY_JITTER_RATIO`
- **Retry on:** 408, 425, 429, 5xx; `httpx.ReadTimeout`, `httpx.ConnectTimeout`, `RemoteProtocolError`, `NetworkError`
- **Backoff:** Exponential with jitter

### Concurrency Limiter (`resilience.py`)

- `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` – default 10

### ResilientHttpClient

- Wraps `httpx.AsyncClient` with retry, circuit breaker, and concurrency limiting.
- Used by adapters for external HTTP calls.

---

## 10. Secondary Tools (Dev/Quality)

| Tool | Purpose | Config |
|------|---------|--------|
| **Black** | Code formatting | `pyproject.toml` – line-length 88, target py312, exclude app/externals |
| **Ruff** | Linting, import sort | `pyproject.toml`, `ruff.toml` – rules E/W/F/I/B/C4/UP/SIM/ARG/TCH/Q/S/TID/PIE/PT/RET/A/COM/C90/ICN/PTH/ERA/PD/PGH/PL/TRY/FLY/NPY/PERF/FURB/RUF |
| **MyPy** | Type checking | `pyproject.toml` – Python 3.12, relaxed, ignore pymongo/motor/bson |
| **Bandit** | Security linting | Pre-commit – exclude tests, app/externals, skip B101 |
| **pytest** | Testing | `tests/` |
| **pytest-asyncio** | Async tests | Required for async fixtures/tests |
| **pytest-cov** | Coverage | Coverage reporting |
| **pytest-mock** | Mocking | Mock support |
| **pre-commit** | Git hooks | `.pre-commit-config.yaml` – black, ruff, bandit, pre-commit-hooks |
| **Safety** | Vulnerability scan | requirements-dev.txt, run manually |
| **Coverage** | Coverage | pytest-cov |
| **Faker** | Test data | Test fixtures |

### Pre-commit Hooks

- black, ruff (with ruff.toml)
- bandit (exclude tests, app/externals)
- pre-commit-hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files, check-merge-conflict, debug-statements, check-docstring-first, requirements-txt-fixer

---

## 11. Logging

### Setup (`app/core/logging.py`)

- **Call:** `setup_logging()` in `main.py` during app init
- **Handlers:** Timed rotating file (daily, UTC), console in development
- **Formatters:**
  - Development: UTC datetime, `client_ip`, logger, level, message
  - Production: `JSONFormatter` – structured JSON for log aggregation

### Filters

- `ClientIPFilter` – adds `client_ip` to log records

### PII Protection

| Function | Purpose |
|----------|---------|
| `sanitize_log_data()` | Masks passwords, tokens, emails, Bearer tokens in dicts |
| `mask_phone_number()` | Masks phone numbers, keeps last N digits |
| `hash_identifier()` | SHA256 prefix for identifiers (deterministic, non-reversible) |

### Reduced Verbosity

- `uvicorn`, `uvicorn.access` → WARNING
- `pymongo`, `pymongo.topology`, `pymongo.connection`, `pymongo.pool`, `pymongo.serverSelection` → WARNING

### Usage Pattern

```python
logger = logging.getLogger(__name__)
logger.info("message", extra={"key": value})
```

---

## 12. Monitoring & Metrics

### Built-in

- **Prometheus:** `prometheus-fastapi-instrumentator` exposes `/metrics` – HTTP request metrics, response times, error counts

### External Stack (see `monitoring/MONITORING_GUIDE.md`)

| Tool | Port | Purpose |
|------|------|---------|
| Grafana | 3000 | Visualization, dashboards |
| Prometheus | 9090 | Metrics DB |
| Loki | 3100 | Log aggregation |
| Promtail | 9080 | Log shipper |
| Node Exporter | 9100 | System metrics |
| Nginx Exporter | 9113 | Nginx metrics |

---

## 13. Configuration

### Mechanism

- `pydantic_settings.BaseSettings` in `app/core/config.py`
- Source: `.env` at project root (explicit path for systemd)

### Required at Startup

| Variable | Purpose |
|----------|---------|
| ENCRYPTION_KEY | History encryption – fail if missing |
| MONGODB_URL | MongoDB connection – fail if missing |

### Key Environment Variables

| Category | Variables |
|----------|-----------|
| API | API_V1_STR, PROJECT_NAME, ENVIRONMENT, DEBUG, CORS_ORIGINS |
| Auth | SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS |
| DB | MONGODB_DATABASE |
| Resilience | CB_*, RETRY_*, MAX_CONCURRENT_REQUESTS, EXTERNAL_API_TIMEOUT |
| Rate limiting | RATE_LIMIT_PER_MINUTE, SEEKER_PUBLIC_RATE_LIMIT_PER_MINUTE |
| Logging | LOG_LEVEL, LOG_PATH, LOG_BACKUP_COUNT |
| Email | AZURE_EMAIL_*, FRONTEND_URL |
| Payments | CASHFREE_*, GST_RATE, WEBHOOK_SIGNATURE_BYPASS |
| Scheduler | CREDIT_EXPIRY_SCHEDULER_ENABLED, CREDIT_EXPIRY_SCHEDULE_HOUR, CREDIT_EXPIRY_SCHEDULE_MINUTE |
| Seeker | SEEKER_ENABLED, SEEKER_*, TINYURL_API_KEY |
| External APIs | RAPIDAPI_KEY, VPNAPI_IO_API_KEY, AITAN_API_KEY, BEFISC_API_KEY, TELEGRAM_*, SKYPE_*, etc. |

---

## 14. Services & Adapters

**Orchestrators** (`app/services/orchestrators/`): Coordinate multiple adapters for complex searches.

| Orchestrator | Purpose |
|--------------|---------|
| SearchOrchestrator | Main search routing by SearchType to adapters |
| PhoneLookupOrchestrator | Phone lookups (Skype, Befisc, Ignorant, etc.) |
| EmailLookupOrchestrator | Email lookups (multiple sources) |
| LightweightOrchestrator | Simple lookups (1–3 APIs) |

**Adapters** (`app/adapters/`): Implement `OSINTAdapter` interface; each handles a specific lookup type.

| Adapter | Search Type(s) |
|---------|----------------|
| EmailAdapter | EMAIL |
| DomainAdapter | DOMAIN |
| PhoneLookupAdapter | PHONE |
| VehicleLookupAdapter | VEHICLE_RC, VEHICLE_FAST_TAG, VEHICLE_ALL, VEHICLE_CHASIS |
| IPLookupAdapter | IP_LOOKUP |
| IMEILookupAdapter | IMEI_LOOKUP |
| VirtualNumberAdapter | VIRTUAL_NUMBER |
| VirtualEmailAdapter | VIRTUAL_EMAIL |
| BankLookupAdapter | BANK_ACCOUNT |
| VerifyIdAdapter | VERIFY_ID |
| SocialMediaAdapter | EMAIL, DOMAIN (Twitter, LinkedIn, Facebook, Instagram) |
| SecurityAdapter | EMAIL, DOMAIN (security-focused lookups) |

---

## 15. Excluded External Packages

These packages are **not** part of core architecture – they are used by integrations only:

| Package | Used For |
|---------|----------|
| ghunt | Google email lookup |
| selenium | Browser automation (some lookups) |
| telethon | Telegram API |
| skpy | Skype API |
| ignorant | Phone number validation |

---

# Part B: LLM-Optimized Technical Reference

Dense, structured reference for LLM consumption.

## B1. Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, lifespan, middleware, routers
│   ├── api/router.py       # API router aggregation
│   ├── api/endpoints/      # auth, user, search, history, seeker, plan, payment, subscription, credit, admin
│   ├── core/               # config, database, security, auth_dependencies, logging, resilience,
│   │                       # credit_scheduler, error_handlers, exceptions
│   ├── infrastructure/     # raw PyMongo infra collections (blocklist, email_otp)
│   ├── models/             # Beanie documents
│   ├── schemas/            # Pydantic API schemas
│   ├── services/           # orchestrators, integrations
│   ├── adapters/           # lookup adapters
│   ├── utils/              # jwt, encryption, validators
│   └── externals/          # PhilINT, Holehe (third-party)
├── tests/
├── monitoring/
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── ruff.toml
└── .pre-commit-config.yaml
```

## B2. Core Tool Usage Matrix

| Tool | Files | Usage |
|------|-------|-------|
| Beanie | database.py, models/*, search.py, history.py, seeker_service.py, endpoints | init_beanie, Document, Indexed, Insert/Replace/Update, before_event, PydanticObjectId, find_one, find, insert_one |
| PyMongo | database.py, infrastructure/blocklist.py, infrastructure/email_otp.py, models/user.py, models/seeker.py, seeker_service.py | ASCENDING, ConnectionFailure, DuplicateKeyError, IndexModel, create_index, insert_one, find_one, delete_one |
| Motor | database.py | AsyncIOMotorClient |
| Pydantic | config.py, schemas/*, models/*, utils/validators.py | BaseModel, BaseSettings, Field, field_validator, field_serializer, ConfigDict |
| PyJWT | security.py, utils/jwt.py | jwt.encode, jwt.decode, PyJWTError |
| passlib (bcrypt) | security.py | CryptContext, verify_password, get_password_hash |
| cryptography | utils/encryption.py, models/history.py | AESGCM, PBKDF2HMAC for History encryption |

## B3. Async/Parallelism Locations

```
asyncio.gather: search_orchestrator, phone_lookup_orchestrator, email_lookup_orchestrator,
  lightweight_orchestrator, befisc_service, aitan/phone.py, aitan/vehicle.py,
  social_media_adapter, security_adapter, domain_adapter, admin/phone_lookup,
  admin/email_lookup, admin/befisc_service, ignorant_service, ghunt_service
asyncio.wait_for: telegram_service (connect, operations timeout)
asyncio.Semaphore: resilience.ConcurrencyLimiter
AsyncIOScheduler: credit_scheduler (CronTrigger 02:00 UTC)
```

## B4. Auth Flow

```
Login: credentials → verify_password (passlib/bcrypt) → JWTManager.create_access_token/create_refresh_token
Protected: Bearer → get_authorization_header → verify_access_token (PyJWT, iss/aud) → is_token_blocked (MongoDB) → TokenData
Logout: get_token_jti → add_token_to_blocklist (blocked_tokens.insert_one)
Deps: get_authorization_header, get_current_user_token, get_current_user, require_admin, require_org_admin, require_user_type, require_feature
```

## B5. Resilience

```
Rate limiting (incoming):
  - Global: RateLimitMiddleware, per-IP, RATE_LIMIT_PER_MINUTE=60, sliding 60s window
  - Seeker: _check_seeker_rate_limit, SEEKER_PUBLIC_RATE_LIMIT_PER_MINUTE=20

CircuitBreaker (outgoing): per-host/circuit_key, closed/open/half-open,
  CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT_SECONDS; used by ResilientHttpClient for external API calls
RetryPolicy: exponential backoff + jitter, retry 408/425/429/5xx, httpx timeouts
ConcurrencyLimiter: Semaphore(MAX_CONCURRENT_REQUESTS=10)
ResilientHttpClient: httpx + retry + circuit breaker + concurrency limit
```

## B6. Response Schemas

```
SuccessResponse[T], ErrorResponse (error_code, details), ValidationErrorResponse (validation_errors),
PaginatedResponse[T] (PaginationMeta)
```

## B7. Secondary Tools Summary

```
Black: pyproject.toml, line-length 88
Ruff: pyproject.toml/ruff.toml, known-first-party: [app, tests]
MyPy: pyproject.toml, ignore pymongo/motor/bson
Bandit: pre-commit, exclude tests, app/externals
pytest/pytest-asyncio/pytest-cov/pytest-mock
pre-commit: black, ruff, bandit, pre-commit-hooks
```

## B8. Logging & Monitoring

```
Logging: setup_logging() in main; UTCFormatter/JSONFormatter; ClientIPFilter; sanitize_log_data, mask_phone_number, hash_identifier; uvicorn/pymongo WARNING
Metrics: prometheus-fastapi-instrumentator on /metrics
External: Grafana(3000), Prometheus(9090), Loki(3100), Promtail, Node Exporter(9100), Nginx Exporter(9113)
```

## B9. Search Types

```
EMAIL, DOMAIN, PHONE, VEHICLE_RC, VEHICLE_FAST_TAG, VEHICLE_ALL, VEHICLE_CHASIS, USERNAME,
IP_LOOKUP, IMEI_LOOKUP, VIRTUAL_NUMBER, VIRTUAL_EMAIL, BANK_ACCOUNT, VERIFY_ID
```

## B10. Services & Adapters

```
Orchestrators: SearchOrchestrator, PhoneLookupOrchestrator, EmailLookupOrchestrator, LightweightOrchestrator
Adapters: EmailAdapter, DomainAdapter, PhoneLookupAdapter, VehicleLookupAdapter, IPLookupAdapter,
  IMEILookupAdapter, VirtualNumberAdapter, VirtualEmailAdapter, BankLookupAdapter, VerifyIdAdapter,
  SocialMediaAdapter, SecurityAdapter
```

## B11. Excluded from Core

ghunt, selenium, telethon, skpy, ignorant – integration-only, not core architecture.

---

*End of Technical Specification*
