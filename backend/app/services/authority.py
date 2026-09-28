from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.authority import Authority
from app.repositories.authority import AuthorityRepository
from app.schemas.authority import AuthorityCreate, AuthorityRead, AuthorityUpdate


class AuthorityService:
    def __init__(self, session: AsyncSession):
        self.repo = AuthorityRepository(session)

    async def list_authorities(self) -> list[AuthorityRead]:
        items = await self.repo.list_active()
        return [AuthorityRead.model_validate(item) for item in items]

    async def get_authority(self, authority_id: str) -> AuthorityRead:
        item = await self.repo.get_by_id(authority_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        return AuthorityRead.model_validate(item)

    async def create_authority(self, data: AuthorityCreate) -> AuthorityRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authority code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return AuthorityRead.model_validate(existing)

        item = Authority(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return AuthorityRead.model_validate(item)

    async def update_authority(self, authority_id: str, data: AuthorityUpdate) -> AuthorityRead:
        item = await self.repo.get_by_id(authority_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return AuthorityRead.model_validate(item)

    async def delete_authority(self, authority_id: str) -> AuthorityRead:
        item = await self.repo.get_by_id(authority_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return AuthorityRead.model_validate(item)
