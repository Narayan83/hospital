from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prefix import Prefix
from app.repositories.prefix import PrefixRepository
from app.schemas.prefix import PrefixCreate, PrefixRead, PrefixUpdate


class PrefixService:
    def __init__(self, session: AsyncSession):
        self.repo = PrefixRepository(session)

    async def list_prefixes(self) -> list[PrefixRead]:
        items = await self.repo.list_active()
        return [PrefixRead.model_validate(item) for item in items]

    async def get_prefix(self, prefix_id: str) -> PrefixRead:
        item = await self.repo.get_by_id(prefix_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prefix not found")
        return PrefixRead.model_validate(item)

    async def get_prefix_value(self, code: str, default: str) -> str:
        wanted = code.strip().upper()
        item = await self.repo.get_by_code(wanted)
        if item and item.is_active and item.prefix_value:
            return item.prefix_value.strip()
        if wanted == "PATIENT":
            for candidate in await self.repo.list_active():
                name = (candidate.name or "").upper()
                if candidate.prefix_value and (
                    candidate.code.upper() == "PATIENT" or "PATIENT" in name
                ):
                    return candidate.prefix_value.strip()
        return default

    async def create_prefix(self, data: PrefixCreate) -> PrefixRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prefix code already exists",
                )
            existing.name = data.name.strip()
            existing.prefix_value = data.prefix_value.strip().upper()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return PrefixRead.model_validate(existing)

        item = Prefix(
            code=code,
            name=data.name.strip(),
            prefix_value=data.prefix_value.strip().upper(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrefixRead.model_validate(item)

    async def update_prefix(self, prefix_id: str, data: PrefixUpdate) -> PrefixRead:
        item = await self.repo.get_by_id(prefix_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prefix not found")
        payload = data.model_dump(exclude_unset=True, exclude_none=True)
        if "name" in payload:
            item.name = payload["name"].strip()
        if "prefix_value" in payload:
            item.prefix_value = payload["prefix_value"].strip().upper()
        if "sort_order" in payload:
            item.sort_order = payload["sort_order"]
        if "is_active" in payload:
            item.is_active = payload["is_active"]
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrefixRead.model_validate(item)

    async def delete_prefix(self, prefix_id: str) -> PrefixRead:
        item = await self.repo.get_by_id(prefix_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prefix not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrefixRead.model_validate(item)
