from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.opd_bill import OpdBill
from app.models.opd_token import OpdToken
from app.repositories.opd_token import OpdTokenRepository
from app.schemas.opd_bill import SCHEDULED_VISIT_CATEGORIES
from app.schemas.opd_token import OpdTokenRead


class OpdTokenService:
    """Issue numeric tokens per doctor + date + session + visit type.

    Each queue starts at 1 and increments (1, 2, 3…). Queues are separate for
    OPD, Reference, Appointment, and Online Booking, and for morning vs evening.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OpdTokenRepository(session)

    def _to_read(self, token: OpdToken) -> OpdTokenRead:
        patient_name = None
        patient_no = None
        if token.patient:
            patient_no = token.patient.patient_no
            parts = [
                token.patient.first_name,
                token.patient.middle_name,
                token.patient.last_name,
            ]
            patient_name = " ".join(p for p in parts if p)
        return OpdTokenRead.model_validate(token).model_copy(
            update={
                "doctor_name": token.doctor.full_name if token.doctor else None,
                "patient_no": patient_no,
                "patient_name": patient_name,
            }
        )

    @staticmethod
    def _max_slots(doctor: Doctor, visit_category: str) -> int:
        if visit_category == "appointment":
            return doctor.appointment_token_end
        if visit_category == "online_booking":
            return doctor.online_booking_token_end
        raise ValueError(f"Not a scheduled visit category: {visit_category}")

    async def issue_token(
        self,
        *,
        doctor: Doctor,
        patient_id: str,
        bill_id: str,
        bill_no: str,
        visit_category: str,
        token_session: str,
        bill_date: date,
        appointment_date: date | None,
    ) -> OpdToken:
        if visit_category in SCHEDULED_VISIT_CATEGORIES:
            if not appointment_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Booking date is required",
                )
            token_date = appointment_date
            max_slots = self._max_slots(doctor, visit_category)
            if max_slots < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor {visit_category.replace('_', ' ')} slot limit is not configured",
                )
        else:
            token_date = bill_date
            max_slots = None

        # Lock this queue for the transaction so concurrent bill saves
        # cannot both pick the same next token_number.
        await self.repo.lock_slot(
            doctor_id=doctor.id,
            visit_category=visit_category,
            token_session=token_session,
            token_date=token_date,
        )

        if max_slots is not None:
            count = await self.repo.count_active(
                doctor_id=doctor.id,
                visit_category=visit_category,
                token_session=token_session,
                token_date=token_date,
            )
            if count >= max_slots:
                label = "Online booking" if visit_category == "online_booking" else "Appointment"
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{label} slots full for this doctor on {token_date} ({token_session})",
                )

        token_number = await self.repo.next_token_number(
            doctor_id=doctor.id,
            visit_category=visit_category,
            token_session=token_session,
            token_date=token_date,
        )

        token = OpdToken(
            doctor_id=doctor.id,
            patient_id=patient_id,
            bill_id=bill_id,
            bill_no=bill_no,
            token_number=token_number,
            token_date=token_date,
            token_session=token_session,
            visit_category=visit_category,
            is_active=True,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def sync_for_bill(
        self,
        *,
        bill: "OpdBill",
        doctor: Doctor,
        token_session: str,
        visit_category: str,
        appointment_date: date | None,
    ) -> OpdToken:
        token_date = (
            appointment_date
            if visit_category in SCHEDULED_VISIT_CATEGORIES and appointment_date
            else bill.bill_date
        )
        existing = await self.repo.get_by_bill_id(bill.id)
        if existing:
            unchanged = (
                existing.doctor_id == doctor.id
                and existing.token_session == token_session
                and existing.visit_category == visit_category
                and existing.token_date == token_date
            )
            if unchanged:
                return existing
            existing.is_active = False
            await self.session.flush()

        return await self.issue_token(
            doctor=doctor,
            patient_id=bill.patient_id,
            bill_id=bill.id,
            bill_no=bill.bill_no,
            visit_category=visit_category,
            token_session=token_session,
            bill_date=bill.bill_date,
            appointment_date=appointment_date,
        )

    async def list_tokens(
        self,
        *,
        doctor_id: str | None = None,
        token_date: date | None = None,
        token_session: str | None = None,
        visit_category: str | None = None,
    ) -> list[OpdTokenRead]:
        rows = await self.repo.list_tokens(
            doctor_id=doctor_id,
            token_date=token_date,
            token_session=token_session,
            visit_category=visit_category,
        )
        return [self._to_read(row) for row in rows]
