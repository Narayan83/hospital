from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pharmacy import (
    PharmacyItem,
    PharmacyPurchaseBill,
    PharmacyPurchaseBillLine,
    PharmacySaleBill,
    PharmacySaleBillLine,
)
from app.repositories.base import BaseRepository


class PharmacySaleBillRepository(BaseRepository[PharmacySaleBill]):
    model = PharmacySaleBill

    async def get_with_lines(self, bill_id: str) -> PharmacySaleBill | None:
        result = await self.session.execute(
            select(PharmacySaleBill)
            .options(selectinload(PharmacySaleBill.lines))
            .where(PharmacySaleBill.id == bill_id, PharmacySaleBill.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_date_range(
        self, from_date: date, to_date: date
    ) -> list[PharmacySaleBill]:
        result = await self.session.execute(
            select(PharmacySaleBill)
            .options(selectinload(PharmacySaleBill.lines))
            .where(
                PharmacySaleBill.is_active.is_(True),
                PharmacySaleBill.bill_date >= from_date,
                PharmacySaleBill.bill_date <= to_date,
            )
            .order_by(PharmacySaleBill.bill_date.desc(), PharmacySaleBill.bill_no.desc())
        )
        return list(result.scalars().all())

    async def get_last_bill_no(self) -> str | None:
        result = await self.session.execute(
            select(PharmacySaleBill.bill_no)
            .where(PharmacySaleBill.is_active.is_(True))
            .order_by(PharmacySaleBill.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class PharmacyPurchaseBillRepository(BaseRepository[PharmacyPurchaseBill]):
    model = PharmacyPurchaseBill

    async def get_with_lines(self, bill_id: str) -> PharmacyPurchaseBill | None:
        result = await self.session.execute(
            select(PharmacyPurchaseBill)
            .options(selectinload(PharmacyPurchaseBill.lines))
            .where(PharmacyPurchaseBill.id == bill_id, PharmacyPurchaseBill.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_date_range(
        self, from_date: date, to_date: date
    ) -> list[PharmacyPurchaseBill]:
        result = await self.session.execute(
            select(PharmacyPurchaseBill)
            .options(selectinload(PharmacyPurchaseBill.lines))
            .where(
                PharmacyPurchaseBill.is_active.is_(True),
                PharmacyPurchaseBill.bill_date >= from_date,
                PharmacyPurchaseBill.bill_date <= to_date,
            )
            .order_by(PharmacyPurchaseBill.bill_date.desc(), PharmacyPurchaseBill.bill_no.desc())
        )
        return list(result.scalars().all())


async def purchased_qty_by_item(session: AsyncSession) -> dict[str, int]:
    """Net purchased qty (purchases minus supplier returns)."""
    signed_qty = func.sum(
        case(
            (PharmacyPurchaseBill.bill_kind == "return", -PharmacyPurchaseBillLine.quantity),
            else_=PharmacyPurchaseBillLine.quantity,
        )
    )
    result = await session.execute(
        select(
            PharmacyPurchaseBillLine.item_id,
            func.coalesce(signed_qty, 0),
        )
        .join(PharmacyPurchaseBill, PharmacyPurchaseBillLine.bill_id == PharmacyPurchaseBill.id)
        .where(PharmacyPurchaseBill.is_active.is_(True))
        .group_by(PharmacyPurchaseBillLine.item_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def sold_qty_by_item(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(
        select(
            PharmacySaleBillLine.item_id,
            func.coalesce(func.sum(PharmacySaleBillLine.quantity), 0),
        )
        .join(PharmacySaleBill, PharmacySaleBillLine.bill_id == PharmacySaleBill.id)
        .where(PharmacySaleBill.is_active.is_(True))
        .group_by(PharmacySaleBillLine.item_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def sales_summary_by_item(
    session: AsyncSession, from_date: date, to_date: date
) -> list[tuple[str, str, int, float]]:
    result = await session.execute(
        select(
            PharmacySaleBillLine.item_code,
            PharmacySaleBillLine.item_name,
            func.coalesce(func.sum(PharmacySaleBillLine.quantity), 0),
            func.coalesce(func.sum(PharmacySaleBillLine.amount), 0),
        )
        .join(PharmacySaleBill, PharmacySaleBillLine.bill_id == PharmacySaleBill.id)
        .where(
            PharmacySaleBill.is_active.is_(True),
            PharmacySaleBill.bill_date >= from_date,
            PharmacySaleBill.bill_date <= to_date,
        )
        .group_by(PharmacySaleBillLine.item_code, PharmacySaleBillLine.item_name)
        .order_by(PharmacySaleBillLine.item_name)
    )
    return list(result.all())


async def schedule_h_sales(
    session: AsyncSession, from_date: date, to_date: date
) -> list[tuple]:
    result = await session.execute(
        select(
            PharmacySaleBill.bill_no,
            PharmacySaleBill.bill_date,
            PharmacySaleBill.patient_name,
            PharmacySaleBillLine.item_code,
            PharmacySaleBillLine.item_name,
            PharmacySaleBillLine.schedule,
            PharmacySaleBillLine.quantity,
            PharmacySaleBillLine.amount,
        )
        .join(PharmacySaleBillLine, PharmacySaleBillLine.bill_id == PharmacySaleBill.id)
        .where(
            PharmacySaleBill.is_active.is_(True),
            PharmacySaleBill.bill_date >= from_date,
            PharmacySaleBill.bill_date <= to_date,
            PharmacySaleBillLine.schedule.in_(["H", "H1", "X"]),
        )
        .order_by(PharmacySaleBill.bill_date.desc(), PharmacySaleBill.bill_no.desc())
    )
    return list(result.all())


async def list_active_items(session: AsyncSession) -> list[PharmacyItem]:
    result = await session.execute(
        select(PharmacyItem)
        .where(PharmacyItem.is_active.is_(True))
        .order_by(PharmacyItem.item_type, PharmacyItem.name)
    )
    return list(result.scalars().all())
