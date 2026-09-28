from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.letter_template import LetterTemplate
from app.repositories.letter_template import LetterTemplateRepository
from app.schemas.letter_template import LetterTemplateCreate, LetterTemplateRead, LetterTemplateUpdate


class LetterTemplateService:
    def __init__(self, session: AsyncSession):
        self.repo = LetterTemplateRepository(session)

    async def list_letters(self) -> list[LetterTemplateRead]:
        items = await self.repo.list_active()
        return [LetterTemplateRead.model_validate(item) for item in items]

    async def get_letter(self, letter_id: str) -> LetterTemplateRead:
        item = await self.repo.get_by_id(letter_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        return LetterTemplateRead.model_validate(item)

    async def create_letter(self, data: LetterTemplateCreate) -> LetterTemplateRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Letter code already exists",
                )
            existing.name = data.name.strip()
            existing.subject = data.subject.strip() if data.subject else None
            existing.body = data.body or ""
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return LetterTemplateRead.model_validate(existing)

        item = LetterTemplate(
            code=code,
            name=data.name.strip(),
            subject=data.subject.strip() if data.subject else None,
            body=data.body or "",
            sort_order=data.sort_order,
            is_active=True,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return LetterTemplateRead.model_validate(item)

    async def update_letter(self, letter_id: str, data: LetterTemplateUpdate) -> LetterTemplateRead:
        item = await self.repo.get_by_id(letter_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            elif field == "subject" and value is not None:
                value = value.strip() or None
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return LetterTemplateRead.model_validate(item)

    async def delete_letter(self, letter_id: str) -> LetterTemplateRead:
        item = await self.repo.get_by_id(letter_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return LetterTemplateRead.model_validate(item)
