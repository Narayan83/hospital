from datetime import date, datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_document import PatientDocument, PatientDocumentView
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.repositories.patient_document import PatientDocumentRepository
from app.schemas.patient_document import PatientDocumentCreate, PatientDocumentRead, PatientDocumentViewRead
from app.services.patient_document_files import save_patient_document_pdf


class PatientDocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatientDocumentRepository(session)
        self.patient_repo = PatientRepository(session)

    def _patient_name(self, patient) -> str | None:
        if not patient:
            return None
        parts = [patient.first_name, patient.middle_name, patient.last_name]
        return " ".join(p for p in parts if p)

    def _to_read(
        self,
        doc: PatientDocument,
        *,
        doctor_id: str | None = None,
    ) -> PatientDocumentRead:
        viewed = None
        viewed_flag = False
        if doctor_id and doc.views:
            for view in doc.views:
                if view.doctor_id == doctor_id:
                    viewed_flag = True
                    viewed = view.viewed_at
                    break
        return PatientDocumentRead.model_validate(doc).model_copy(
            update={
                "patient_no": doc.patient.patient_no if doc.patient else None,
                "patient_name": self._patient_name(doc.patient),
                "scanned_by_name": doc.scanned_by.full_name if doc.scanned_by else None,
                "viewed_by_current_doctor": viewed_flag,
                "viewed_at": viewed,
            }
        )

    async def list_documents(
        self,
        *,
        patient_id: str,
        doctor_id: str | None = None,
    ) -> list[PatientDocumentRead]:
        patient = await self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        rows = await self.repo.list_by_patient(patient_id=patient_id)
        return [self._to_read(row, doctor_id=doctor_id) for row in rows]

    async def upload_document(
        self,
        *,
        data: PatientDocumentCreate,
        upload: UploadFile,
        user: User,
    ) -> PatientDocumentRead:
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        file_path, file_size = await save_patient_document_pdf(data.patient_id, upload)
        doc = PatientDocument(
            patient_id=data.patient_id,
            file_path=file_path,
            original_name=data.original_name or upload.filename,
            document_type="patient_document",
            page_count=data.page_count,
            file_size_bytes=file_size,
            scanner_name=data.scanner_name,
            scanned_by_user_id=user.id,
            document_date=data.document_date or date.today(),
            remarks=data.remarks,
            is_active=True,
        )
        self.session.add(doc)
        await self.session.flush()
        loaded = await self.repo.get_with_relations(doc.id)
        return self._to_read(loaded)  # type: ignore[arg-type]

    async def get_document(self, document_id: str, *, doctor_id: str | None = None) -> PatientDocumentRead:
        doc = await self.repo.get_with_relations(document_id)
        if not doc or not doc.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return self._to_read(doc, doctor_id=doctor_id)

    async def mark_viewed(self, document_id: str, *, doctor_id: str) -> PatientDocumentViewRead:
        doc = await self.repo.get_with_relations(document_id)
        if not doc or not doc.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        existing = await self.repo.get_view(document_id=document_id, doctor_id=doctor_id)
        if existing:
            return PatientDocumentViewRead.model_validate(existing)

        view = PatientDocumentView(
            document_id=document_id,
            doctor_id=doctor_id,
            viewed_at=datetime.now(timezone.utc),
        )
        self.session.add(view)
        await self.session.flush()
        return PatientDocumentViewRead.model_validate(view)
