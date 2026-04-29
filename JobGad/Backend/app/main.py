from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Import routers
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.coaching import router as coaching_router
from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.hr import router as hr_router
from app.api.v1.routes.applications import router as applications_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.cv import router as cv_router
from app.api.v1.routes.coaching_ws import router as coaching_ws_router
from app.api.v1.routes.search import router as search_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router setup
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(profile_router, prefix=f"{settings.API_V1_STR}/profile", tags=["Profile"])
app.include_router(jobs_router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Jobs"])
app.include_router(coaching_router, prefix=f"{settings.API_V1_STR}/coaching", tags=["Coaching"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])
app.include_router(hr_router, prefix=f"{settings.API_V1_STR}/hr", tags=["HR"])
app.include_router(applications_router,prefix=f"{settings.API_V1_STR}/applications",tags=["Applications"],)
app.include_router(notifications_router,prefix=f"{settings.API_V1_STR}/notifications",tags=["Notifications"],)
app.include_router(cv_router,prefix=f"{settings.API_V1_STR}/cv",tags=["CV Generation"])
app.include_router(coaching_ws_router,prefix=f"{settings.API_V1_STR}/coaching",tags=["Coaching WebSocket"])
app.include_router(search_router,prefix=f"{settings.API_V1_STR}/search",tags=["Search"])

@app.get("/health", tags=["System"])
async def root():
    return {
        "status": "ok", 
        "project": settings.PROJECT_NAME, 
        "version": settings.PROJECT_VERSION
    }
