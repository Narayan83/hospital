from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.doctor import DoctorRepository
from app.repositories.ipd_bill import IpdBillRepository
from app.repositories.opd_bill import OpdBillRepository
from app.repositories.patient import PatientRepository
from app.schemas.bill_identity import BillIdentityLookupRead, BillIdentityUpdate


class BillIdentityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.opd_repo = OpdBillRepository(session)
        self.ipd_repo = IpdBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.doctor_repo = DoctorRepository(session)

    async def lookup(self, *, bill_type: str, bill_no: str) -> BillIdentityLookupRead:
        bill_type = bill_type.strip().upper()
        bill_no = bill_no.strip()
        if bill_type == "OPD":
            bill = await self.opd_repo.get_by_bill_no(bill_no)
        elif bill_type == "IPD":
            bill = await self.ipd_repo.get_by_bill_no(bill_no)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bill_type must be OPD or IPD")
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        patient = bill.patient or await self.patient_repo.get_by_id(bill.patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        doctor_name = None
        if bill.doctor_id:
            doctor = await self.doctor_repo.get_by_id(bill.doctor_id)
            doctor_name = doctor.full_name if doctor else None

        patient_no = getattr(bill, "patient_no", None) or patient.patient_no
        return BillIdentityLookupRead(
            bill_type=bill_type,
            bill_id=bill.id,
            bill_no=bill.bill_no,
            bill_date=str(bill.bill_date) if bill.bill_date else None,
            patient_id=patient.id,
            patient_no=patient_no,
            title=patient.title,
            first_name=patient.first_name,
            middle_name=patient.middle_name,
            last_name=patient.last_name,
            doctor_id=bill.doctor_id,
            doctor_name=doctor_name,
            net_amount=float(bill.net_amount or 0),
        )

    async def update(self, data: BillIdentityUpdate) -> BillIdentityLookupRead:
        if not data.update_patient_name and not data.update_doctor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select patient name and/or doctor to update",
            )

        current = await self.lookup(bill_type=data.bill_type, bill_no=data.bill_no)

        if data.update_patient_name:
            if not data.first_name or not data.first_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="First name is required",
                )
            patient = await self.patient_repo.get_by_id(current.patient_id)
            if not patient or not patient.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            patient.title = (data.title or "").strip() or None
            patient.first_name = data.first_name.strip()
            patient.middle_name = (data.middle_name or "").strip() or None
            patient.last_name = (data.last_name or "").strip() or None

        if data.update_doctor:
            if not data.doctor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Select a doctor",
                )
            doctor = await self.doctor_repo.get_by_id(data.doctor_id)
            if not doctor or not doctor.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor not found")

            bill_type = data.bill_type.strip().upper()
            if bill_type == "OPD":
                bill = await self.opd_repo.get_by_bill_no(data.bill_no.strip())
            else:
                bill = await self.ipd_repo.get_by_bill_no(data.bill_no.strip())
            if not bill or not bill.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
            bill.doctor_id = data.doctor_id
            if doctor.department_id:
                bill.department_id = doctor.department_id

        await self.session.flush()
        return await self.lookup(bill_type=data.bill_type, bill_no=data.bill_no)
