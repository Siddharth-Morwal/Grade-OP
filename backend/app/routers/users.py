# ============================================================
# routers/users.py
# ============================================================
#
# CONCEPT: Why a separate users router?
# --------------------------------------
# auth.py handles *proving who you are* (authentication).
# users.py handles *your account data* (CRUD on the User resource).
# Separation of concerns → each file has one clear job.
#
# CONCEPT: Password Hashing
# --------------------------
# NEVER store plain-text passwords. Ever.
# bcrypt is the standard: it's slow by design (brute-force resistant)
# and includes a random salt so two users with "password123"
# get completely different hashes.
#
# passlib makes this trivial:
#   pwd_context.hash("mypassword")   → "$2b$12$..."
#   pwd_context.verify("mypassword", stored_hash) → True/False
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.users import UserCreate, UserOut, UserUpdate

# NOTE: prefix is set in main.py via include_router() — do NOT set it here too.
router = APIRouter(tags=["users"])


# ---------------------------------------------------------------
# POST /users   → Create a new account (public, no auth needed)
# ---------------------------------------------------------------
# CONCEPT: status_code=201
# ---------------------------
# HTTP 200 = "OK, here's data you asked for"
# HTTP 201 = "Created — a new resource now exists"
# Always use 201 for successful resource creation. It signals to
# API clients (and HTTP caches) that something new was made.
# ---------------------------------------------------------------
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,               # { email, password, full_name, role }
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Checks:
    - Email must not already exist
    - Password is hashed before storage
    """
    from app.models.user import User
    from app.auth.hashing import hash_password

    # ---- Guard: duplicate email ----
    # `select(User).where(...)` is SQLAlchemy 2.0 style (async-compatible).
    # Older style was `db.query(User).filter(...)` — that's sync-only.
    result = await db.execute(select(User).where(User.email == payload.email))
    existing = result.scalar_one_or_none()  # Returns None if not found, User if found

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,   # 409 = resource already exists
            detail="A user with this email already exists",
        )

    # ---- Hash the password before touching the DB ----
    hashed = hash_password(payload.password)

    # ---- Create the ORM object ----
    # We unpack the Pydantic schema with .model_dump() → plain dict
    # Then override 'password' with the hashed version
    user = User(
        **payload.model_dump(exclude={"password"}),  # spread all fields except password
        hashed_password=hashed,
    )

    db.add(user)          # Stage the INSERT
    await db.commit()     # Execute it and commit the transaction
    await db.refresh(user)  # Reload from DB so we get the auto-generated id, created_at etc.

    return user  # FastAPI serializes this through UserOut (hides hashed_password)


# ---------------------------------------------------------------
# GET /users/me  → Current user's profile (protected)
# ---------------------------------------------------------------
# CONCEPT: Depends(get_current_user)
# -----------------------------------
# This is FastAPI's dependency injection. When a request hits this route:
# 1. FastAPI calls get_current_user() first
# 2. get_current_user reads the Authorization header
# 3. Decodes the JWT → extracts user_id
# 4. Fetches the User from DB
# 5. Returns the User object → injected as `current_user` here
#
# If the token is missing/expired → get_current_user raises 401
# and our function never even runs. Clean!
# ---------------------------------------------------------------
@router.get("/me", response_model=UserOut)
async def get_my_profile(current_user=Depends(get_current_user)):
    """Return the authenticated user's own profile."""
    return current_user


# ---------------------------------------------------------------
# PATCH /users/me  → Update own profile
# ---------------------------------------------------------------
# CONCEPT: PATCH vs PUT
# ----------------------
# PUT    = replace the entire resource (send ALL fields)
# PATCH  = update only the fields you send (partial update)
# For user profiles, PATCH is almost always correct — you don't
# want to accidentally wipe fields you didn't include.
#
# CONCEPT: exclude_unset=True
# ----------------------------
# Pydantic tracks which fields were actually sent vs just defaulting.
# payload.model_dump(exclude_unset=True) → only the fields the client
# actually provided in the request body. This is how partial updates work.
# ---------------------------------------------------------------
@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Partially update the authenticated user's profile."""
    update_data = payload.model_dump(exclude_unset=True)  # Only sent fields

    if "password" in update_data:
        from app.auth.hashing import hash_password
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(current_user, field, value)  # Update the ORM object in-place

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return current_user


# ---------------------------------------------------------------
# GET /users/{user_id}  → Fetch any user (admin only)
# ---------------------------------------------------------------
# CONCEPT: Role-based access control (RBAC)
# ------------------------------------------
# require_roles("admin") is another Depends() chain.
# It calls get_current_user internally, then checks user.role.
# If the user isn't an admin → raises 403 Forbidden.
# 401 = "I don't know who you are"  (not authenticated)
# 403 = "I know who you are, but you can't do this" (not authorized)
# ---------------------------------------------------------------
@router.get("/{user_id}", response_model=UserOut)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_roles("admin")),  # underscore = we don't use the return value
):
    """Fetch any user by ID. Admin only."""
    from app.models.user import User
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return user


# ---------------------------------------------------------------
# DELETE /users/{user_id}  → Soft-delete (admin only)
# ---------------------------------------------------------------
# CONCEPT: Soft Delete vs Hard Delete
# ------------------------------------
# Hard delete: DELETE FROM users WHERE id = ?  → gone forever
# Soft delete: UPDATE users SET is_active = false → row stays
#
# Soft deletes are safer: audit trails, foreign key integrity,
# and "undo" become possible. Most production apps use soft deletes.
# ---------------------------------------------------------------
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Soft-delete (deactivate) a user account. Admin only."""
    from app.models.user import User
    import uuid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False   # Soft delete
    db.add(user)
    await db.commit()
    # HTTP 204 = No Content: success, but nothing to return
