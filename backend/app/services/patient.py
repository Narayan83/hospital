import math

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.hospital_section import HospitalSectionRepository
from app.repositories.patient import PatientRepository
from app.schemas.common import PaginatedResponse
from app.schemas.patient import PatientCreate, PatientNoPreview, PatientRead, PatientSearchFilters, PatientUpdate
from app.services.patient_files import save_patient_aadhar_scan
from app.services.patient_number import PatientNumberService


class PatientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatientRepository(session)
        self.section_repo = HospitalSectionRepository(session)
        self.number_svc = PatientNumberService(session)

    async def list_patients(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> PaginatedResponse[PatientRead]:
        items, total = await self.repo.list(page=page, page_size=page_size, search=search)
        pages = math.ceil(total / page_size) if page_size else 0
        enriched = []
        for item in items:
            read = PatientRead.model_validate(item)
            if item.hospital_section_id:
                section = await self.section_repo.get_by_id(item.hospital_section_id)
                if section:
                    read = read.model_copy(update={"hospital_section_name": section.name})
            enriched.append(read)
        return PaginatedResponse(
            items=enriched,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def search_patients(self, filters: PatientSearchFilters) -> PaginatedResponse[PatientRead]:
        items, total = await self.repo.advanced_search(
            patient_no=filters.patient_no,
            first_name=filters.first_name,
            middle_name=filters.middle_name,
            last_name=filters.last_name,
            village=filters.village,
            post=filters.post,
            taluk=filters.taluk,
            district=filters.district,
            phone=filters.phone,
            mobile=filters.mobile,
            mobile2=filters.mobile2,
            pin_code=filters.pin_code,
            old_id=filters.old_id,
            aadhar_no=filters.aadhar_no,
            page=filters.page,
            page_size=filters.page_size,
            active_only=filters.active_only,
        )
        pages = math.ceil(total / filters.page_size) if filters.page_size else 0
        enriched = []
        for item in items:
            read = PatientRead.model_validate(item)
            if item.hospital_section_id:
                section = await self.section_repo.get_by_id(item.hospital_section_id)
                if section:
                    read = read.model_copy(update={"hospital_section_name": section.name})
            enriched.append(read)
        return PaginatedResponse(
            items=enriched,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=pages,
        )

    async def get_patient(self, patient_id: str) -> PatientRead:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        read = PatientRead.model_validate(patient)
        if patient.hospital_section_id:
            section = await self.section_repo.get_by_id(patient.hospital_section_id)
            if section:
                read = read.model_copy(update={"hospital_section_name": section.name})
        return read

    async def _resolve_facility(self, data: PatientCreate | PatientUpdate) -> str | None:
        section_id = getattr(data, "hospital_section_id", None)
        if section_id:
            section = await self.section_repo.get_by_id(section_id)
            if section:
                return section.name
        return getattr(data, "facility", None)

    async def preview_next_patient_no(
        self, hospital_section_id: str | None = None
    ) -> PatientNoPreview:
        return await self.number_svc.preview_next(hospital_section_id=hospital_section_id)

    async def create_patient(self, data: PatientCreate) -> PatientRead:
        patient_no = await self.number_svc.generate_next(
            hospital_section_id=data.hospital_section_id
        )
        payload = data.model_dump()
        payload["facility"] = await self._resolve_facility(data)
        patient = await self.repo.create(PatientCreate(**payload), patient_no=patient_no)
        return await self.get_patient(patient.id)

    async def update_patient(self, patient_id: str, data: PatientUpdate) -> PatientRead:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        payload = data.model_dump(exclude_unset=True)
        if data.hospital_section_id is not None:
            section = await self.section_repo.get_by_id(data.hospital_section_id)
            payload["facility"] = section.name if section else data.facility
        updated = await self.repo.update(patient, PatientUpdate(**payload))
        return await self.get_patient(updated.id)

    async def upload_aadhar_scan(self, patient_id: str, upload: UploadFile) -> PatientRead:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        patient.aadhar_scan_path = await save_patient_aadhar_scan(patient_id, upload)
        await self.session.flush()
        return await self.get_patient(patient_id)
