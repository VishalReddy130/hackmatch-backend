import re
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Body for POST /auth/register"""

    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 30:
            raise ValueError("Username must be at most 30 characters")
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                "Username may only contain lowercase letters, numbers, and underscores"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    """Body for POST /auth/login"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Returned by both /auth/register and /auth/login.

    The frontend stores access_token in a cookie or localStorage,
    then sends it as: Authorization: Bearer <access_token>
    """

    access_token: str
    token_type: str = "bearer"
    username: str
