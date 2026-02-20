"""
Admin Debug Endpoints Module

This module combines all admin debug routers for phone lookup, email lookup, and services.
"""

from fastapi import APIRouter

from app.api.endpoints.admin import (
    aitan_service,
    befisc_service,
    email_lookup,
    phone_lookup,
    services,
    simple_lookup,
    user_management,
)

# Create main admin router
router = APIRouter()

# Include all admin sub-routers
router.include_router(phone_lookup.router, tags=["Admin Debug - Phone Lookup"])
router.include_router(email_lookup.router, tags=["Admin Debug - Email Lookup"])
router.include_router(services.router, tags=["Admin Debug - Services"])
router.include_router(user_management.router, tags=["Admin - User Management"])
router.include_router(befisc_service.router, tags=["Admin Debug - Befisc Service"])
router.include_router(
    aitan_service.router, prefix="/aitan", tags=["Admin Debug - AITAN Service"]
)
router.include_router(simple_lookup.router, tags=["Admin Debug - Simple Lookups"])
