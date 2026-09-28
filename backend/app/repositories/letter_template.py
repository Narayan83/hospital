from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.letter_template import LetterTemplate
from app.repositories.base import BaseRepository


class LetterTemplateRepository(BaseRepository[LetterTemplate]):
    model = LetterTemplate

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[LetterTemplate]:
        result = await self.session.execute(
            select(LetterTemplate)
            .where(LetterTemplate.is_active.is_(True))
            .order_by(LetterTemplate.sort_order, LetterTemplate.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> LetterTemplate | None:
        result = await self.session.execute(
            select(LetterTemplate).where(LetterTemplate.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, letter_id: str) -> LetterTemplate | None:
        result = await self.session.execute(
            select(LetterTemplate).where(LetterTemplate.id == letter_id)
        )
        return result.scalar_one_or_none()
