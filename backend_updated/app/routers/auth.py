"""
WeatherGPT — Auth Router

POST /api/auth/signup   — create an account with name/email/password
POST /api/auth/login    — exchange email/password for a JWT access token
POST /api/auth/google   — demo "Continue with Google" (name/email, no password)
GET  /api/auth/me       — return the current user for a valid Bearer token
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from app.services import database
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _user_out(record: dict) -> UserOut:
    return UserOut(
        id=record["id"],
        name=record["name"],
        email=record["email"],
        role=record.get("role", "citizen"),
        provider=record.get("provider", "password"),
    )


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: require a valid `Authorization: Bearer <token>` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await database.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


async def get_current_user_optional(authorization: str | None = Header(default=None)) -> dict | None:
    """Like get_current_user, but returns None instead of raising for guests."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """Create a new account and return an access token."""
    existing = await database.get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    try:
        record = await database.create_user(
            name=request.name.strip(),
            email=request.email,
            password_hash=hash_password(request.password),
            provider="password",
            role=request.role,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    except Exception:
        logger.exception("Signup failed")
        raise HTTPException(status_code=500, detail="Could not create the account.")

    token = create_access_token(user_id=record["id"], email=record["email"])
    return TokenResponse(access_token=token, user=_user_out(record))


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Verify credentials and return an access token."""
    record = await database.get_user_by_email(request.email)
    if not record or not verify_password(request.password, record.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user_id=record["id"], email=record["email"])
    return TokenResponse(access_token=token, user=_user_out(record))


@router.post("/google", response_model=TokenResponse)
async def google_auth(request: GoogleAuthRequest):
    """Demo Google sign-in: creates the account on first use, then logs in.

    NOTE: this trusts the name/email the frontend sends. Before shipping,
    replace this with verification of a real Google ID token on the backend.
    """
    record = await database.get_user_by_email(request.email)
    if not record:
        record = await database.create_user(
            name=request.name.strip(),
            email=request.email,
            password_hash=None,
            provider="google",
        )

    token = create_access_token(user_id=record["id"], email=record["email"])
    return TokenResponse(access_token=token, user=_user_out(record))


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return _user_out(current_user)
