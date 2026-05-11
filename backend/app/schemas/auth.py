# ============================================================
# schemas/auth.py
# ============================================================
#
# CONCEPT: Field validators — Pydantic's input sanitisation layer
# ----------------------------------------------------------------
# Validators run BEFORE the data reaches your route function.
# If validation fails → Pydantic raises a 422 Unprocessable Entity
# automatically. Your route function never runs.
#
# Two types of validators in Pydantic v2:
#
#   @field_validator("field_name")  → validates/transforms a single field
#   @model_validator(mode="after")  → validates the whole model after all
#                                     fields are set (cross-field checks)
#
# CONCEPT: EmailStr vs str for email fields
# ------------------------------------------
# EmailStr is a Pydantic type that validates the email FORMAT:
#   "notanemail"         → rejected (no @)
#   "x@"                → rejected (no domain)
#   "user@example.com"  → accepted
#
# It does NOT verify the email actually exists (no DNS check).
# Install: pip install pydantic[email]   (installs email-validator)
# ============================================================

from pydantic import BaseModel, EmailStr, field_validator, Field


# ---------------------------------------------------------------
# POST /auth/login   request body
# ---------------------------------------------------------------
# CONCEPT: Request schemas don't need from_attributes=True
# ---------------------------------------------------------
# from_attributes is for reading ORM objects → response schemas.
# Request schemas read from plain JSON dicts → no ORM needed.
# Keep them as simple BaseModel subclasses.
# ---------------------------------------------------------------
class LoginRequest(BaseModel):
    """
    Credentials sent by the client to authenticate.
    Used by: POST /auth/login
    """

    email: EmailStr = Field(
        ...,
        description="The user's registered email address",
        examples=["student@university.edu"],
    )

    # CONCEPT: Field(...) with constraints
    # ------------------------------------
    # Field(...) = required (same as having no default)
    # min_length=8 → Pydantic rejects passwords shorter than 8 chars
    # This is CLIENT-SIDE validation. The real security is bcrypt hashing.
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,     # Prevent bcrypt DoS (bcrypt is slow by design)
        description="Account password — minimum 8 characters",
    )

    # CONCEPT: @field_validator with mode="before"
    # ---------------------------------------------
    # mode="before" → runs BEFORE Pydantic's own type coercion
    # mode="after"  → runs AFTER (value is already the correct type)
    #
    # Use "before" when you want to transform raw input (e.g. lowercase email)
    # Use "after"  when you need the already-typed value for logic
    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        """Lowercase and strip whitespace from the email before validation."""
        return v.strip().lower()


# ---------------------------------------------------------------
# POST /auth/login   response body
# POST /auth/refresh response body
# ---------------------------------------------------------------
# CONCEPT: token_type is always "bearer"
# ----------------------------------------
# The OAuth2 Bearer token scheme requires the client to send:
#   Authorization: Bearer <access_token>
# token_type tells the client which scheme to use.
# It's always "bearer" for JWT-based APIs.
# We include it in the response for OAuth2 spec compliance and
# so generic OAuth2 clients (Postman, etc.) can auto-configure.
# ---------------------------------------------------------------
class TokenResponse(BaseModel):
    """
    JWT token pair returned after successful authentication or refresh.
    Used by: POST /auth/login, POST /auth/refresh
    """

    access_token: str = Field(
        ...,
        description="Short-lived JWT (15 min). Include in Authorization: Bearer header.",
    )

    refresh_token: str = Field(
        ...,
        description="Long-lived JWT (7 days). Use only to obtain new access tokens.",
    )

    # CONCEPT: Literal type for fixed values
    # ----------------------------------------
    # Literal["bearer"] means this field can ONLY ever be the string "bearer".
    # - The response is always correct (no accidental wrong value)
    # - OpenAPI docs show the exact value in the schema
    # - Client code can assert token_type == "bearer" safely
    token_type: str = Field(
        default="bearer",
        description="OAuth2 token scheme. Always 'bearer' for this API.",
    )