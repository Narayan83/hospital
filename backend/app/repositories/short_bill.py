from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.short_bill import ShortBill, ShortBillType
from app.repositories.base import BaseRepository


class ShortBillTypeRepository(BaseRepository[ShortBillType]):
    model = ShortBillType

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[ShortBillType]:
        stmt = (
            select(ShortBillType)
            .options(
                selectinload(ShortBillType.default_service),
                selectinload(ShortBillType.default_doctor),
            )
            .where(ShortBillType.is_active.is_(True))
            .order_by(ShortBillType.sort_order, ShortBillType.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[ShortBillType]:
        stmt = (
            select(ShortBillType)
            .options(
                selectinload(ShortBillType.default_service),
                selectinload(ShortBillType.default_doctor),
            )
            .order_by(ShortBillType.sort_order, ShortBillType.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, type_id: str) -> ShortBillType | None:
        stmt = (
            select(ShortBillType)
            .options(
                selectinload(ShortBillType.default_service),
                selectinload(ShortBillType.default_doctor),
            )
            .where(ShortBillType.id == type_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_menu_code(self, menu_code: str) -> ShortBillType | None:
        stmt = (
            select(ShortBillType)
            .options(
                selectinload(ShortBillType.default_service),
                selectinload(ShortBillType.default_doctor),
            )
            .where(ShortBillType.menu_code == menu_code, ShortBillType.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_menu_any(self, menu_code: str) -> ShortBillType | None:
        stmt = select(ShortBillType).where(ShortBillType.menu_code == menu_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> ShortBillType | None:
        stmt = select(ShortBillType).where(ShortBillType.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ShortBillRepository(BaseRepository[ShortBill]):
    model = ShortBill

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_id(self, bill_id: str) -> ShortBill | None:
        stmt = (
            select(ShortBill)
            .options(
                selectinload(ShortBill.bill_type),
                selectinload(ShortBill.patient),
                selectinload(ShortBill.doctor),
            )
            .where(ShortBill.id == bill_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_for_type(self, type_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ShortBill)
            .where(ShortBill.short_bill_type_id == type_id, ShortBill.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def list_by_type_and_dates(
        self,
        type_id: str,
        from_date: date,
        to_date: date,
    ) -> list[ShortBill]:
        stmt = (
            select(ShortBill)
            .where(
                ShortBill.short_bill_type_id == type_id,
                ShortBill.is_active.is_(True),
                ShortBill.bill_date >= from_date,
                ShortBill.bill_date <= to_date,
            )
            .order_by(ShortBill.bill_date, ShortBill.bill_no)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, type_id: str, query: str, *, limit: int = 50) -> list[ShortBill]:
        text = query.strip()
        like = f"%{text}%"
        stmt = (
            select(ShortBill)
            .options(
                selectinload(ShortBill.bill_type),
                selectinload(ShortBill.patient),
                selectinload(ShortBill.doctor),
            )
            .where(
                ShortBill.short_bill_type_id == type_id,
                ShortBill.is_active.is_(True),
                or_(
                    ShortBill.bill_no.ilike(like),
                    ShortBill.patient_name.ilike(like),
                ),
            )
            .order_by(ShortBill.bill_date.desc(), ShortBill.bill_no.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
