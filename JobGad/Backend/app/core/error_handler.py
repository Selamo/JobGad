"""
Global Error Handler — catches all unhandled exceptions and returns
clean, consistent JSON error responses.
"""
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from jose import JWTError


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    Returns clean error messages instead of raw Pydantic output.
    """
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation Error",
            "message": "One or more fields are invalid.",
            "details": errors,
        },
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """
    Handle database errors gracefully.
    Hides internal DB details from the client.
    """
    print(f"[DB Error] {request.url}: {str(exc)}")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Database Error",
            "message": "A database error occurred. Please try again.",
        },
    )


async def jwt_exception_handler(
    request: Request,
    exc: JWTError,
) -> JSONResponse:
    """Handle JWT token errors."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "success": False,
            "error": "Authentication Error",
            "message": "Invalid or expired token. Please login again.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catch-all handler for any unhandled exceptions.
    Logs the full traceback but returns a clean response.
    """
    print(f"[Unhandled Error] {request.method} {request.url}")
    print(f"Error: {type(exc).__name__}: {str(exc)}")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": "Something went wrong. Please try again later.",
        },
    )


async def rate_limit_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "success": False,
            "error": "Rate Limit Exceeded",
            "message": "Too many requests. Please slow down and try again.",
        },
    )