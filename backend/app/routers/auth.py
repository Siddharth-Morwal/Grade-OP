# ============================================================
# routers/auth.py
# ============================================================
#
# CONCEPT: What is a Router?
# ---------------------------
# Instead of defining ALL routes in main.py (which becomes a mess),
# FastAPI lets you create "mini-apps" called APIRouters.
# Each router owns a slice of your API (auth, users, exams...).
# main.py then just mounts them: app.include_router(auth.router)
#
# CONCEPT: What happens during login?
# -------------------------------------
# 1. User sends { email, password }
# 2. We look up the user in PostgreSQL
# 3. We verify the password hash (never store plain text!)
# 4. We mint two JWTs:
#    - access_token  → short-lived (15 min), used on every request
#    - refresh_token → long-lived (7 days), only used to get new access tokens
# 5. Client stores both; when access_token expires, hits /auth/refresh
#
# WHY TWO TOKENS?
# ---------------
# If we made the access token long-lived and it got stolen,
# the attacker has days of access. Short access tokens limit damage.
# The refresh token lives in httpOnly cookie (JS can't read it).
# ============================================================

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserOut
from app.auth.dependencies import get_current_user

# ---------------------------------------------------------------
# Router setup
# prefix="/auth"  → every route here starts with /auth
# tags=["auth"]   → groups routes in the auto-generated /docs UI
# ---------------------------------------------------------------
# NOTE: prefix is set in main.py via include_router() — do NOT set it here too.
router = APIRouter(tags=["auth"])


class RefreshRequest(BaseModel):
    """Request body for the /refresh endpoint."""
    refresh_token: str


# ---------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------
# CONCEPT: status_code=200 is implicit, but being explicit is good practice.
# response_model=TokenResponse tells FastAPI:
#   - Validate the return value against this Pydantic schema
#   - Only expose fields declared in TokenResponse (data hiding)
#   - Auto-generate the correct OpenAPI docs shape
# ---------------------------------------------------------------
@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,        # ← Pydantic auto-validates incoming JSON
    db: AsyncSession = Depends(get_db) # ← Dependency injection: FastAPI calls get_db()
                                       #   and passes the session here; closes it after
):
    """
    Authenticate a user and return JWT access + refresh tokens.

    Flow:
      1. Find user by email
      2. Verify bcrypt password hash
      3. Return signed tokens
    """
    # ---- Step 1: Import here to avoid circular imports at module level ----
    # In large projects, keep DB queries in a separate `crud/` layer.
    # For now, inline is fine while learning.
    from app.auth.dependencies import authenticate_user

    user = await authenticate_user(db, credentials.email, credentials.password)

    if not user:
        # SECURITY: Always say "incorrect credentials" — never reveal
        # which field (email vs password) was wrong. Enumeration attacks
        # try to discover which emails are registered.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},  # OAuth2 spec requires this header
        )

    # ---- Step 2: Mint tokens ----
    # The "subject" of a JWT is the unique identifier for the entity it represents.
    # We use user.id (UUID string) so we can look them up on every request.
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


# ---------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------
# CONCEPT: Token Refresh Flow
# ----------------------------
# The client sends the refresh_token (from cookie or body).
# We verify it's a valid, non-expired refresh token we signed.
# If valid → issue a brand-new access_token.
# We do NOT re-issue the refresh token (prevents indefinite sessions).
# ---------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    payload: RefreshRequest,           # Body field — not a query param (avoids log exposure)
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    The refresh token itself is NOT rotated here (stateless design).
    """
    # verify_refresh_token decodes the JWT and returns the user_id (subject)
    # Raises HTTPException 401 if token is expired or tampered
    user_id = verify_refresh_token(payload.refresh_token)

    # Optional: check user still exists / is still active
    from app.auth.dependencies import get_user_by_id
    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    new_access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=payload.refresh_token,   # Return same refresh token unchanged
        token_type="bearer",
    )


# ---------------------------------------------------------------
# GET /auth/me  (bonus: verify a token and return the current user)
# ---------------------------------------------------------------
# CONCEPT: get_current_user is a Depends chain:
#   get_current_user → reads Bearer token from Authorization header
#                    → decodes JWT
#                    → fetches user from DB
#                    → returns User ORM object
# This pattern is reused across ALL protected routes.
# ---------------------------------------------------------------
@router.get("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_me(current_user=Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
