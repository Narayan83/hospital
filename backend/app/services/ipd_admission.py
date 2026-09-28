from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ipd_admission import IpdAdmission
from app.repositories.ipd_admission import IpdAdmissionRepository
from app.repositories.patient import PatientRepository
from app.schemas.ipd_admission import IpdAdmissionCreate, IpdAdmissionRead
from app.services.bill_number import BillNumberService


class IpdAdmissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IpdAdmissionRepository(session)
        self.patient_repo = PatientRepository(session)
        self.number_svc = BillNumberService(session)

    def _to_read(self, admission: IpdAdmission) -> IpdAdmissionRead:
        patient_name = None
        patient_no = None
        if admission.patient:
            patient_no = admission.patient.patient_no
            parts = [
                admission.patient.first_name,
                admission.patient.middle_name,
                admission.patient.last_name,
            ]
            patient_name = " ".join(p for p in parts if p)
        read = IpdAdmissionRead.model_validate(admission)
        return read.model_copy(
            update={
                "patient_no": patient_no,
                "patient_name": patient_name,
                "ward_name": admission.ward.name if admission.ward else None,
                "doctor_name": admission.doctor.full_name if admission.doctor else None,
                "department_name": admission.department.name if admission.department else None,
            }
        )

    async def create_admission(self, data: IpdAdmissionCreate) -> IpdAdmissionRead:
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        admission_no = await self.number_svc.generate_ipd_admission_no()
        admission = IpdAdmission(
            admission_no=admission_no,
            admission_date=data.admission_date or date.today(),
            patient_id=data.patient_id,
            ward_id=data.ward_id,
            doctor_id=data.doctor_id,
            department_id=data.department_id,
            bed_no=data.bed_no,
            advance_amount=data.advance_amount,
            diagnosis=data.diagnosis,
            remarks=data.remarks,
            status="admitted",
            is_active=True,
        )
        self.session.add(admission)
        await self.session.flush()
        saved = await self.repo.get_with_details(admission.id)
        return self._to_read(saved)  # type: ignore[arg-type]

    async def get_admission(self, admission_id: str) -> IpdAdmissionRead:
        admission = await self.repo.get_with_details(admission_id)
        if not admission or not admission.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        return self._to_read(admission)

    async def get_admission_by_no(self, admission_no: str) -> IpdAdmissionRead:
        admission = await self.repo.get_by_admission_no(admission_no.strip().upper())
        if not admission or not admission.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        full = await self.repo.get_with_details(admission.id)
        return self._to_read(full)  # type: ignore[arg-type]

    async def list_admissions(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        patient_id: str | None = None,
    ) -> list[IpdAdmissionRead]:
        rows = await self.repo.list_admissions(
            status=status, search=search, patient_id=patient_id
        )
        return [self._to_read(row) for row in rows]
