from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_type import UserType
from app.repositories.user_type import UserTypeRepository
from app.schemas.user_type import UserTypeCreate, UserTypeRead, UserTypeUpdate


class UserTypeService:
    def __init__(self, session: AsyncSession):
        self.repo = UserTypeRepository(session)

    async def list_user_types(self) -> list[UserTypeRead]:
        types = await self.repo.list_active()
        return [UserTypeRead.model_validate(item) for item in types]

    async def create_user_type(self, data: UserTypeCreate) -> UserTypeRead:
        code = data.code.strip().lower()
        existing = await self.repo.get_by_code(code)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User type code already exists")
        item = UserType(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            maps_to_doctor=data.maps_to_doctor,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        return UserTypeRead.model_validate(item)

    async def update_user_type(self, user_type_id: str, data: UserTypeUpdate) -> UserTypeRead:
        item = await self.repo.get_by_id(user_type_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User type not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.repo.session.flush()
        return UserTypeRead.model_validate(item)
