from fastapi import APIRouter

from app.api.endpoints import (
    admin,
    auth,
    credit,
    history,
    payment,
    plan,
    search,
    seeker,
    subscription,
    user,
)
from app.api.endpoints.admin import profiler_scrape as admin_profiler_scrape
from app.profiler.router import router as profiler_router

# Main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(user.router, prefix="/user", tags=["User"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(admin.router, prefix="/admin/debug", tags=["Admin Debug"])
api_router.include_router(
    admin_profiler_scrape.router,
    prefix="/admin/profiler",
    tags=["Admin Profiler"],
)
api_router.include_router(plan.router, prefix="/plans", tags=["Plans"])
api_router.include_router(payment.router, prefix="/payments", tags=["Payments"])
api_router.include_router(
    subscription.router, prefix="/subscriptions", tags=["Subscriptions"]
)
api_router.include_router(credit.router, prefix="/credits", tags=["Credits"])
api_router.include_router(seeker.router, prefix="/seeker", tags=["Seeker"])
api_router.include_router(profiler_router)
