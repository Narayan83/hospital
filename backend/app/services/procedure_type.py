from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procedure_type import ProcedureType
from app.repositories.procedure_type import ProcedureTypeRepository
from app.schemas.procedure_type import ProcedureTypeCreate, ProcedureTypeRead, ProcedureTypeUpdate


class ProcedureTypeService:
    def __init__(self, session: AsyncSession):
        self.repo = ProcedureTypeRepository(session)

    async def list_procedure_types(self) -> list[ProcedureTypeRead]:
        items = await self.repo.list_active()
        return [ProcedureTypeRead.model_validate(item) for item in items]

    async def get_procedure_type(self, procedure_type_id: str) -> ProcedureTypeRead:
        item = await self.repo.get_by_id(procedure_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure type not found")
        return ProcedureTypeRead.model_validate(item)

    async def create_procedure_type(self, data: ProcedureTypeCreate) -> ProcedureTypeRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Procedure type code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return ProcedureTypeRead.model_validate(existing)

        item = ProcedureType(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ProcedureTypeRead.model_validate(item)

    async def update_procedure_type(
        self, procedure_type_id: str, data: ProcedureTypeUpdate
    ) -> ProcedureTypeRead:
        item = await self.repo.get_by_id(procedure_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure type not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ProcedureTypeRead.model_validate(item)

    async def delete_procedure_type(self, procedure_type_id: str) -> ProcedureTypeRead:
        item = await self.repo.get_by_id(procedure_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure type not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return ProcedureTypeRead.model_validate(item)
