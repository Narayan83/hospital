from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.role import RoleRepository
from app.schemas.role import (
    RoleCreate,
    RoleMenuPermissionRead,
    RolePermissionsUpdate,
    RoleRead,
    RoleUpdate,
)


class RoleManagementService:
    def __init__(self, session: AsyncSession):
        self.repo = RoleRepository(session)

    async def list_roles(self) -> list[RoleRead]:
        roles = await self.repo.list_roles(active_only=False)
        return [RoleRead.model_validate(r) for r in roles]

    async def create_role(self, data: RoleCreate) -> RoleRead:
        existing = await self.repo.get_by_name(data.role_name)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role name already exists")
        role = await self.repo.create(data)
        return RoleRead.model_validate(role)

    async def update_role(self, role_id: str, data: RoleUpdate) -> RoleRead:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        if data.role_name and data.role_name != role.role_name:
            existing = await self.repo.get_by_name(data.role_name)
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role name already exists")
        updated = await self.repo.update(role, data)
        return RoleRead.model_validate(updated)

    async def get_permissions(self, role_id: str) -> list[RoleMenuPermissionRead]:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        perms = await self.repo.get_permissions(role_id)
        return [
            RoleMenuPermissionRead(
                menu_id=p.menu_id,
                can_view=p.can_view,
                can_create=p.can_create,
                can_update=p.can_update,
                can_delete=p.can_delete,
            )
            for p in perms
        ]

    async def set_permissions(self, role_id: str, data: RolePermissionsUpdate) -> dict:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        perms = await self.repo.set_permissions(role_id, data)
        return {"updated": len(perms)}
