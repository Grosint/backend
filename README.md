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

```
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
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

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

### Run all tests
```bash
pytest
```

### Run specific test categories
```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m e2e          # End-to-end tests only
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

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

## License

[Add your license here]
