from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RoleMenuPermissionRead,
    RolePermissionsUpdate,
    RoleRead,
    RoleUpdate,
)
from app.services.role_mgmt import RoleManagementService

router = APIRouter()


@router.get("", response_model=list[RoleRead])
async def list_roles(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await RoleManagementService(session).list_roles()


@router.post("", response_model=RoleRead, status_code=201)
async def create_role(
    data: RoleCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await RoleManagementService(session).create_role(data)


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: str,
    data: RoleUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await RoleManagementService(session).update_role(role_id, data)


@router.get("/{role_id}/permissions", response_model=list[RoleMenuPermissionRead])
async def get_role_permissions(
    role_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await RoleManagementService(session).get_permissions(role_id)


@router.put("/{role_id}/permissions")
async def set_role_permissions(
    role_id: str,
    data: RolePermissionsUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await RoleManagementService(session).set_permissions(role_id, data)
