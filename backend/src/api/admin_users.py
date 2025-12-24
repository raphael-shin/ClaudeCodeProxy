from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..domain import UserCreate, UserResponse, UserStatus
from ..repositories import UserRepository, AccessKeyRepository
from ..proxy import invalidate_access_key_cache
from .deps import require_admin

router = APIRouter(prefix="/admin/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserResponse])
async def list_users(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    users = await repo.list_active(limit=limit, offset=offset)
    return [UserResponse(**u.__dict__) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.create(name=data.name, description=data.description)
    await session.commit()
    return UserResponse(**user.__dict__)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user or user.status == UserStatus.DELETED:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user.__dict__)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    key_repo = AccessKeyRepository(session)

    user = await user_repo.get_by_id(user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="User not found or not active")

    # Get all keys before revoking to invalidate cache
    keys = await key_repo.list_by_user(user_id)

    await user_repo.update_status(user_id, UserStatus.INACTIVE)
    await key_repo.revoke_all_for_user(user_id)
    await session.commit()

    # Invalidate cache for all user's keys
    for key in keys:
        invalidate_access_key_cache(key.key_hash)

    user = await user_repo.get_by_id(user_id)
    return UserResponse(**user.__dict__)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    key_repo = AccessKeyRepository(session)

    user = await user_repo.get_by_id(user_id)
    if not user or user.status == UserStatus.DELETED:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all keys before revoking to invalidate cache
    keys = await key_repo.list_by_user(user_id)

    await user_repo.update_status(user_id, UserStatus.DELETED)
    await key_repo.revoke_all_for_user(user_id)
    await session.commit()

    # Invalidate cache for all user's keys
    for key in keys:
        invalidate_access_key_cache(key.key_hash)
