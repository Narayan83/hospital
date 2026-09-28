from sqlalchemy import select

from app.models.service_note import ServiceNote
from app.repositories.base import BaseRepository


class ServiceNoteRepository(BaseRepository[ServiceNote]):
    model = ServiceNote

    async def list_active(self) -> list[ServiceNote]:
        result = await self.session.execute(
            select(ServiceNote)
            .where(ServiceNote.is_active.is_(True))
            .order_by(ServiceNote.service_code.nullsfirst(), ServiceNote.created_at)
        )
        return list(result.scalars().all())

    async def get_by_code(self, service_code: str | None) -> ServiceNote | None:
        stmt = select(ServiceNote).where(ServiceNote.is_active.is_(True))
        if service_code:
            stmt = stmt.where(ServiceNote.service_code == service_code.upper())
        else:
            stmt = stmt.where(ServiceNote.service_code.is_(None))
        result = await self.session.execute(stmt.order_by(ServiceNote.created_at))
        return result.scalars().first()
