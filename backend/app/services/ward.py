from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ward import Ward
from app.repositories.ward import WardRepository
from app.schemas.ward import WardCreate, WardRead, WardUpdate


class WardService:
    def __init__(self, session: AsyncSession):
        self.repo = WardRepository(session)

    async def list_wards(self) -> list[WardRead]:
        items = await self.repo.list_active()
        return [WardRead.model_validate(item) for item in items]

    async def get_ward(self, ward_id: str) -> WardRead:
        item = await self.repo.get_by_id(ward_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        return WardRead.model_validate(item)

    async def create_ward(self, data: WardCreate) -> WardRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ward code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return WardRead.model_validate(existing)

        item = Ward(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return WardRead.model_validate(item)

    async def update_ward(self, ward_id: str, data: WardUpdate) -> WardRead:
        item = await self.repo.get_by_id(ward_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return WardRead.model_validate(item)

    async def delete_ward(self, ward_id: str) -> WardRead:
        item = await self.repo.get_by_id(ward_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return WardRead.model_validate(item)
