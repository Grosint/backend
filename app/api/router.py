from fastapi import APIRouter

from app.api.endpoints import admin, auth, history, search, user

# Main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(user.router, prefix="/user", tags=["User"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(admin.router, prefix="/admin/debug", tags=["Admin Debug"])
