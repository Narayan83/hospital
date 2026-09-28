import math

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.doctor import DoctorRepository
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorUpdate
from app.services.doctor_files import save_doctor_file


class DoctorService:
    def __init__(self, session: AsyncSession):
        self.repo = DoctorRepository(session)

    def _to_read(self, doctor) -> DoctorRead:
        payload = DoctorRead.model_validate(doctor)
        if doctor.department:
            payload = payload.model_copy(update={"department_name": doctor.department.name})
        return payload

    async def list_doctors_for_cache(self, *, limit: int = 500) -> list[DoctorRead]:
        items = await self.repo.list_all_active(limit=limit)
        return [self._to_read(item) for item in items]

    async def list_doctors(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        active_only: bool = True,
    ) -> PaginatedResponse[DoctorRead]:
        items, total = await self.repo.list(
            page=page,
            page_size=page_size,
            search=search,
            active_only=active_only,
        )
        pages = math.ceil(total / page_size) if page_size else 0
        return PaginatedResponse(
            items=[self._to_read(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_doctor(self, doctor_id: str) -> DoctorRead:
        doctor = await self.repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return self._to_read(doctor)

    async def create_doctor(self, data: DoctorCreate) -> DoctorRead:
        seq = await self.repo.get_next_sequence()
        doctor_code = f"D{seq:04d}"
        doctor = await self.repo.create(data, doctor_code=doctor_code)
        return self._to_read(doctor)

    async def update_doctor(self, doctor_id: str, data: DoctorUpdate) -> DoctorRead:
        doctor = await self.repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        updated = await self.repo.update(doctor, data)
        return self._to_read(updated)

    async def delete_doctor(self, doctor_id: str) -> DoctorRead:
        doctor = await self.repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        deactivated = await self.repo.deactivate(doctor)
        return self._to_read(deactivated)

    async def upload_photo(self, doctor_id: str, upload: UploadFile) -> DoctorRead:
        doctor = await self.repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        doctor.photo_path = await save_doctor_file(doctor_id, upload, kind="photo")
        await self.repo.session.flush()
        return self._to_read(await self.repo.get_by_id(doctor_id))  # type: ignore[arg-type]

    async def upload_certificate(self, doctor_id: str, upload: UploadFile) -> DoctorRead:
        doctor = await self.repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        doctor.certificate_path = await save_doctor_file(doctor_id, upload, kind="certificate")
        await self.repo.session.flush()
        return self._to_read(await self.repo.get_by_id(doctor_id))  # type: ignore[arg-type]
