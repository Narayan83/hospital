from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_note import ServiceNote
from app.repositories.service_note import ServiceNoteRepository
from app.schemas.service_note import ServiceNoteCreate, ServiceNoteRead, ServiceNoteUpdate


class ServiceNoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ServiceNoteRepository(session)

    async def list_notes(self) -> list[ServiceNoteRead]:
        items = await self.repo.list_active()
        return [ServiceNoteRead.model_validate(i) for i in items]

    async def create_note(self, data: ServiceNoteCreate) -> ServiceNoteRead:
        existing = await self.repo.get_by_code(data.service_code)
        if existing:
            # One note per service (and one general note) — update in place.
            existing.note_text = data.note_text.strip()
            existing.is_active = True
            await self.session.flush()
            return ServiceNoteRead.model_validate(existing)
        item = ServiceNote(
            service_code=data.service_code,
            note_text=data.note_text.strip(),
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        return ServiceNoteRead.model_validate(item)

    async def update_note(self, note_id: str, data: ServiceNoteUpdate) -> ServiceNoteRead:
        item = await self.repo.get_by_id(note_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        payload = data.model_dump(exclude_unset=True)
        if "service_code" in payload:
            item.service_code = payload["service_code"]
        if "note_text" in payload and payload["note_text"] is not None:
            item.note_text = payload["note_text"].strip()
        if "is_active" in payload and payload["is_active"] is not None:
            item.is_active = payload["is_active"]
        await self.session.flush()
        return ServiceNoteRead.model_validate(item)

    async def delete_note(self, note_id: str) -> ServiceNoteRead:
        item = await self.repo.get_by_id(note_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        item.is_active = False
        await self.session.flush()
        return ServiceNoteRead.model_validate(item)
