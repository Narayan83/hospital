from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pathology_result_template import PathologyResultTemplate
from app.repositories.base import BaseRepository


class PathologyResultTemplateRepository(BaseRepository[PathologyResultTemplate]):
    model = PathologyResultTemplate

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[PathologyResultTemplate]:
        result = await self.session.execute(
            select(PathologyResultTemplate)
            .options(
                selectinload(PathologyResultTemplate.parameter),
                selectinload(PathologyResultTemplate.service),
            )
            .where(PathologyResultTemplate.is_active.is_(True))
            .order_by(PathologyResultTemplate.sort_order, PathologyResultTemplate.name)
        )
        return list(result.scalars().all())

    async def list_for_result(
        self,
        *,
        parameter_id: str | None = None,
        service_id: str | None = None,
    ) -> list[PathologyResultTemplate]:
        stmt = (
            select(PathologyResultTemplate)
            .options(
                selectinload(PathologyResultTemplate.parameter),
                selectinload(PathologyResultTemplate.service),
            )
            .where(PathologyResultTemplate.is_active.is_(True))
        )
        if parameter_id:
            stmt = stmt.where(
                or_(
                    PathologyResultTemplate.parameter_id.is_(None),
                    PathologyResultTemplate.parameter_id == parameter_id,
                )
            )
        if service_id:
            stmt = stmt.where(
                or_(
                    PathologyResultTemplate.service_id.is_(None),
                    PathologyResultTemplate.service_id == service_id,
                )
            )
        stmt = stmt.order_by(PathologyResultTemplate.sort_order, PathologyResultTemplate.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_by_code(self, code: str) -> PathologyResultTemplate | None:
        result = await self.session.execute(
            select(PathologyResultTemplate).where(PathologyResultTemplate.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, template_id: str) -> PathologyResultTemplate | None:
        result = await self.session.execute(
            select(PathologyResultTemplate)
            .options(
                selectinload(PathologyResultTemplate.parameter),
                selectinload(PathologyResultTemplate.service),
            )
            .where(PathologyResultTemplate.id == template_id)
        )
        return result.scalar_one_or_none()
