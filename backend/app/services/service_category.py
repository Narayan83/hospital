from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_category import ServiceCategory
from app.repositories.service_category import ServiceCategoryRepository
from app.schemas.service_category import (
    ServiceCategoryCreate,
    ServiceCategoryRead,
    ServiceCategoryUpdate,
)


class ServiceCategoryService:
    def __init__(self, session: AsyncSession):
        self.repo = ServiceCategoryRepository(session)

    async def list_categories(self) -> list[ServiceCategoryRead]:
        items = await self.repo.list_active()
        return [ServiceCategoryRead.model_validate(item) for item in items]

    async def get_category(self, category_id: str) -> ServiceCategoryRead:
        item = await self.repo.get_by_id(category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return ServiceCategoryRead.model_validate(item)

    async def create_category(self, data: ServiceCategoryCreate) -> ServiceCategoryRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return ServiceCategoryRead.model_validate(existing)

        item = ServiceCategory(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=True,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ServiceCategoryRead.model_validate(item)

    async def update_category(
        self, category_id: str, data: ServiceCategoryUpdate
    ) -> ServiceCategoryRead:
        item = await self.repo.get_by_id(category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ServiceCategoryRead.model_validate(item)

    async def delete_category(self, category_id: str) -> ServiceCategoryRead:
        item = await self.repo.get_by_id(category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ServiceCategoryRead.model_validate(item)
