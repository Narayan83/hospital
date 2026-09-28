from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hospital_section import HospitalSection
from app.repositories.hospital_section import HospitalSectionRepository
from app.schemas.hospital_section import (
    HospitalSectionCreate,
    HospitalSectionRead,
    HospitalSectionUpdate,
)


class HospitalSectionService:
    def __init__(self, session: AsyncSession):
        self.repo = HospitalSectionRepository(session)

    async def list_sections(self) -> list[HospitalSectionRead]:
        items = await self.repo.list_active()
        return [HospitalSectionRead.model_validate(item) for item in items]

    async def get_section(self, section_id: str) -> HospitalSectionRead:
        item = await self.repo.get_by_id(section_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital section not found")
        return HospitalSectionRead.model_validate(item)

    async def create_section(self, data: HospitalSectionCreate) -> HospitalSectionRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Hospital section code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return HospitalSectionRead.model_validate(existing)

        item = HospitalSection(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return HospitalSectionRead.model_validate(item)

    async def update_section(self, section_id: str, data: HospitalSectionUpdate) -> HospitalSectionRead:
        item = await self.repo.get_by_id(section_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital section not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return HospitalSectionRead.model_validate(item)

    async def delete_section(self, section_id: str) -> HospitalSectionRead:
        item = await self.repo.get_by_id(section_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital section not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return HospitalSectionRead.model_validate(item)
