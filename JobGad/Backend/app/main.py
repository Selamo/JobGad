from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from jose import JWTError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.error_handler import (
    validation_exception_handler,
    sqlalchemy_exception_handler,
    jwt_exception_handler,
    general_exception_handler,
    rate_limit_handler,
)

# Import all routers
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.coaching import router as coaching_router
from app.api.v1.routes.coaching_ws import router as coaching_ws_router
from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.hr import router as hr_router
from app.api.v1.routes.applications import router as applications_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.cv import router as cv_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.dashboard import router as dashboard_router

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="""
    ## AI-Powered Graduate Career Acceleration Platform

    This API powers the JobGad platform — helping graduates in Cameroon
    and across Africa find jobs, practice interviews, and accelerate their careers.

    ### Key Features:
    - 🎯 AI-powered job matching using semantic search
    - 🤖 AI interview coaching with real-time feedback
    - 📄 Automated CV generation tailored to specific jobs
    - 🏢 Company and HR management system
    - 📊 Progress tracking and IRI scoring

    ### Authentication:
    Use the `/auth/login` endpoint to get a JWT token.
    Include it as: `Authorization: Bearer <token>`
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ─── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Exception Handlers ───────────────────────────────────────────────────────
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
app.add_exception_handler(
    SQLAlchemyError,
    sqlalchemy_exception_handler,
)
app.add_exception_handler(
    JWTError,
    jwt_exception_handler,
)
app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_handler,
)
app.add_exception_handler(
    Exception,
    general_exception_handler,
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(
    auth_router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"],
)
app.include_router(
    profile_router,
    prefix=f"{settings.API_V1_STR}/profile",
    tags=["Profile"],
)
app.include_router(
    jobs_router,
    prefix=f"{settings.API_V1_STR}/jobs",
    tags=["Jobs"],
)
app.include_router(
    coaching_router,
    prefix=f"{settings.API_V1_STR}/coaching",
    tags=["Coaching"],
)
app.include_router(
    coaching_ws_router,
    prefix=f"{settings.API_V1_STR}/coaching",
    tags=["Coaching WebSocket"],
)
app.include_router(
    admin_router,
    prefix=f"{settings.API_V1_STR}/admin",
    tags=["Admin"],
)
app.include_router(
    hr_router,
    prefix=f"{settings.API_V1_STR}/hr",
    tags=["HR"],
)
app.include_router(
    applications_router,
    prefix=f"{settings.API_V1_STR}/applications",
    tags=["Applications"],
)
app.include_router(
    notifications_router,
    prefix=f"{settings.API_V1_STR}/notifications",
    tags=["Notifications"],
)
app.include_router(
    cv_router,
    prefix=f"{settings.API_V1_STR}/cv",
    tags=["CV Generation"],
)
app.include_router(
    search_router,
    prefix=f"{settings.API_V1_STR}/search",
    tags=["Search"],
)
app.include_router(
    dashboard_router,
    prefix=f"{settings.API_V1_STR}/dashboard",
    tags=["Dashboard"],
)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Used by Render and other deployment platforms to verify the app is running.
    """
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — redirects to docs."""
    return {
        "message": "Welcome to JobGad API",
        "docs": "/docs",
        "health": "/health",
        "version": settings.PROJECT_VERSION,
    }