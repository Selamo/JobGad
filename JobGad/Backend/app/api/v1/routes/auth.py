from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.api.v1.dependencies import get_current_user
from app.services.email_service import send_welcome_email

router = APIRouter()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user account.
    """
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    await send_welcome_email(
        email=new_user.email,
        full_name=new_user.full_name,
    )

    return new_user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT tokens",
)
@limiter.limit("10/minute")
async def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.
    Returns access_token and refresh_token.
    """
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return Token(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


# ---------------------------------------------------------------------------
# Refresh Access Token
# ---------------------------------------------------------------------------
@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Get a fresh access token using a refresh token",
)
async def refresh_access_token(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(body.refresh_token)
    if payload is None:
        raise invalid_exc

    if payload.get("type") != "refresh":
        raise invalid_exc

    user_id: str = payload.get("sub")
    if not user_id:
        raise invalid_exc

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise invalid_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return TokenRefreshResponse(
        access_token=create_access_token(subject=str(user.id)),
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Stateless logout. Client should discard tokens.
    """
    return {"message": f"Successfully logged out. Goodbye, {current_user.full_name}!"}


# ---------------------------------------------------------------------------
# Current User
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the authenticated user.
    """
    return current_user