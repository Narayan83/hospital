from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.repositories.base import BaseRepository
from app.schemas.doctor import DoctorCreate, DoctorUpdate


class DoctorRepository(BaseRepository[Doctor]):
    model = Doctor

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _query(self):
        return select(Doctor).options(selectinload(Doctor.department))

    async def list_all_active(self, *, limit: int = 500) -> list[Doctor]:
        result = await self.session.execute(
            self._query()
            .where(Doctor.is_active.is_(True))
            .order_by(Doctor.doctor_code)
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[Doctor], int]:
        query = self._query()
        if active_only:
            query = query.where(Doctor.is_active.is_(True))

        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Doctor.doctor_code.ilike(term),
                    Doctor.first_name.ilike(term),
                    Doctor.second_name.ilike(term),
                    Doctor.third_name.ilike(term),
                    Doctor.register_no.ilike(term),
                    Doctor.mobile.ilike(term),
                    Doctor.phone.ilike(term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        query = query.order_by(Doctor.doctor_code).offset((page - 1) * page_size).limit(page_size)

        items_result = await self.session.execute(query)
        count_result = await self.session.execute(count_query)
        return list(items_result.scalars().unique().all()), int(count_result.scalar_one())

    async def get_by_id(self, record_id: str) -> Doctor | None:
        result = await self.session.execute(self._query().where(Doctor.id == record_id))
        return result.scalar_one_or_none()

    async def create(self, data: DoctorCreate, doctor_code: str) -> Doctor:
        doctor = Doctor(doctor_code=doctor_code, **data.model_dump())
        self.session.add(doctor)
        await self.session.flush()
        return await self.get_by_id(doctor.id)  # type: ignore[return-value]

    async def update(self, doctor: Doctor, data: DoctorUpdate) -> Doctor:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(doctor, field, value)
        await self.session.flush()
        return await self.get_by_id(doctor.id)  # type: ignore[return-value]

    async def deactivate(self, doctor: Doctor) -> Doctor:
        doctor.is_active = False
        await self.session.flush()
        return await self.get_by_id(doctor.id)  # type: ignore[return-value]

    async def get_next_sequence(self) -> int:
        result = await self.session.execute(select(Doctor.doctor_code))
        numbers = [
            int(code.replace("D", ""))
            for (code,) in result.all()
            if code and code.startswith("D") and code[1:].isdigit()
        ]
        return max(numbers, default=0) + 1
