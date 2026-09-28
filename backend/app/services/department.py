from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.repositories.department import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate


class DepartmentService:
    def __init__(self, session: AsyncSession):
        self.repo = DepartmentRepository(session)

    async def list_departments(self) -> list[DepartmentRead]:
        items = await self.repo.list_active()
        return [DepartmentRead.model_validate(item) for item in items]

    async def get_department(self, department_id: str) -> DepartmentRead:
        item = await self.repo.get_by_id(department_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        return DepartmentRead.model_validate(item)

    async def create_department(self, data: DepartmentCreate) -> DepartmentRead:
        raw_code = (data.code or "").strip()
        code = raw_code.upper() if raw_code else await self.repo.next_auto_code()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return DepartmentRead.model_validate(existing)

        item = Department(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return DepartmentRead.model_validate(item)

    async def update_department(self, department_id: str, data: DepartmentUpdate) -> DepartmentRead:
        item = await self.repo.get_by_id(department_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return DepartmentRead.model_validate(item)

    async def delete_department(self, department_id: str) -> DepartmentRead:
        item = await self.repo.get_by_id(department_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return DepartmentRead.model_validate(item)
