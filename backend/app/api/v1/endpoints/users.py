from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.user_mgmt import UserCreate, UserRead, UserUpdate
from app.services.user_mgmt import UserManagementService

router = APIRouter()


@router.get("", response_model=list[UserRead])
async def list_users(
    active_only: bool = Query(True),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserManagementService(session).list_users(active_only=active_only)


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    data: UserCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserManagementService(session).create_user(data)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    data: UserUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserManagementService(session).update_user(user_id, data)


@router.delete("/{user_id}", response_model=UserRead)
async def delete_user(
    user_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserManagementService(session).delete_user(user_id)
