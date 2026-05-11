# ============================================================
# schemas/users.py
# ============================================================
#
# CONCEPT: Schema layering — one resource, three schemas
# -------------------------------------------------------
# The User resource has different shapes at different points:
#
#   UserCreate  (POST /users)
#   ├── email:      required
#   ├── password:   required (plain text — we hash it before DB)
#   ├── full_name:  required
#   └── role:       optional (default: student)
#
#   UserUpdate  (PATCH /users/me)
#   ├── full_name:  optional
#   ├── password:   optional (user changing their password)
#   └── avatar_url: optional
#   (email not updatable — changing email needs a verification flow)
#
#   UserOut  (response for all User endpoints)
#   ├── id, email, full_name, role, is_active, avatar_url
#   ├── created_at, updated_at
#   └── ← hashed_password is ABSENT — never exposed
#
# CONCEPT: Why not one schema with all fields optional?
# -------------------------------------------------------
# Because the validation rules differ:
#   - POST: password is REQUIRED and must meet strength rules
#   - PATCH: password is OPTIONAL but still must meet strength rules IF sent
#   - Response: password doesn't exist at all
# One "catch-all" schema can't express these three sets of rules cleanly.
# ============================================================

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from app.models.user import UserRole
from app.schemas.base import AppResponseSchema


# ---------------------------------------------------------------
# UserCreate — POST /users  request body
# ---------------------------------------------------------------
class UserCreate(BaseModel):
    """
    Payload for registering a new user account.
    Password is plain text here — the router hashes it before touching the DB.
    """

    email: EmailStr = Field(
        ...,
        description="Unique email address used to log in",
        examples=["student@university.edu"],
    )

    # CONCEPT: Password strength validation
    # ----------------------------------------
    # min_length=8 is a minimum floor — many real systems enforce more.
    # The validator below adds a strength check (uppercase + digit).
    # In production, consider zxcvbn library for real strength scoring.
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password. Min 8 chars, must include a digit.",
    )

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="User's display name",
        examples=["Arjun Sharma"],
    )

    # CONCEPT: Optional with Enum default
    # -------------------------------------
    # Optional[UserRole] means the client doesn't HAVE to send a role.
    # If omitted, it defaults to "student".
    # We reuse the same UserRole enum defined in the ORM model —
    # single source of truth for valid role values.
    role: Optional[UserRole] = Field(
        default=UserRole.student,
        description="Access level. Defaults to 'student' if not specified.",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Enforce minimum password complexity:
        - At least one digit
        - At least one uppercase letter
        """
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------
# UserUpdate — PATCH /users/me  request body
# ---------------------------------------------------------------
# CONCEPT: All-optional schema for PATCH endpoints
# --------------------------------------------------
# Every field is Optional because PATCH means "send only what changed".
# The router uses:
#   payload.model_dump(exclude_unset=True)
# which returns ONLY the fields the client actually included in the request.
# Fields the client didn't send are excluded from the update entirely.
#
# This is the correct pattern — never wipe fields the client didn't mention.
# ---------------------------------------------------------------
class UserUpdate(BaseModel):
    """
    Partial update payload for a user's own profile.
    Only include fields you want to change.
    """

    full_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=200,
        description="Updated display name",
    )

    # Changing password goes through the same strength check
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New password. Must meet strength requirements.",
    )

    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to the user's profile picture",
    )

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


# ---------------------------------------------------------------
# UserOut — response schema for ALL user endpoints
# ---------------------------------------------------------------
# CONCEPT: What makes a good response schema
# -------------------------------------------
# 1. Inherits AppResponseSchema (from_attributes=True) so FastAPI
#    can pass an ORM User object directly and Pydantic reads its attributes.
#
# 2. NEVER includes hashed_password. If it's not declared here,
#    Pydantic won't include it — even if the ORM object has it.
#    This is the security guarantee: response_model=UserOut strips secrets.
#
# 3. UUID fields → serialized as plain strings in JSON (uuid.UUID objects
#    aren't JSON-serializable by default; Pydantic handles this for us).
#
# 4. datetime fields → serialized as ISO 8601 strings automatically.
#    "2025-01-15T10:30:00Z" — universally parseable by any client.
# ---------------------------------------------------------------
class UserOut(AppResponseSchema):
    """
    User data returned by the API. Safe to expose to any caller.
    hashed_password is intentionally absent.
    """

    id: uuid.UUID = Field(description="User's unique identifier")
    email: str    = Field(description="Login email address")
    full_name: str= Field(description="Display name")
    role: UserRole= Field(description="Access level: student | teacher | admin")
    is_active: bool = Field(description="False means the account is deactivated")
    avatar_url: Optional[str] = Field(default=None, description="Profile picture URL")
    created_at: datetime = Field(description="When the account was created")
    updated_at: datetime = Field(description="When the account was last modified")

    # CONCEPT: model_config in the response schema
    # ----------------------------------------------
    # We inherit from AppResponseSchema which already sets from_attributes=True.
    # No need to repeat it here. Inheritance handles it.
    # If you need to OVERRIDE a parent config option, you can redeclare it here.