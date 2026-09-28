from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash
from app.models.doctor import Doctor
from app.models.user import User
from app.models.user_role_mapping import UserRoleMapping
from app.models.user_type import UserType
from app.repositories.base import BaseRepository
from app.schemas.user_mgmt import UserCreate, UserUpdate


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _base_query(self):
        return select(User).options(
            selectinload(User.role_mappings).selectinload(UserRoleMapping.role),
            selectinload(User.user_type),
            selectinload(User.doctor),
        )

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(self._base_query().where(User.email == email))
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: str) -> User | None:
        result = await self.session.execute(self._base_query().where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_users(self, *, active_only: bool = True) -> list[User]:
        query = self._base_query().order_by(User.full_name)
        if active_only:
            query = query.where(User.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, data: UserCreate) -> User:
        user = User(
            email=data.email.lower(),
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            phone=data.phone,
            user_type_id=data.user_type_id,
            doctor_id=data.doctor_id,
            is_active=data.is_active,
        )
        self.session.add(user)
        await self.session.flush()
        return await self.get_with_roles(user.id)  # type: ignore[return-value]

    async def update(self, user: User, data: UserUpdate) -> User:
        payload = data.model_dump(exclude_unset=True)
        password = payload.pop("password", None)
        for field, value in payload.items():
            if field == "email" and value:
                value = value.lower()
            setattr(user, field, value)
        if password:
            user.hashed_password = get_password_hash(password)
        await self.session.flush()
        return await self.get_with_roles(user.id)  # type: ignore[return-value]

    async def deactivate(self, user: User) -> User:
        user.is_active = False
        await self.session.flush()
        return await self.get_with_roles(user.id)  # type: ignore[return-value]
