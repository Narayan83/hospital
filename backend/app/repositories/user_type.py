from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_type import UserType
from app.repositories.base import BaseRepository


class UserTypeRepository(BaseRepository[UserType]):
    model = UserType

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[UserType]:
        result = await self.session.execute(
            select(UserType)
            .where(UserType.is_active.is_(True))
            .order_by(UserType.sort_order, UserType.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> UserType | None:
        result = await self.session.execute(select(UserType).where(UserType.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_type_id: str) -> UserType | None:
        result = await self.session.execute(select(UserType).where(UserType.id == user_type_id))
        return result.scalar_one_or_none()
