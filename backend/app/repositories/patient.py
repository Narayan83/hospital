from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.repositories.base import BaseRepository
from app.schemas.patient import PatientCreate, PatientUpdate


class PatientRepository(BaseRepository[Patient]):
    model = Patient

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_patient_no(self, patient_no: str) -> Patient | None:
        result = await self.session.execute(
            select(Patient).where(Patient.patient_no.ilike(patient_no.strip()))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[Patient], int]:
        query = select(Patient)
        count_query = select(func.count()).select_from(Patient)

        if active_only:
            query = query.where(Patient.is_active.is_(True))
            count_query = count_query.where(Patient.is_active.is_(True))

        if search:
            term = f"%{search.strip()}%"
            digit_term = self._digits(search.strip())
            conditions = [
                Patient.patient_no.ilike(term),
                Patient.first_name.ilike(term),
                Patient.middle_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.phone.ilike(term),
                Patient.mobile.ilike(term),
                Patient.mobile2.ilike(term),
                Patient.aadhar_no.ilike(term),
                Patient.old_software_id.ilike(term),
            ]
            if digit_term:
                digit_pattern = f"%{digit_term}%"
                conditions.extend(
                    [
                        Patient.phone.ilike(digit_pattern),
                        Patient.mobile.ilike(digit_pattern),
                        Patient.mobile2.ilike(digit_pattern),
                        Patient.aadhar_no.ilike(digit_pattern),
                    ]
                )
            condition = or_(*conditions)
            query = query.where(condition)
            count_query = count_query.where(condition)

        query = query.order_by(Patient.patient_no.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        items_result = await self.session.execute(query)
        count_result = await self.session.execute(count_query)
        items = list(items_result.scalars().all())
        total = count_result.scalar_one()
        return items, total

    @staticmethod
    def _ilike(value: str | None):
        if not value or not value.strip():
            return None
        return f"%{value.strip()}%"

    @staticmethod
    def _digits(value: str | None) -> str | None:
        if not value:
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        return digits or None

    def _contact_terms(self, *values: str | None) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or not value.strip():
                continue
            stripped = value.strip()
            for candidate in (stripped, self._digits(stripped)):
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                terms.append(candidate)
                if candidate.isdigit() and len(candidate) > 10:
                    last10 = candidate[-10:]
                    if last10 not in seen:
                        seen.add(last10)
                        terms.append(last10)
        return terms

    def _apply_contact_filter(self, query, count_query, phone, mobile, mobile2):
        terms = self._contact_terms(phone, mobile, mobile2)
        if not terms:
            return query, count_query
        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.append(
                or_(
                    Patient.phone.ilike(pattern),
                    Patient.mobile.ilike(pattern),
                    Patient.mobile2.ilike(pattern),
                )
            )
        contact_cond = conditions[0] if len(conditions) == 1 else or_(*conditions)
        return query.where(contact_cond), count_query.where(contact_cond)

    def _apply_aadhar_filter(self, query, count_query, aadhar_no: str | None):
        terms = self._contact_terms(aadhar_no)
        if not terms:
            return query, count_query
        conditions = [Patient.aadhar_no.ilike(f"%{term}%") for term in terms]
        aadhar_cond = conditions[0] if len(conditions) == 1 else or_(*conditions)
        return query.where(aadhar_cond), count_query.where(aadhar_cond)

    async def advanced_search(
        self,
        *,
        patient_no: str | None = None,
        first_name: str | None = None,
        middle_name: str | None = None,
        last_name: str | None = None,
        village: str | None = None,
        post: str | None = None,
        taluk: str | None = None,
        district: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        mobile2: str | None = None,
        pin_code: str | None = None,
        old_id: str | None = None,
        aadhar_no: str | None = None,
        page: int = 1,
        page_size: int = 50,
        active_only: bool = False,
    ) -> tuple[list[Patient], int]:
        query = select(Patient)
        count_query = select(func.count()).select_from(Patient)

        if active_only:
            query = query.where(Patient.is_active.is_(True))
            count_query = count_query.where(Patient.is_active.is_(True))

        filters = (
            (Patient.patient_no, self._ilike(patient_no)),
            (Patient.first_name, self._ilike(first_name)),
            (Patient.middle_name, self._ilike(middle_name)),
            (Patient.last_name, self._ilike(last_name)),
            (Patient.old_software_id, self._ilike(old_id)),
            (Patient.contact_address2, self._ilike(post)),
            (Patient.contact_address3, self._ilike(taluk)),
            (Patient.contact_address4, self._ilike(district)),
        )
        for column, term in filters:
            if term:
                query = query.where(column.ilike(term))
                count_query = count_query.where(column.ilike(term))

        query, count_query = self._apply_contact_filter(query, count_query, phone, mobile, mobile2)
        query, count_query = self._apply_aadhar_filter(query, count_query, aadhar_no)

        village_term = self._ilike(village)
        if village_term:
            village_cond = or_(
                Patient.village_code.ilike(village_term),
                Patient.contact_address1.ilike(village_term),
            )
            query = query.where(village_cond)
            count_query = count_query.where(village_cond)

        pin_term = self._ilike(pin_code)
        if pin_term:
            pin_cond = or_(
                Patient.contact_address5.ilike(pin_term),
                Patient.perm_address5.ilike(pin_term),
            )
            query = query.where(pin_cond)
            count_query = count_query.where(pin_cond)

        query = query.order_by(Patient.patient_no.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        items_result = await self.session.execute(query)
        count_result = await self.session.execute(count_query)
        return list(items_result.scalars().all()), count_result.scalar_one()

    async def create(self, data: PatientCreate, patient_no: str) -> Patient:
        patient = Patient(patient_no=patient_no, **data.model_dump())
        self.session.add(patient)
        await self.session.flush()
        await self.session.refresh(patient)
        return patient

    async def update(self, patient: Patient, data: PatientUpdate) -> Patient:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)
        await self.session.flush()
        await self.session.refresh(patient)
        return patient
