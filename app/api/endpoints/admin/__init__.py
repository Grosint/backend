"""
Admin Debug Endpoints Module

This module combines all admin debug routers for phone lookup, email lookup, and services.
"""

from fastapi import APIRouter

from app.api.endpoints.admin import email_lookup, phone_lookup, services

# Create main admin router
router = APIRouter()

# Include all admin sub-routers
router.include_router(phone_lookup.router, tags=["Admin Debug - Phone Lookup"])
router.include_router(email_lookup.router, tags=["Admin Debug - Email Lookup"])
router.include_router(services.router, tags=["Admin Debug - Services"])
