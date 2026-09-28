from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role
from app.models.role_menu_permission import RoleMenuPermission
from app.repositories.base import BaseRepository
from app.schemas.role import RoleCreate, RolePermissionsUpdate, RoleUpdate


class RoleRepository(BaseRepository[Role]):
    model = Role

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.role_name == name))
        return result.scalar_one_or_none()

    async def list_roles(self, active_only: bool = True) -> list[Role]:
        query = select(Role).order_by(Role.role_name)
        if active_only:
            query = query.where(Role.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, data: RoleCreate) -> Role:
        role = Role(**data.model_dump())
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def update(self, role: Role, data: RoleUpdate) -> Role:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(role, field, value)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def get_permissions(self, role_id: str) -> list[RoleMenuPermission]:
        result = await self.session.execute(
            select(RoleMenuPermission).where(RoleMenuPermission.role_id == role_id)
        )
        return list(result.scalars().all())

    async def set_permissions(self, role_id: str, data: RolePermissionsUpdate) -> list[RoleMenuPermission]:
        existing = await self.get_permissions(role_id)
        for row in existing:
            await self.session.delete(row)
        await self.session.flush()

        created: list[RoleMenuPermission] = []
        for item in data.permissions:
            perm = RoleMenuPermission(
                role_id=role_id,
                menu_id=item.menu_id,
                can_view=item.can_view,
                can_create=item.can_create,
                can_update=item.can_update,
                can_delete=item.can_delete,
            )
            self.session.add(perm)
            created.append(perm)
        await self.session.flush()
        return created

    async def get_with_permissions(self, role_id: str) -> Role | None:
        result = await self.session.execute(
            select(Role)
            .options(selectinload(Role.menu_permissions))
            .where(Role.id == role_id)
        )
        return result.scalar_one_or_none()
