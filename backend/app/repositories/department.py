from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    model = Department

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[Department]:
        result = await self.session.execute(
            select(Department)
            .where(Department.is_active.is_(True))
            .order_by(Department.sort_order, Department.name)
        )
        return list(result.scalars().all())

    async def next_auto_code(self) -> str:
        """Next department code as a plain number (max numeric code + 1, else count + 1)."""
        result = await self.session.execute(select(Department.code))
        codes = [str(code).strip() for code in result.scalars().all() if code]
        nums = [int(code) for code in codes if code.isdigit()]
        if nums:
            return str(max(nums) + 1)
        return str(len(codes) + 1)

    async def get_by_code(self, code: str) -> Department | None:
        result = await self.session.execute(select(Department).where(Department.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, department_id: str) -> Department | None:
        result = await self.session.execute(select(Department).where(Department.id == department_id))
        return result.scalar_one_or_none()