"""Schemas for signup, login, and the authenticated user."""

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: Literal["farmer", "fisherman", "disaster_team", "citizen"] = "citizen"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class GoogleAuthRequest(BaseModel):
    """Demo-only 'Continue with Google' — accepts a name/email pair from the
    frontend's Google Identity Services sign-in instead of a real password.
    Swap this for verified Google ID-token validation before going live."""
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str = "citizen"
    provider: str = "password"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
