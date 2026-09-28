from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_no_format import PatientNoFormat
from app.repositories.patient_no_format import PatientNoFormatRepository
from app.schemas.patient_no_format import (
    PatientNoFormatCreate,
    PatientNoFormatRead,
    PatientNoFormatUpdate,
)


class PatientNoFormatService:
    def __init__(self, session: AsyncSession):
        self.repo = PatientNoFormatRepository(session)

    async def list_formats(self) -> list[PatientNoFormatRead]:
        items = await self.repo.list_active()
        return [PatientNoFormatRead.model_validate(item) for item in items]

    async def get_format(self, format_id: str) -> PatientNoFormatRead:
        item = await self.repo.get_by_id(format_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient number format not found")
        return PatientNoFormatRead.model_validate(item)

    async def _apply_selected(self, item: PatientNoFormat, selected: bool) -> None:
        if selected:
            await self.repo.clear_selected()
            item.is_selected = True
        elif item.is_selected:
            item.is_selected = False

    async def create_format(self, data: PatientNoFormatCreate) -> PatientNoFormatRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Patient number format code already exists",
                )
            existing.name = data.name.strip()
            existing.pattern = data.pattern
            existing.sample_output = data.sample_output.strip()
            existing.seq_pad_width = data.seq_pad_width
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self._apply_selected(existing, data.is_selected)
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return PatientNoFormatRead.model_validate(existing)

        item = PatientNoFormat(
            code=code,
            name=data.name.strip(),
            pattern=data.pattern,
            sample_output=data.sample_output.strip(),
            seq_pad_width=data.seq_pad_width,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self._apply_selected(item, data.is_selected)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PatientNoFormatRead.model_validate(item)

    async def update_format(self, format_id: str, data: PatientNoFormatUpdate) -> PatientNoFormatRead:
        item = await self.repo.get_by_id(format_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient number format not found")
        payload = data.model_dump(exclude_unset=True)
        selected = payload.pop("is_selected", None)
        for field, value in payload.items():
            if field == "name" and value is not None:
                value = value.strip()
            if field == "sample_output" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        if selected is not None:
            await self._apply_selected(item, selected)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PatientNoFormatRead.model_validate(item)

    async def delete_format(self, format_id: str) -> PatientNoFormatRead:
        item = await self.repo.get_by_id(format_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient number format not found")
        if item.is_selected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the selected patient number format",
            )
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PatientNoFormatRead.model_validate(item)
