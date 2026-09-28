from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ipd_admission import IpdAdmission
from app.models.ipd_discharge_summary import IpdDischargeSummary
from app.repositories.ipd_admission import IpdAdmissionRepository
from app.repositories.ipd_discharge_summary import IpdDischargeSummaryRepository
from app.repositories.patient import PatientRepository
from app.schemas.ipd_discharge_summary import (
    IpdDischargeSummaryCreate,
    IpdDischargeSummaryListRead,
    IpdDischargeSummaryRead,
    IpdDischargeSummaryUpdate,
)
from app.services.bill_number import BillNumberService


class IpdDischargeSummaryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IpdDischargeSummaryRepository(session)
        self.admission_repo = IpdAdmissionRepository(session)
        self.patient_repo = PatientRepository(session)
        self.number_svc = BillNumberService(session)

    @staticmethod
    def _patient_name_from_admission(admission: IpdAdmission) -> tuple[str | None, str | None]:
        if not admission.patient:
            return None, None
        patient_no = admission.patient.patient_no
        parts = [
            admission.patient.first_name,
            admission.patient.middle_name,
            admission.patient.last_name,
        ]
        patient_name = " ".join(p for p in parts if p)
        return patient_no, patient_name

    @staticmethod
    def _patient_age_gender(admission: IpdAdmission) -> tuple[str | None, str | None]:
        if not admission.patient:
            return None, None
        age = admission.patient.age
        gender = admission.patient.gender
        return (str(age) if age is not None else None, gender)

    @staticmethod
    def _stay_days_between(admission_date: date | None, discharge_date: date | None) -> int | None:
        if not admission_date or not discharge_date:
            return None
        return max((discharge_date - admission_date).days + 1, 1)

    @staticmethod
    def _stay_days(admission: IpdAdmission) -> int | None:
        if not admission.admission_date:
            return None
        discharge = admission.discharge_date or date.today()
        return IpdDischargeSummaryService._stay_days_between(admission.admission_date, discharge)

    @staticmethod
    def _patient_from_record(patient: Any) -> tuple[str | None, str | None, str | None, str | None]:
        if not patient:
            return None, None, None, None
        patient_no = getattr(patient, "patient_no", None)
        parts = [
            getattr(patient, "first_name", None),
            getattr(patient, "middle_name", None),
            getattr(patient, "last_name", None),
        ]
        patient_name = " ".join(p for p in parts if p)
        age = getattr(patient, "age", None)
        gender = getattr(patient, "gender", None)
        return (
            patient_no,
            patient_name or None,
            str(age) if age is not None else None,
            gender,
        )

    def _resolve_patient_display(
        self, summary: IpdDischargeSummary
    ) -> tuple[str | None, str | None, str | None, str | None]:
        if summary.patient:
            return self._patient_from_record(summary.patient)
        admission = summary.admission
        if admission and admission.patient:
            return self._patient_from_record(admission.patient)
        return None, None, None, None

    def _to_read(self, summary: IpdDischargeSummary) -> IpdDischargeSummaryRead:
        admission = summary.admission
        patient_no, patient_name, patient_age, patient_gender = self._resolve_patient_display(summary)
        doctor_name = summary.doctor.full_name if summary.doctor else None
        if not doctor_name and admission and admission.doctor:
            doctor_name = admission.doctor.full_name

        read = IpdDischargeSummaryRead.model_validate(summary)
        admission_date = summary.admission_date
        discharge_date = summary.discharge_date
        return read.model_copy(
            update={
                "admission_no": admission.admission_no if admission else None,
                "patient_no": patient_no,
                "patient_name": patient_name,
                "patient_age": patient_age,
                "patient_gender": patient_gender,
                "ward_name": admission.ward.name if admission and admission.ward else None,
                "bed_no": admission.bed_no if admission else None,
                "department_name": admission.department.name if admission and admission.department else None,
                "admission_date": admission_date,
                "discharge_date": discharge_date,
                "stay_days": self._stay_days_between(admission_date, discharge_date),
                "doctor_name": doctor_name,
            }
        )

    def _to_list_read(self, summary: IpdDischargeSummary) -> IpdDischargeSummaryListRead:
        admission = summary.admission
        patient_no, patient_name, _, _ = self._resolve_patient_display(summary)
        doctor_name = summary.doctor.full_name if summary.doctor else None
        if not doctor_name and admission and admission.doctor:
            doctor_name = admission.doctor.full_name
        return IpdDischargeSummaryListRead(
            id=summary.id,
            summary_no=summary.summary_no,
            summary_date=summary.summary_date,
            admission_no=admission.admission_no if admission else None,
            patient_no=patient_no,
            patient_name=patient_name,
            doctor_name=doctor_name,
            final_diagnosis=summary.final_diagnosis,
            discharge_date=summary.discharge_date,
            created_at=summary.created_at,
        )

    async def _get_admission(self, admission_id: str) -> IpdAdmission:
        admission = await self.admission_repo.get_with_details(admission_id)
        if not admission or not admission.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        return admission

    async def create_summary(self, data: IpdDischargeSummaryCreate) -> IpdDischargeSummaryRead:
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        admission = None
        admission_id = None
        if data.include_admission_details:
            if not data.admission_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admission is required when admission details are enabled",
                )
            admission = await self._get_admission(data.admission_id)
            if admission.patient_id != patient.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admission does not belong to the selected patient",
                )
            existing = await self.repo.get_by_admission_id(data.admission_id)
            if existing and existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Discharge summary already exists for this admission",
                )
            admission_id = admission.id
        elif data.admission_id:
            admission = await self._get_admission(data.admission_id)
            if admission.patient_id != patient.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admission does not belong to the selected patient",
                )
            admission_id = admission.id

        summary_date = data.summary_date or data.discharge_date
        if data.discharge_date < data.admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge date cannot be before admission date",
            )
        summary_no = await self.number_svc.generate_discharge_summary_no(summary_date)

        summary = IpdDischargeSummary(
            summary_no=summary_no,
            summary_date=summary_date,
            admission_date=data.admission_date,
            discharge_date=data.discharge_date,
            admission_id=admission_id,
            patient_id=patient.id,
            doctor_id=data.doctor_id,
            include_admission_details=data.include_admission_details,
            chief_complaint=data.chief_complaint,
            history_of_illness=data.history_of_illness,
            diagnosis_on_admission=data.diagnosis_on_admission
            or (admission.diagnosis if admission else None),
            final_diagnosis=data.final_diagnosis,
            investigation=data.investigation,
            treatment_given=data.treatment_given,
            procedures=data.procedures,
            condition_on_discharge=data.condition_on_discharge,
            medications_on_discharge=data.medications_on_discharge,
            advice_follow_up=data.advice_follow_up,
            remarks=data.remarks,
            is_active=True,
        )
        self.session.add(summary)
        await self.session.flush()
        saved = await self.repo.get_with_details(summary.id)
        return self._to_read(saved)  # type: ignore[arg-type]

    async def get_summary(self, summary_id: str) -> IpdDischargeSummaryRead:
        summary = await self.repo.get_with_details(summary_id)
        if not summary or not summary.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")
        return self._to_read(summary)

    async def get_summary_by_no(self, summary_no: str) -> IpdDischargeSummaryRead:
        summary = await self.repo.get_by_summary_no(summary_no)
        if not summary or not summary.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")
        full = await self.repo.get_with_details(summary.id)
        return self._to_read(full)  # type: ignore[arg-type]

    async def get_summary_by_admission(self, admission_id: str) -> IpdDischargeSummaryRead:
        summary = await self.repo.get_by_admission_id(admission_id)
        if not summary or not summary.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")
        full = await self.repo.get_with_details(summary.id)
        return self._to_read(full)  # type: ignore[arg-type]

    async def update_summary(self, summary_id: str, data: IpdDischargeSummaryUpdate) -> IpdDischargeSummaryRead:
        summary = await self.repo.get_with_details(summary_id)
        if not summary or not summary.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")

        updates = data.model_dump(exclude_unset=True)
        include_admission = updates.get("include_admission_details", summary.include_admission_details)
        admission_id = updates.get("admission_id", summary.admission_id)

        if include_admission and not admission_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admission is required when admission details are enabled",
            )
        if "admission_id" in updates and updates["admission_id"]:
            admission = await self._get_admission(updates["admission_id"])
            if admission.patient_id != summary.patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admission does not belong to the selected patient",
                )
            if updates["admission_id"] != summary.admission_id:
                existing = await self.repo.get_by_admission_id(updates["admission_id"])
                if existing and existing.is_active and existing.id != summary.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Discharge summary already exists for this admission",
                    )
        if include_admission is False:
            updates["admission_id"] = None

        admission_date = updates.get("admission_date", summary.admission_date)
        discharge_date = updates.get("discharge_date", summary.discharge_date)
        if discharge_date < admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge date cannot be before admission date",
            )

        for field, value in updates.items():
            setattr(summary, field, value)
        await self.session.flush()
        saved = await self.repo.get_with_details(summary.id)
        return self._to_read(saved)  # type: ignore[arg-type]

    async def list_summaries(
        self,
        *,
        search: str | None = None,
        patient_id: str | None = None,
        patient_no: str | None = None,
        admission_id: str | None = None,
    ) -> list[IpdDischargeSummaryListRead]:
        resolved_patient_id = patient_id
        if patient_no and not resolved_patient_id:
            patient = await self.patient_repo.get_by_patient_no(patient_no.strip())
            if not patient:
                return []
            resolved_patient_id = patient.id
        rows = await self.repo.list_summaries(
            search=search,
            patient_id=resolved_patient_id,
            patient_no=patient_no if not resolved_patient_id else None,
            admission_id=admission_id,
        )
        return [self._to_list_read(row) for row in rows]
