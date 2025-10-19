# OSINT Backend API

A comprehensive REST API backend built with FastAPI and MongoDB for OSINT (Open Source Intelligence) data gathering and analysis.

## Features

- **RESTful API** with FastAPI framework
- **MongoDB** database with PyMongo Async driver for data persistence
- **JWT Authentication** with secure token management
- **Rate Limiting** and security headers
- **Async Operations** for concurrent data gathering
- **Comprehensive Testing** with pytest
- **Logging** with rotation and sanitization
- **Background Tasks** for long-running operations

## Architecture

```text
app/
├── core/           # Core functionality (config, database, security, logging)
├── models/         # Data models and schemas
├── services/       # Business logic and data access
├── adapters/       # External API adapters
├── api/            # API endpoints and routing
├── schemas/        # Request/response schemas
└── main.py         # Application entry point

tests/              # Test suite
├── conftest.py     # Test configuration
├── test_auth.py    # Authentication tests
├── test_user.py    # User management tests
└── test_search.py  # Search functionality tests
```

## Quick Start

### Prerequisites

- Python 3.8+
- MongoDB 4.4+
- pip

### Installation

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

## API Endpoints

### Authentication

- `POST /api/v1/auth/token` - Get access token

### Users

- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/me` - Get current user
- `PUT /api/v1/users/me` - Update current user
- `GET /api/v1/users/` - List users (admin)
- `DELETE /api/v1/users/{user_id}` - Delete user (admin)

### Searches

- `POST /api/v1/searches/` - Create search
- `GET /api/v1/searches/{search_id}` - Get search results
- `GET /api/v1/searches/` - List searches
- `GET /api/v1/searches/stats/overview` - Get search statistics
- `DELETE /api/v1/searches/{search_id}` - Delete search

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

#### ✅ **Service Layer Tests (Recommended Pattern)**

For testing service methods that use Beanie queries like `User.find_one(User.email == user.email)`:

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

#### ✅ **Unit Tests for Model Behavior**

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

#### ✅ **Integration Tests**

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

### **Key Testing Rules**

1. **Always use `Mock(spec=User)` for mock user instances** (same pattern as auth tests)
2. **Mock the User class at the service level** (`app.services.user_service.User`)
3. **Setup `mock_user_class.email` with `__eq__` method** for query patterns
4. **Make database methods like `find_one` and `insert` AsyncMock objects**
5. **For model unit tests, always mock `User.get_settings`** to avoid initialization errors

For comprehensive testing patterns and examples, see [tests/README.md](tests/README.md#testing-with-beanie-models).

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `osint_backend` |
| `SECRET_KEY` | JWT secret key | `development_secret_key` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per IP | `60` |

## Development

### Project Structure

- **Models**: Data models using Pydantic with MongoDB ObjectId support
- **Services**: Business logic layer with database operations
- **Adapters**: External API integrations (email, domain, etc.)
- **API**: FastAPI endpoints with proper error handling
- **Tests**: Comprehensive test suite with fixtures

### Adding New Adapters

1. Create a new adapter class inheriting from `OSINTAdapter`
2. Implement the required methods
3. Add the adapter to `SearchOrchestrator`
4. Write tests for the new adapter

### Database Schema

- **users**: User accounts and authentication
- **searches**: Search requests and status
- **results**: Search results from various sources

## Security Features

- JWT token authentication
- Password hashing with bcrypt
- Rate limiting per IP address
- Security headers (CORS, XSS protection, etc.)
- Input validation and sanitization
- Logging with sensitive data sanitization

## Production Deployment

1. Set production environment variables
2. Use a production MongoDB instance
3. Configure proper CORS origins
4. Set up monitoring and logging
5. Use a reverse proxy (nginx)
6. Enable HTTPS
