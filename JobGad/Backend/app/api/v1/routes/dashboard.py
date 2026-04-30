"""
Dashboard routes — overview stats for graduates and HR users.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.services.dashboard_service import (
    get_graduate_dashboard,
    get_hr_dashboard,
)

router = APIRouter()


@router.get(
    "/graduate",
    summary="Get graduate dashboard stats",
)
async def graduate_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete dashboard for a graduate user.

    Returns:
    - Profile completeness and details
    - Job matches summary (total, new this week, top match)
    - Applications by status
    - Recent applications
    - Coaching stats and IRI score history
    - Unread notifications count
    - Personalized next steps

    Available to: **graduate** role only
    """
    if current_user.role not in {"graduate", "admin", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This dashboard is for graduate users only.",
        )

    return await get_graduate_dashboard(db, current_user)


@router.get(
    "/hr",
    summary="Get HR dashboard stats",
)
async def hr_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete dashboard for an HR user.

    Returns:
    - Company details and status
    - Jobs overview (total, published, draft, closed)
    - Applications overview (by status, new today, new this week)
    - Recent applications with applicant info
    - Top jobs by application count
    - Unread notifications count

    Available to: **hr**, **admin**, **superadmin** roles
    """
    if current_user.role not in {"hr", "admin", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This dashboard is for HR users only.",
        )

    return await get_hr_dashboard(db, current_user)


@router.get(
    "/me",
    summary="Get dashboard for current user (auto-detects role)",
)
async def my_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Automatically returns the right dashboard based on your role.

    - graduate → returns graduate dashboard
    - hr → returns HR dashboard
    - superadmin → returns admin dashboard stats
    """
    if current_user.role == "graduate":
        return await get_graduate_dashboard(db, current_user)

    elif current_user.role in {"hr"}:
        return await get_hr_dashboard(db, current_user)

    elif current_user.role in {"admin", "superadmin"}:
        from app.services.admin_service import get_admin_dashboard
        return await get_admin_dashboard(db, current_user)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No dashboard available for role: {current_user.role}",
        )