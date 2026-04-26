"""
Notifications routes — in-app notifications for all users.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.application import Notification

router = APIRouter()


@router.get(
    "/",
    summary="Get all my notifications",
)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notifications for the current user, newest first."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "related_job_id": str(n.related_job_id) if n.related_job_id else None,
                "related_application_id": str(n.related_application_id) if n.related_application_id else None,
                "created_at": str(n.created_at),
            }
            for n in notifications
        ],
        "total": len(notifications),
        "unread": sum(1 for n in notifications if not n.is_read),
    }


@router.patch(
    "/{notification_id}/read",
    summary="Mark a notification as read",
)
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a specific notification as read."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    notification = result.scalar_one_or_none()

    if not notification:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    notification.is_read = True
    await db.commit()

    return {"message": "Notification marked as read."}


@router.patch(
    "/read-all",
    summary="Mark all notifications as read",
)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all unread notifications as read."""
    stmt = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    for notification in notifications:
        notification.is_read = True

    await db.commit()

    return {
        "message": f"Marked {len(notifications)} notifications as read."
    }