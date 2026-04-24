from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Import routers
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.coaching import router as coaching_router
from app.api.v1.routes.admin import router as admin_router

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

@app.get("/health", tags=["System"])
async def root():
    return {
        "status": "ok", 
        "project": settings.PROJECT_NAME, 
        "version": settings.PROJECT_VERSION
    }
