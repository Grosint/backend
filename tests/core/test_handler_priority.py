#!/usr/bin/env python3
"""Test FastAPI exception handler priority."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import BaseAPIException, ConflictException

app = FastAPI()


# Handler 1: Specific ConflictException handler
async def conflict_specific_handler(
    request: Request, exc: ConflictException
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"message": "SPECIFIC: Conflict handler", "type": "ConflictException"},
    )


# Handler 2: General BaseAPIException handler
async def base_api_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": "GENERAL: BaseAPI handler", "type": "BaseAPIException"},
    )


# Test 1: Only BaseAPIException handler registered
print("=== Test 1: Only BaseAPIException handler ===")
app1 = FastAPI()
app1.add_exception_handler(BaseAPIException, base_api_handler)

# Simulate handler resolution
exc = ConflictException("Test conflict")
print(f"Exception type: {type(exc)}")
print(f"Exception MRO: {type(exc).__mro__}")

# Check which handler would be used
for exc_type in type(exc).__mro__:
    if exc_type in app1.exception_handlers:
        print(f"✅ Handler found for: {exc_type.__name__}")
        break
    else:
        print(f"❌ No handler for: {exc_type.__name__}")

print("\n=== Test 2: Both handlers registered ===")
app2 = FastAPI()
app2.add_exception_handler(
    ConflictException, conflict_specific_handler
)  # More specific
app2.add_exception_handler(BaseAPIException, base_api_handler)  # Less specific

# Check which handler would be used
for exc_type in type(exc).__mro__:
    if exc_type in app2.exception_handlers:
        print(f"✅ Handler found for: {exc_type.__name__}")
        break
    else:
        print(f"❌ No handler for: {exc_type.__name__}")

print("\n=== Handler Priority Summary ===")
print("1. ConflictException handler (most specific) - wins if registered")
print("2. BaseAPIException handler (parent class) - used if #1 not found")
print("3. Exception handler (grandparent) - fallback if #1,#2 not found")
