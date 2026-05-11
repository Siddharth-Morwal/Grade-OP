from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database.postgres import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["users"])

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    from app.models.user import User
    from app.auth.hashing import hash_password

    result = await db.execute(select(User).where(User.email == payload.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    hashed = hash_password(payload.password)

    user = User(
        **payload.model_dump(exclude={"password"}),
        hashed_password=hashed,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

@router.get("/me", response_model=UserOut)
async def get_my_profile(current_user=Depends(get_current_user)):
    """Return the authenticated user's own profile."""
    return current_user

@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Partially update the authenticated user's profile."""
    update_data = payload.model_dump(exclude_unset=True)

    if "password" in update_data:
        from app.auth.hashing import hash_password
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return current_user

@router.get("/{user_id}", response_model=UserOut)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Fetch any user by ID. Admin only."""
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_roles("admin")),
):
    """Soft-delete (deactivate) a user account. Admin only."""
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    db.add(user)
    await db.commit()
