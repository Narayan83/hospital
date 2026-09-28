from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user_role_mapping import UserRoleMapping
from app.repositories.base import BaseRepository
from app.schemas.user_mgmt import UserRoleAssign


class UserRoleRepository(BaseRepository[UserRoleMapping]):
    model = UserRoleMapping

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_for_user(self, user_id: str) -> list[UserRoleMapping]:
        result = await self.session.execute(
            select(UserRoleMapping)
            .options(selectinload(UserRoleMapping.role))
            .where(UserRoleMapping.user_id == user_id)
            .order_by(UserRoleMapping.priority.desc())
        )
        return list(result.scalars().all())

    async def assign(self, data: UserRoleAssign) -> UserRoleMapping:
        result = await self.session.execute(
            select(UserRoleMapping).where(
                UserRoleMapping.user_id == data.user_id,
                UserRoleMapping.role_id == data.role_id,
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping:
            mapping.priority = data.priority
        else:
            mapping = UserRoleMapping(**data.model_dump())
            self.session.add(mapping)
        await self.session.flush()
        await self.session.refresh(mapping)
        return mapping

    async def remove(self, mapping_id: str) -> None:
        mapping = await self.get_by_id(mapping_id)
        if mapping:
            await self.session.delete(mapping)
