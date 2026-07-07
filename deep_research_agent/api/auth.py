from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from deep_research_agent.core.settings import get_settings

settings = get_settings()
security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Current authenticated user parsed from a JWT."""

    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="Username")
    role: str = Field(default="user", description="User role")


class TokenPayload(BaseModel):
    """JWT payload fields used by the API."""

    sub: str = Field(..., description="Subject user ID")
    username: str
    role: str = "user"
    exp: int


def _auth_error(
    error_type: str,
    title: str,
    detail: str,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error_type": error_type,
            "title": title,
            "detail": detail,
        },
    )


def create_access_token(
    user_id: str,
    username: str,
    role: str = "user",
    expires_minutes: Optional[int] = None,
) -> str:
    """Create a JWT access token."""

    if expires_minutes is None:
        expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
    }
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token."""

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        raise _auth_error(
            error_type="token-expired",
            title="Token Expired",
            detail="Access token has expired. Please log in again.",
        )

    except jwt.InvalidTokenError:
        raise _auth_error(
            error_type="invalid-token",
            title="Invalid Token",
            detail="Access token is invalid.",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    """FastAPI dependency that returns the current authenticated user."""

    if credentials is None:
        raise _auth_error(
            error_type="missing-token",
            title="Missing Authorization Token",
            detail="Missing Authorization Bearer token.",
        )

    if credentials.scheme.lower() != "bearer":
        raise _auth_error(
            error_type="invalid-auth-scheme",
            title="Invalid Authorization Scheme",
            detail="Authorization scheme must be Bearer.",
        )

    payload = decode_access_token(credentials.credentials)

    return CurrentUser(
        user_id=payload.sub,
        user_name=payload.username,
        role=payload.role,
    )
