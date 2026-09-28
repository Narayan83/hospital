from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.print_config import PrintConfig
from app.repositories.print_config import PrintConfigRepository
from app.schemas.print_config import PrintConfigCreate, PrintConfigRead, PrintConfigUpdate


class PrintConfigService:
    def __init__(self, session: AsyncSession):
        self.repo = PrintConfigRepository(session)

    async def list_configs(self) -> list[PrintConfigRead]:
        items = await self.repo.list_active()
        return [PrintConfigRead.model_validate(item) for item in items]

    async def get_config(self, config_id: str) -> PrintConfigRead:
        item = await self.repo.get_by_id(config_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Print config not found")
        return PrintConfigRead.model_validate(item)

    async def get_config_by_code(self, code: str) -> PrintConfigRead:
        item = await self.repo.get_by_code(code)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Print config not found")
        return PrintConfigRead.model_validate(item)

    async def create_config(self, data: PrintConfigCreate) -> PrintConfigRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Print config code already exists",
                )
            self._apply_create_fields(existing, data)
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return PrintConfigRead.model_validate(existing)

        item = PrintConfig(
            code=code,
            name=data.name.strip(),
            printer_name=(data.printer_name.strip() if data.printer_name else None),
            paper_size=data.paper_size,
            custom_width_mm=data.custom_width_mm,
            custom_height_mm=data.custom_height_mm,
            orientation=data.orientation,
            print_mode=data.print_mode,
            margin_top_mm=data.margin_top_mm,
            margin_right_mm=data.margin_right_mm,
            margin_bottom_mm=data.margin_bottom_mm,
            margin_left_mm=data.margin_left_mm,
            copies=data.copies,
            sort_order=data.sort_order,
            is_active=True,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrintConfigRead.model_validate(item)

    async def update_config(self, config_id: str, data: PrintConfigUpdate) -> PrintConfigRead:
        item = await self.repo.get_by_id(config_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Print config not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            elif field == "printer_name":
                value = value.strip() if value else None
            setattr(item, field, value)
        if item.paper_size == "CUSTOM" and (not item.custom_width_mm or not item.custom_height_mm):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom width and height (mm) are required for CUSTOM paper size",
            )
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrintConfigRead.model_validate(item)

    async def delete_config(self, config_id: str) -> PrintConfigRead:
        item = await self.repo.get_by_id(config_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Print config not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return PrintConfigRead.model_validate(item)

    @staticmethod
    def _apply_create_fields(item: PrintConfig, data: PrintConfigCreate) -> None:
        item.name = data.name.strip()
        item.printer_name = data.printer_name.strip() if data.printer_name else None
        item.paper_size = data.paper_size
        item.custom_width_mm = data.custom_width_mm
        item.custom_height_mm = data.custom_height_mm
        item.orientation = data.orientation
        item.print_mode = data.print_mode
        item.margin_top_mm = data.margin_top_mm
        item.margin_right_mm = data.margin_right_mm
        item.margin_bottom_mm = data.margin_bottom_mm
        item.margin_left_mm = data.margin_left_mm
        item.copies = data.copies
        item.sort_order = data.sort_order
