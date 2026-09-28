from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient_document import PatientDocument, PatientDocumentView
from app.repositories.base import BaseRepository


class PatientDocumentRepository(BaseRepository[PatientDocument]):
    model = PatientDocument

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _query(self):
        return select(PatientDocument).options(
            selectinload(PatientDocument.patient),
            selectinload(PatientDocument.scanned_by),
            selectinload(PatientDocument.views),
        )

    async def list_by_patient(self, *, patient_id: str, active_only: bool = True) -> list[PatientDocument]:
        stmt = self._query().where(PatientDocument.patient_id == patient_id)
        if active_only:
            stmt = stmt.where(PatientDocument.is_active.is_(True))
        stmt = stmt.order_by(PatientDocument.document_date.desc(), PatientDocument.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_with_relations(self, document_id: str) -> PatientDocument | None:
        result = await self.session.execute(self._query().where(PatientDocument.id == document_id))
        return result.scalar_one_or_none()

    async def get_view(self, *, document_id: str, doctor_id: str) -> PatientDocumentView | None:
        result = await self.session.execute(
            select(PatientDocumentView).where(
                PatientDocumentView.document_id == document_id,
                PatientDocumentView.doctor_id == doctor_id,
            )
        )
        return result.scalar_one_or_none()
