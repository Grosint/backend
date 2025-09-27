from fastapi import APIRouter

from app.api.endpoints import auth, search, user

# Main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(search.router, prefix="/searches", tags=["Searches"])
api_router.include_router(user.router, prefix="/users", tags=["Users"])
