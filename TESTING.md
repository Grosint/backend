# Testing Setup

This project uses Docker to provide a MongoDB instance for testing, eliminating the need for a local MongoDB installation.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ with virtual environment activated

## Running Tests

### Option 1: Using the test runner script (Recommended)

```bash
# Run all tests with Docker
python run_tests.py

# Run specific test file
python run_tests.py tests/test_user.py

# Run tests with verbose output
python run_tests.py -v

# Run tests without Docker (if MongoDB is already running locally)
python run_tests.py --no-docker
```

### Option 2: Using Make commands

```bash
# Install dependencies
make install

# Run tests with Docker (default)
make test

# Run tests without Docker
make test-no-docker

# Clean up Docker containers
make clean-docker
```

### Option 3: Using pytest directly

```bash
# Run tests (requires Docker to be started manually)
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_user.py
```

## Docker Configuration

The test setup uses `docker-compose.test.yml` which:

- Starts a MongoDB 7.0 container on port 27018
- Uses authentication with username `testuser` and password `testpass`
- Creates a test database `test_osint_backend`
- Automatically cleans up after tests

## Test Database

- **URL**: `mongodb://testuser:testpass@localhost:27018`
- **Database**: `test_osint_backend`
- **Collections**: `users`, `searches`, `results`

The test database is automatically cleaned before and after each test run.

## Troubleshooting

### Docker Issues

If you encounter Docker-related issues:

1. Ensure Docker is running: `docker --version`
2. Check if ports are available: `lsof -i :27018`
3. Clean up containers: `make clean-docker`

### MongoDB Connection Issues

If MongoDB connection fails:

1. Check if the container is running: `docker ps`
2. Check container logs: `docker logs osint-backend-test-mongodb`
3. Verify the container is healthy: `docker exec osint-backend-test-mongodb mongosh --eval "db.adminCommand('ping')"`

### Test Failures

If tests fail:

1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check if the virtual environment is activated
3. Verify the test database connection string in `tests/conftest.py`
