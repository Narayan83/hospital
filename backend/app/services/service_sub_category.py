from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_sub_category import ServiceSubCategory
from app.repositories.service_category import ServiceCategoryRepository
from app.repositories.service_sub_category import ServiceSubCategoryRepository
from app.schemas.service_sub_category import (
    ServiceSubCategoryCreate,
    ServiceSubCategoryRead,
    ServiceSubCategoryUpdate,
)


class ServiceSubCategoryService:
    def __init__(self, session: AsyncSession):
        self.repo = ServiceSubCategoryRepository(session)
        self.category_repo = ServiceCategoryRepository(session)

    def _to_read(self, item: ServiceSubCategory) -> ServiceSubCategoryRead:
        read = ServiceSubCategoryRead.model_validate(item)
        if item.category:
            read = read.model_copy(
                update={
                    "category_code": item.category.code,
                    "category_name": item.category.name,
                }
            )
        return read

    async def list_sub_categories(
        self, category_id: str | None = None
    ) -> list[ServiceSubCategoryRead]:
        items = await self.repo.list_active(category_id=category_id)
        return [self._to_read(item) for item in items]

    async def get_sub_category(self, sub_category_id: str) -> ServiceSubCategoryRead:
        item = await self.repo.get_by_id(sub_category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub category not found")
        loaded = await self.repo.list_active(category_id=item.category_id)
        match = next((row for row in loaded if row.id == sub_category_id), item)
        return self._to_read(match)

    async def create_sub_category(self, data: ServiceSubCategoryCreate) -> ServiceSubCategoryRead:
        category = await self.category_repo.get_by_id(data.category_id)
        if not category or not category.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
        code = data.code.strip().upper()
        existing = await self.repo.get_by_category_code(data.category_id, code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sub category code already exists for this category",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return self._to_read(existing)

        item = ServiceSubCategory(
            category_id=data.category_id,
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=True,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        item.category = category
        return self._to_read(item)

    async def update_sub_category(
        self, sub_category_id: str, data: ServiceSubCategoryUpdate
    ) -> ServiceSubCategoryRead:
        item = await self.repo.get_by_id(sub_category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub category not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        return await self.get_sub_category(sub_category_id)

    async def delete_sub_category(self, sub_category_id: str) -> ServiceSubCategoryRead:
        item = await self.repo.get_by_id(sub_category_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub category not found")
        read = await self.get_sub_category(sub_category_id)
        item.is_active = False
        await self.repo.session.flush()
        return read.model_copy(update={"is_active": False})
