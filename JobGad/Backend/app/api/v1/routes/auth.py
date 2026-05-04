from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.services.email_service import send_welcome_email
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from app.core.rate_limiter import limiter

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.api.v1.dependencies import get_current_user

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
@limiter.limit("5/minute")  # Max 5 registrations per minute per IP
async def register_user(
    request: Request,  # Required for rate limiter
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):

async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account.

    - **email**: unique email address
    - **password**: minimum 6 characters
    - **full_name**: display name
    - **role**: `graduate` (default) | `recruiter` | `admin`
    """
    # Check if the email is already taken
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
from fastapi.security import OAuth2PasswordRequestForm

@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT tokens",
)
@limiter.limit("10/minute")  # Max 10 login attempts per minute per IP
async def login_user(
    request: Request,  # Required for rate limiter
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):

async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.
    Returns access_token and refresh_token.
    """
    # Look up user by email
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Validate credentials
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Block inactive accounts
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
    Exchange a valid **refresh token** for a new **access token**.

    The refresh token must:
    - Be a valid JWT signed by this server
    - Have `type == "refresh"` in its payload
    - Not be expired
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode and validate the token
    payload = decode_token(body.refresh_token)
    if payload is None:
        raise invalid_exc

    # Ensure this is actually a refresh token (not an access token being reused)
    if payload.get("type") != "refresh":
        raise invalid_exc

    user_id: str = payload.get("sub")
    if not user_id:
        raise invalid_exc

    # Confirm the user still exists and is active
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

    # Issue a fresh access token
    return TokenRefreshResponse(
        access_token=create_access_token(subject=str(user.id)),
    )


# ---------------------------------------------------------------------------
# Logout  (stateless — client should discard tokens)
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout (invalidate session on client side)",
)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout the current user.

    Since JWTs are stateless, actual token invalidation happens on the **client**
    (delete stored tokens). A token blacklist (e.g. Redis) can be wired in here
    in a future iteration for server-side revocation.
    """
    return {"message": f"Successfully logged out. Goodbye, {current_user.full_name}!"}


# ---------------------------------------------------------------------------
# Current User Profile
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the user associated with the provided Bearer token.
    """
    return current_user
