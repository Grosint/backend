from fastapi import APIRouter

from app.api.endpoints import auth, user

# Main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(user.router, prefix="/user", tags=["User"])
