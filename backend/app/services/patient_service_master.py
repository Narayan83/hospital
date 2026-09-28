from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.patient_service_master import (
    PatientServiceMasterCreate,
    PatientServiceMasterRead,
    PatientServiceMasterUpdate,
)


class PatientServiceMasterService:
    PATHOLOGY_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatientServiceMasterRepository(session)

    def _to_read(self, item: PatientServiceMaster) -> PatientServiceMasterRead:
        read = PatientServiceMasterRead.model_validate(item)
        if item.doctor:
            read = read.model_copy(update={"doctor_name": item.doctor.full_name})
        if item.category:
            read = read.model_copy(update={"category_name": item.category.name})
        if item.sub_category:
            read = read.model_copy(update={"sub_category_name": item.sub_category.name})
        return read

    async def list_services(self) -> list[PatientServiceMasterRead]:
        items = await self.repo.list_active(
            exclude_category_codes=(self.PATHOLOGY_CATEGORY_CODE,)
        )
        return [self._to_read(item) for item in items]

    async def _ensure_patient_service_category(self, category_id: str | None) -> None:
        if not category_id:
            return
        category = (
            await self.session.execute(
                select(ServiceCategory).where(ServiceCategory.id == category_id)
            )
        ).scalar_one_or_none()
        if category and category.code == self.PATHOLOGY_CATEGORY_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pathology services must be managed from Pathology, not Patient Service Master",
            )

    async def get_service(self, service_id: str) -> PatientServiceMasterRead:
        item = await self.repo.get_by_id(service_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        await self._ensure_patient_service_category(item.category_id)
        return self._to_read(item)

    async def create_service(self, data: PatientServiceMasterCreate) -> PatientServiceMasterRead:
        raw_code = (data.code or "").strip()
        code = raw_code.upper() if raw_code else await self.repo.next_auto_code()
        await self._ensure_patient_service_category(data.category_id)
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Service code already exists",
                )
            for field, value in data.model_dump().items():
                if field == "code":
                    continue
                if field == "name" and value is not None:
                    value = value.strip()
                setattr(existing, field, value)
            if not existing.is_sharing:
                existing.doctor_id = None
            if not existing.is_renewal:
                existing.renewal_days = None
            if existing.is_service_active:
                existing.close_date = None
            self._validate_item(existing)
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            item = await self.repo.get_by_id(existing.id)
            return self._to_read(item)  # type: ignore[arg-type]

        item = PatientServiceMaster(
            code=code,
            name=data.name.strip(),
            **data.model_dump(exclude={"code", "name"}),
        )
        self._validate_item(item)
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        loaded = await self.repo.get_by_id(item.id)
        return self._to_read(loaded)  # type: ignore[arg-type]

    def _validate_item(self, item: PatientServiceMaster) -> None:
        if item.is_sharing and not item.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is required when sharing is enabled",
            )
        if item.is_renewal and item.renewal_days is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Renewal days is required when renewal is enabled",
            )
        if not item.is_service_active and not item.close_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Close date is required when status is closed",
            )

    async def update_service(
        self, service_id: str, data: PatientServiceMasterUpdate
    ) -> PatientServiceMasterRead:
        item = await self.repo.get_by_id(service_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self._ensure_patient_service_category(item.category_id)
        if not item.is_sharing:
            item.doctor_id = None
        if not item.is_renewal:
            item.renewal_days = None
        if item.is_service_active:
            item.close_date = None
        self._validate_item(item)

        await self.repo.session.flush()
        loaded = await self.repo.get_by_id(item.id)
        return self._to_read(loaded)  # type: ignore[arg-type]

    async def delete_service(self, service_id: str) -> PatientServiceMasterRead:
        item = await self.repo.get_by_id(service_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        await self._ensure_patient_service_category(item.category_id)
        item.is_active = False
        await self.repo.session.flush()
        loaded = await self.repo.get_by_id(item.id)
        return self._to_read(loaded)  # type: ignore[arg-type]
