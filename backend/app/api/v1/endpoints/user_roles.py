from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.user_mgmt import UserRoleAssign, UserRoleMappingRead
from app.services.user_role import UserRoleService

router = APIRouter()


@router.get("", response_model=list[UserRoleMappingRead])
async def list_user_roles(
    user_id: str = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserRoleService(session).list_for_user(user_id)


@router.post("", response_model=UserRoleMappingRead, status_code=201)
async def assign_role(
    data: UserRoleAssign,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserRoleService(session).assign(data)


@router.delete("/{mapping_id}", status_code=204)
async def remove_role(
    mapping_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await UserRoleService(session).remove(mapping_id)
