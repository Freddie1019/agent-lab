from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status, Depends
from deep_research_agent.api.auth import create_access_token, CurrentUser, get_current_user

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str
    token_type: str = "bearer"


FAKE_USERS = {
    "alice": {
        "user_id": "user_alice",
        "username": "alice",
        "password": "123456",
        "role": "user",
    },
    "admin": {
        "user_id": "user_admin",
        "username": "admin",
        "password": "admin123",
        "role": "admin",
    },
}


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Log in and return an access token."""

    user = FAKE_USERS.get(request.username)

    if user is None or user["password"] != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "invalid-credentials",
                "title": "Invalid Credentials",
                "detail": "Username or password is incorrect",
            },
        )

    token = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
    )

    return LoginResponse(access_token=token)

@router.get("/me", response_model=CurrentUser)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Get current authenticated user info."""
    return current_user