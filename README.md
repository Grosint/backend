# OSINT Backend API - Comprehensive Documentation

A comprehensive REST API backend built with FastAPI and MongoDB for OSINT (Open Source Intelligence) data gathering and analysis. This system provides a flexible, resilient architecture for orchestrating multiple external APIs with circuit breaker protection, retry logic, and comprehensive history tracking.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Implementation Details](#implementation-details)
5. [Usage Examples](#usage-examples)
6. [Development Guide](#development-guide)
7. [Testing](#testing)
8. [Configuration](#configuration)
9. [Deployment](#deployment)

---

## Overview

### Features

- **RESTful API** with FastAPI framework
- **MongoDB** database with PyMongo Async driver for data persistence
- **JWT Authentication** with secure token management and refresh tokens
- **Rate Limiting** and security headers
- **Async Operations** for concurrent data gathering
- **Resilience Patterns**: Circuit breakers, retry logic, timeout handling
- **Comprehensive Testing** with pytest
- **Logging** with rotation and sanitization
- **Background Tasks** for long-running operations
- **History Tracking** for all API calls and results
- **Multi-API Orchestration** with parallel execution

### Quick Start

#### Prerequisites

- Python 3.8+
- MongoDB 4.4+
- pip

#### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. **Start MongoDB**

   ```bash
   # Make sure MongoDB is running on localhost:27017
   mongod
   ```

6. **Run the application**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### API Documentation

Once the server is running, visit:

- **Swagger UI**: <http://localhost:8000/api/docs>
- **ReDoc**: <http://localhost:8000/api/redoc>

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Endpoints Layer                     │
│  (auth.py, user.py, search.py, history.py, admin.py)        │
└──────────────────────┬──────────────────────────────────────┘
                      │
┌──────────────────────▼──────────────────────────────────────┐
│                   Services Layer                             │
│  (auth_service, user_service, search_orchestrator,          │
│   history_service, result_service)                          │
└──────────────────────┬──────────────────────────────────────┘
                      │
┌──────────────────────▼──────────────────────────────────────┐
│                    Adapters Layer                            │
│  (phone_lookup_adapter, domain_adapter, email_adapter,      │
│   social_media_adapter, security_adapter)                   │
└──────────────────────┬──────────────────────────────────────┘
                      │
┌──────────────────────▼──────────────────────────────────────┐
│              External APIs Layer (by Category)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Phone Lookup │  │ Social Media │  │   Security   │     │
│  │ Orchestrator │  │ Orchestrator │  │ Orchestrator │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐                                           │
│  │    Domain    │                                           │
│  │ Orchestrator │                                           │
│  └──────────────┘                                           │
└──────────────────────┬──────────────────────────────────────┘
                      │
┌──────────────────────▼──────────────────────────────────────┐
│              Individual API Services                         │
│  (ViewCaller, TrueCaller, Eyecon, CallApp, WhatsApp, etc.)  │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Request Received**: API endpoint receives request (e.g., `/api/v1/searches/`)
2. **Search Creation**: `SearchService` creates a search record in MongoDB
3. **Orchestration**: `SearchOrchestrator` determines which adapters to use based on search type
4. **Adapter Execution**: Each adapter orchestrates multiple external APIs in parallel
5. **History Tracking**: `GenericOrchestrator` tracks all API calls and results
6. **Result Storage**: Results stored in MongoDB via `ResultService` and `HistoryService`
7. **Response**: Search status and history ID returned to client

### Key Components

#### 1. **GenericOrchestrator** (`app/services/generic_orchestrator.py`)

- Manages parallel execution of multiple adapters
- Tracks history of all API calls
- Handles errors and exceptions gracefully
- Records latency and success/failure status

#### 2. **SearchOrchestrator** (`app/services/search_orchestrator.py`)

- High-level orchestration for different search types
- Maps search types to appropriate adapters
- Manages search status updates
- Coordinates with GenericOrchestrator

#### 3. **Adapters** (`app/adapters/`)

- High-level interfaces for different API categories
- Normalize responses to standard format
- Handle category-specific logic
- Use category orchestrators for actual API calls

#### 4. **Category Orchestrators** (`app/external_apis/{category}/`)

- Manage multiple APIs within a category
- Execute APIs in parallel
- Combine results from multiple sources
- Handle category-specific response formatting

#### 5. **Individual Services** (`app/external_apis/{category}/`)

- Handle individual external API integration
- Format API-specific responses
- Implement resilience patterns per API

---

## Project Structure

### Complete Folder Structure

```
app/
├── core/                           # Core infrastructure
│   ├── __init__.py
│   ├── auth_dependencies.py       # JWT authentication dependencies
│   ├── config.py                  # Application configuration
│   ├── database.py                # MongoDB connection and Beanie setup
│   ├── error_handlers.py          # Global error handlers
│   ├── exceptions.py              # Custom exceptions
│   ├── logging.py                 # Logging configuration
│   ├── resilience.py              # Circuit breaker, retry, timeout
│   ├── response_mapper.py         # Response normalization
│   ├── security.py                # Security utilities (password hashing, etc.)
│   └── token_blocklist.py         # JWT token blacklist management
│
├── models/                         # Data models (Beanie ODM)
│   ├── user.py                    # User model
│   ├── search.py                  # Search model
│   ├── result.py                  # Result model
│   └── history.py                 # History model
│
├── schemas/                        # Pydantic schemas for API
│   ├── user.py                    # User request/response schemas
│   ├── search.py                  # Search request/response schemas
│   ├── result.py                  # Result schemas
│   └── history.py                 # History schemas
│
├── services/                       # Business logic services
│   ├── auth_service.py            # Authentication business logic
│   ├── user_service.py            # User management business logic
│   ├── history_service.py         # History business logic
│   ├── search_service.py          # Search business logic
│   ├── result_service.py          # Result business logic
│   ├── search_orchestrator.py     # High-level search orchestration
│   └── generic_orchestrator.py    # Generic multi-adapter orchestration
│
├── adapters/                       # High-level adapters
│   ├── base.py                    # Base adapter class (OSINTAdapter)
│   ├── phone_lookup_adapter.py    # Phone lookup adapter
│   ├── domain_adapter.py          # Domain analysis adapter
│   ├── email_adapter.py           # Email validation adapter
│   ├── social_media_adapter.py    # Social media adapter
│   └── security_adapter.py        # Security/threat adapter
│
├── external_apis/                  # External API integrations (by category)
│   ├── __init__.py
│   ├── phone_lookup/              # Phone lookup APIs
│   │   ├── __init__.py
│   │   ├── viewcaller_service.py
│   │   ├── truecaller_service.py
│   │   ├── eyecon_service.py
│   │   ├── callapp_service.py
│   │   ├── whatsapp_service.py
│   │   └── phone_lookup_orchestrator.py
│   ├── social_media/              # Social media APIs
│   │   ├── __init__.py
│   │   └── social_media_orchestrator.py
│   ├── security/                  # Security/threat APIs
│   │   ├── __init__.py
│   │   └── security_orchestrator.py
│   └── domain/                    # Domain analysis APIs
│       ├── __init__.py
│       └── domain_orchestrator.py
│
├── api/                            # API endpoints
│   ├── router.py                  # Main API router
│   └── endpoints/
│       ├── auth.py                # Authentication endpoints
│       ├── user.py                # User management endpoints
│       ├── search.py              # Search endpoints
│       ├── history.py             # History endpoints
│       └── admin.py               # Admin endpoints
│
├── utils/                          # Utility functions
│   └── ...
│
└── main.py                         # Application entry point
```

### Structure Benefits

#### 1. **Clear Separation of Concerns**

- **`services/`**: Business logic (auth, user, history, search orchestration)
- **`external_apis/`**: External API integrations organized by category
- **`adapters/`**: High-level orchestration and normalization
- **`api/`**: REST endpoints
- **`core/`**: Infrastructure components

#### 2. **Scalable by Category**

- **Phone Lookup**: All phone-related APIs in `external_apis/phone_lookup/`
- **Social Media**: All social media APIs in `external_apis/social_media/`
- **Security**: All security APIs in `external_apis/security/`
- **Domain**: All domain analysis APIs in `external_apis/domain/`

#### 3. **Easy Navigation**

- Find phone APIs: `external_apis/phone_lookup/`
- Find social media APIs: `external_apis/social_media/`
- Find business logic: `services/`
- Find orchestration: `adapters/`

#### 4. **Independent Development**

- Teams can work on different categories without conflicts
- Easy to add new APIs to existing categories
- Easy to add new categories of APIs

---

## Implementation Details

### Phone Lookup Implementation

#### Architecture

The phone lookup system demonstrates the complete architecture pattern:

1. **PhoneLookupAdapter** (`app/adapters/phone_lookup_adapter.py`)
   - High-level adapter interface
   - Uses `PhoneLookupOrchestrator` for actual API calls
   - Normalizes responses to standard format

2. **PhoneLookupOrchestrator** (`app/external_apis/phone_lookup/phone_lookup_orchestrator.py`)
   - Orchestrates 5 phone lookup services
   - Executes all APIs in parallel
   - Combines results from all sources

3. **Individual Services** (`app/external_apis/phone_lookup/`)
   - **ViewCallerService**: Name lookup service
   - **TrueCallerService**: Comprehensive phone data (name, email, address)
   - **EyeconService**: Social media integration (Facebook)
   - **CallAppService**: Multi-platform data (Facebook, Twitter, Google+)
   - **WhatsAppService**: WhatsApp business/personal account data

#### Response Format Normalization

Each API has completely different response structures that get normalized:

**ViewCaller Response Format:**

```json
{
  "data": [
    {
      "names": [{"name": "John Doe"}],
      "name": "John Doe"
    }
  ]
}
```

**TrueCaller Response Format:**

```json
{
  "data": [
    {
      "name": "John Doe",
      "internetAddresses": [{"caption": "john@email.com", "id": "john@email.com"}],
      "addresses": [{"street": "123 Main St", "city": "New York"}]
    }
  ]
}
```

**Eyecon Response Format:**

```json
{
  "data": {
    "fullName": "John Doe",
    "image": "profile.jpg",
    "facebookID": {"url": "https://facebook.com/john", "profileURL": "profile.jpg"}
  }
}
```

**CallApp Response Format:**

```json
{
  "data": {
    "name": "John Doe",
    "facebookID": {"id": "john.doe"},
    "emails": [{"email": "john@email.com"}],
    "twitterScreenName": {"id": "johndoe"}
  }
}
```

**WhatsApp Response Format:**

```json
{
  "isBusiness": true,
  "about": "Business description",
  "businessProfile": {
    "address": "123 Main St",
    "description": "Business info",
    "email": "business@email.com"
  },
  "profilePic": "profile.jpg"
}
```

**Standardized Output Format:**
All APIs get normalized to this standard format:

```json
{
  "success": true,
  "message": "Phone lookup completed successfully",
  "data": {
    "phone": "+1234567890",
    "lookup_results": {
      "viewcaller": {
        "found": true,
        "data": [
          {"source": "viewcaller", "type": "name", "value": "John Doe", "category": "TEXT"}
        ]
      },
      "truecaller": {
        "found": true,
        "data": [
          {"source": "truecaller", "type": "name", "value": "John Doe", "category": "TEXT"},
          {"source": "truecaller", "type": "email", "value": "john@email.com", "category": "TEXT"}
        ]
      }
    },
    "summary": {
      "total_sources": 5,
      "successful_sources": 3,
      "found_data": true
    }
  }
}
```

#### Refactoring History

The phone lookup implementation was refactored from a single large adapter (543 lines) into a modular structure:

**Before:**

- Single `PhoneLookupAdapter` with all 5 APIs embedded (543 lines)

**After:**

- `PhoneLookupAdapter`: 65 lines (88% reduction)
- 5 individual service files in `external_apis/phone_lookup/`
- `PhoneLookupOrchestrator` for coordination

**Benefits:**

- Single Responsibility: Each service handles one API
- Small Files: Easy to understand and modify
- Independent Testing: Each service can be tested separately
- Maintainability: Modify one service without affecting others

### Resilience Features

#### Circuit Breaker

- **Failure Threshold**: 3 failures → circuit opens
- **Recovery Time**: 60 seconds → circuit half-open
- **Per-API**: Each API has its own circuit breaker (e.g., `viewcaller_api`, `truecaller_api`)

#### Retry Logic

- **Max Attempts**: 3 retries
- **Backoff**: Exponential with jitter
- **Retryable Errors**: Timeouts, connection errors, 5xx status codes

#### Concurrency Control

- **Max Concurrent**: 10 requests (configurable)
- **Queue Management**: Overflow requests wait for available slots
- **Parallel Execution**: All APIs called in parallel with semaphore limiting

#### Graceful Degradation

- If some APIs fail, others continue working
- Errors are captured and included in response
- Partial results are still returned

### Response Mapper System

Each adapter can define custom response formatting:

- **Social Media**: Focuses on platform data, engagement metrics
- **Security**: Emphasizes threat analysis, risk assessment
- **Domain**: Highlights technical details, SSL status
- **Phone Lookup**: Normalizes different API formats to standard structure

---

## Usage Examples

### API Endpoints

#### Authentication

- `POST /api/v1/auth/token` - Get access token
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout (blacklist token)

#### Users

- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/me` - Get current user
- `PUT /api/v1/users/me` - Update current user
- `GET /api/v1/users/` - List users (admin)
- `DELETE /api/v1/users/{user_id}` - Delete user (admin)

#### Searches

- `POST /api/v1/searches/` - Create and execute search
- `GET /api/v1/searches/{search_id}` - Get search results
- `GET /api/v1/searches/` - List searches
- `GET /api/v1/searches/stats/overview` - Get search statistics
- `DELETE /api/v1/searches/{search_id}` - Delete search

#### History

- `GET /api/v1/history/{history_id}` - Get detailed history

### Example 1: Phone Lookup

```bash
curl -X POST "http://localhost:8000/api/v1/searches/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "1234567890",
    "search_type": "PHONE",
    "country_code": "+1"
  }'
```

**Response:**

```json
{
  "success": true,
  "message": "Search created and execution started",
  "data": {
    "search_id": "65f8a1b2c3d4e5f6a7b8c9d0",
    "status": "IN_PROGRESS",
    "history_id": "65f8a1b2c3d4e5f6a7b8c9d1"
  }
}
```

### Example 2: Get Detailed Results

```bash
curl "http://localhost:8000/api/v1/history/65f8a1b2c3d4e5f6a7b8c9d1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response shows all API results:**

```json
{
  "success": true,
  "data": {
    "history_id": "65f8a1b2c3d4e5f6a7b8c9d1",
    "query_type": "PHONE",
    "query_input": {"phone": "1234567890", "country_code": "+1"},
    "status": "COMPLETED",
    "results": [
      {
        "source": "PhoneLookupAdapter",
        "success": true,
        "latency_ms": 2500,
        "data": {
          "success": true,
          "message": "Phone lookup completed successfully",
          "data": {
            "phone": "+11234567890",
            "lookup_results": {
              "viewcaller": {
                "found": true,
                "data": [
                  {"source": "viewcaller", "type": "name", "value": "John Doe", "category": "TEXT"}
                ]
              },
              "truecaller": {
                "found": true,
                "data": [
                  {"source": "truecaller", "type": "name", "value": "John Doe", "category": "TEXT"},
                  {"source": "truecaller", "type": "email", "value": "john@email.com", "category": "TEXT"}
                ]
              }
            },
            "summary": {
              "total_sources": 5,
              "successful_sources": 5,
              "found_data": true
            }
          }
        }
      }
    ],
    "metadata": {
      "total_sources": 1,
      "successful_sources": 1,
      "failed_sources": 0,
      "duration_ms": 2500
    }
  }
}
```

### Example 3: Email Search with Multiple APIs

```bash
curl -X POST "http://localhost:8000/api/v1/searches/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user@example.com",
    "search_type": "EMAIL"
  }'
```

**What happens:**

1. **EmailAdapter**: Validates email format, checks domain
2. **SocialMediaAdapter**: Searches Twitter, LinkedIn, Facebook
3. **SecurityAdapter**: Checks malware, phishing, breach databases

### Example 4: Domain Search

```bash
curl -X POST "http://localhost:8000/api/v1/searches/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "example.com",
    "search_type": "DOMAIN"
  }'
```

**What happens:**

1. **DomainAdapter**: WHOIS, DNS records, SSL certificate, subdomains
2. **SocialMediaAdapter**: Social media presence, influence metrics
3. **SecurityAdapter**: Malware detection, reputation, SSL analysis

---

## Development Guide

### Adding New Phone Lookup API

1. **Create service in `external_apis/phone_lookup/new_service.py`:**

   ```python
   from app.core.resilience import ResilientHttpClient
   from app.core.config import settings

   class NewPhoneService:
       def __init__(self):
           self.client = ResilientHttpClient(
               timeout=settings.EXTERNAL_API_TIMEOUT,
               circuit_key="new_phone_api"
           )
           self.api_key = settings.NEW_PHONE_API_KEY

       async def search_phone(self, country_code: str, phone: str) -> dict:
           response = await self.client.request(
               "GET",
               "https://api.newphone.com/lookup",
               params={"phone": f"{country_code}{phone}"},
               headers={"X-API-Key": self.api_key},
               circuit_key="new_phone_api"
           )
           return self._format_response(response)

       def _format_response(self, data: dict) -> list[dict]:
           # Convert to standard format
           return [
               {"source": "new_phone", "type": "name", "value": data.get("name"), "category": "TEXT"}
           ]
   ```

2. **Add to `PhoneLookupOrchestrator`:**

   ```python
   from app.external_apis.phone_lookup.new_service import NewPhoneService

   class PhoneLookupOrchestrator:
       def __init__(self):
           self.viewcaller = ViewCallerService()
           self.truecaller = TrueCallerService()
           # ... existing services
           self.new_phone = NewPhoneService()  # Add here

       async def search_phone(self, country_code: str, phone: str):
           tasks = [
               self.viewcaller.search_phone(country_code, phone),
               # ... existing tasks
               self.new_phone.search_phone(country_code, phone),  # Add here
           ]
           results = await asyncio.gather(*tasks, return_exceptions=True)
           # ... combine results
   ```

3. **No changes needed in adapters or endpoints** - they automatically use the orchestrator!

### Adding New Category of APIs

1. **Create folder structure:**

   ```bash
   mkdir -p app/external_apis/new_category
   ```

2. **Create orchestrator:**

   ```python
   # app/external_apis/new_category/new_category_orchestrator.py
   class NewCategoryOrchestrator:
       def __init__(self):
           self.service1 = Service1()
           self.service2 = Service2()

       async def search(self, query: str):
           # Orchestrate all services
           pass
   ```

3. **Create adapter:**

   ```python
   # app/adapters/new_category_adapter.py
   from app.adapters.base import OSINTAdapter
   from app.external_apis.new_category.new_category_orchestrator import NewCategoryOrchestrator

   class NewCategoryAdapter(OSINTAdapter):
       def __init__(self):
           super().__init__()
           self.name = "NewCategoryAdapter"
           self.orchestrator = NewCategoryOrchestrator()

       async def search(self, query: str):
           return await self.orchestrator.search(query)
   ```

4. **Add to SearchOrchestrator:**

   ```python
   from app.adapters.new_category_adapter import NewCategoryAdapter

   class SearchOrchestrator:
       def __init__(self, db):
           # ... existing code
           self.new_category_adapter = NewCategoryAdapter()
           self.adapters[SearchType.NEW_TYPE] = [self.new_category_adapter]
   ```

### Adding New Adapter (Different Base URLs)

1. **Create adapter:**

   ```python
   # app/adapters/new_api_adapter.py
   from app.adapters.base import OSINTAdapter
   from app.core.resilience import ResilientHttpClient

   class NewAPIAdapter(OSINTAdapter):
       def __init__(self):
           super().__init__()
           self.name = "NewAPIAdapter"
           self.client = ResilientHttpClient()

       async def search_email(self, email: str) -> dict[str, Any]:
           try:
               response = await self.client.request(
                   "GET",
                   "https://your-api.com/endpoint",
                   params={"email": email},
                   circuit_key="your_api_key",
               )
               return self.normalize_success_response(response)
           except Exception as e:
               return self.normalize_error_response(e)
   ```

2. **Register response mapper (optional):**

   ```python
   # app/core/response_mapper.py
   def your_api_success_mapper(raw_response: dict) -> dict:
       return {
           "success": True,
           "message": "Your API data retrieved successfully",
           "data": {
               "your_field": raw_response.get("your_field"),
           },
           "metadata": {
               "source_type": "your_api",
           }
       }

   response_mapper.register_success_mapper("NewAPIAdapter", your_api_success_mapper)
   ```

3. **Add to SearchOrchestrator:**

   ```python
   from app.adapters.new_api_adapter import NewAPIAdapter

   class SearchOrchestrator:
       def __init__(self, db):
           # ... existing code
           self.new_api_adapter = NewAPIAdapter()
           self.adapters[SearchType.EMAIL].append(self.new_api_adapter)
   ```

### Key Patterns

#### Service Pattern

- Each external API gets its own service class
- Services handle API-specific logic and formatting
- Services use `ResilientHttpClient` for resilience

#### Orchestrator Pattern

- Category orchestrators manage multiple services
- Execute services in parallel
- Combine and normalize results

#### Adapter Pattern

- Adapters provide high-level interface
- Use orchestrators for actual API calls
- Normalize responses to standard format

---

## Testing

### Quick Start

```bash
# Run all tests with Docker (recommended)
python run_tests.py

# Run all tests without Docker (requires local MongoDB)
python run_tests.py --no-docker

# Run tests and open HTML coverage report
python run_tests.py --open-report
```

### Test Categories

```bash
# Run specific test files
python run_tests.py test_user_database.py
python run_tests.py test_auth_endpoints.py

# Run with pattern matching
python run_tests.py -k "test_user_creation"

# Run specific test classes or functions
python run_tests.py test_user_database::TestUserTimestampBehavior
```

### Testing with Beanie Models

This project uses Beanie (MongoDB ODM) for data models. **Always follow these patterns** when writing tests to avoid `CollectionWasNotInitialized` errors:

#### ✅ Service Layer Tests (Recommended Pattern)

For testing service methods that use Beanie queries:

```python
from unittest.mock import AsyncMock, MagicMock, Mock, patch

@pytest.mark.asyncio
async def test_create_user_database_interaction(self, user_service):
    """Test user creation with proper Beanie mocking."""
    # Create a mock user instance using Mock(spec=User)
    mock_user = Mock(spec=User)
    mock_user.id = ObjectId()
    mock_user.email = "test@example.com"
    mock_user.insert = AsyncMock()

    # Mock the User model at the service level
    with patch('app.services.user_service.User') as mock_user_class:
        # Setup mock to handle query pattern: User.email == user.email
        mock_user_class.email = MagicMock()
        mock_user_class.email.__eq__ = MagicMock(return_value="query")
        mock_user_class.find_one = AsyncMock(return_value=None)
        mock_user_class.return_value = mock_user

        result = await user_service.create_user(user_create)

        # Verify calls
        mock_user_class.find_one.assert_called_once()
        mock_user.insert.assert_called_once()
```

#### ✅ Unit Tests for Model Behavior

For testing model validation, timestamps, and business logic:

```python
def test_user_model_behavior(self):
    """Test user model behavior without database operations."""
    with patch('app.models.user.User.get_settings') as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.pymongo_collection = MagicMock()
        mock_get_settings.return_value = mock_settings

        # Now you can safely instantiate the User model
        user = User(
            email="test@example.com",
            phone="+1234567890",
            password="hashed_password"
        )

        # Test model behavior
        user.set_timestamps()
        assert user.createdAt is not None
        assert user.updatedAt is not None
```

#### ✅ Integration Tests

For testing actual database operations:

```python
@pytest.mark.asyncio
async def test_user_database_operations(self, beanie_init):
    """Test actual database operations with Beanie."""
    # Beanie is now initialized, you can perform database operations
    user = User(
        email="test@example.com",
        phone="+1234567890",
        password="hashed_password"
    )

    # Insert into database
    await user.insert()

    # Query from database
    found_user = await User.find_one(User.email == "test@example.com")
    assert found_user is not None
```

### Key Testing Rules

1. **Always use `Mock(spec=User)` for mock user instances**
2. **Mock the User class at the service level** (`app.services.user_service.User`)
3. **Setup `mock_user_class.email` with `__eq__` method** for query patterns
4. **Make database methods like `find_one` and `insert` AsyncMock objects**
5. **For model unit tests, always mock `User.get_settings`** to avoid initialization errors

For comprehensive testing patterns and examples, see [tests/README.md](tests/README.md#testing-with-beanie-models).

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `osint_backend` |
| `SECRET_KEY` | JWT secret key | `development_secret_key` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per IP | `60` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `DEBUG` | Debug mode | `false` |
| `EXTERNAL_API_TIMEOUT` | Timeout for external API calls (seconds) | `30` |
| `MAX_CONCURRENT_REQUESTS` | Maximum concurrent HTTP requests | `10` |
| `CB_FAILURE_THRESHOLD` | Circuit breaker failure threshold | `3` |
| `CB_RECOVERY_TIMEOUT_SECONDS` | Circuit breaker recovery timeout | `60` |
| `RETRY_MAX_ATTEMPTS` | Maximum retry attempts | `3` |
| `RETRY_INITIAL_BACKOFF_SECONDS` | Initial retry backoff | `0.2` |
| `RETRY_BACKOFF_MULTIPLIER` | Retry backoff multiplier | `2.0` |
| `RAPIDAPI_KEY` | RapidAPI key for external APIs | `""` |

### External API Keys

Add API keys to your `.env` file:

```bash
# Phone Lookup APIs
VIEWCALLER_API_KEY=your_viewcaller_key
TRUECALLER_API_KEY=your_truecaller_key
EYECON_API_KEY=your_eyecon_key
CALLAPP_API_KEY=your_callapp_key
WHATSAPP_API_KEY=your_whatsapp_key

# Other APIs
RAPIDAPI_KEY=your_rapidapi_key
# Add other API keys as needed
```

### Database Schema

- **users**: User accounts and authentication
- **searches**: Search requests and status
- **results**: Search results from various sources
- **history**: Complete history of all API calls and results

---

## Deployment

### Production Deployment

1. **Set production environment variables**

   ```bash
   export ENVIRONMENT=production
   export DEBUG=false
   export SECRET_KEY=<strong-secret-key>
   export MONGODB_URL=<production-mongodb-url>
   ```

2. **Use a production MongoDB instance**
   - Set up MongoDB Atlas or self-hosted MongoDB
   - Configure proper authentication and network access

3. **Configure proper CORS origins**

   ```bash
   export CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

4. **Set up monitoring and logging**
   - Configure log rotation
   - Set up log aggregation (e.g., ELK stack)
   - Monitor circuit breaker states
   - Track API performance metrics

5. **Use a reverse proxy (nginx)**

   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

6. **Enable HTTPS**
   - Use Let's Encrypt for SSL certificates
   - Configure nginx to handle SSL termination

### Monitoring & Analytics

#### Logs to Watch

```bash
# Circuit breaker state changes
grep "Circuit opened" logs/app-*.log
grep "Circuit closed" logs/app-*.log

# API performance
grep "HTTP request success" logs/app-*.log
grep "HTTP retry" logs/app-*.log

# History tracking
grep "History created" logs/app-*.log
grep "History finalized" logs/app-*.log
```

#### Key Metrics

- **Success Rate**: `successful_sources / total_sources`
- **Average Latency**: Per-source timing
- **Circuit Breaker Status**: Which APIs are open/closed
- **Retry Attempts**: How often APIs need retries
- **Error Rates**: Per-API error rates

---

## Security Features

- **JWT token authentication** with short-lived access tokens and refresh tokens
- **Password hashing** with bcrypt
- **Rate limiting** per IP address
- **Security headers** (CORS, XSS protection, etc.)
- **Input validation** and sanitization
- **Logging with sensitive data sanitization**
- **Token blacklist** for logout functionality
- **Circuit breakers** to prevent cascading failures

---

## Benefits of This Architecture

1. **Flexible**: Easy to add new APIs with different response formats
2. **Resilient**: Continues working even if some APIs fail
3. **Fast**: All APIs called in parallel with concurrency control
4. **Trackable**: Complete history of all API calls and results
5. **Standardized**: Consistent response format across all APIs
6. **Maintainable**: Clear separation between API logic and response formatting
7. **Scalable**: Easy to add new categories and APIs
8. **Testable**: Each component can be tested independently

---

## License

[Add your license here]

---

## Contributing

[Add contributing guidelines here]

---

## Support

[Add support information here]
