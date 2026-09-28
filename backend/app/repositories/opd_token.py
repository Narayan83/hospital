from datetime import date
from hashlib import md5

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.opd_token import OpdToken
from app.repositories.base import BaseRepository


class OpdTokenRepository(BaseRepository[OpdToken]):
    model = OpdToken

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    @staticmethod
    def _slot_lock_keys(
        *,
        doctor_id: str,
        visit_category: str,
        token_session: str,
        token_date: date,
    ) -> tuple[int, int]:
        payload = f"{doctor_id}|{token_date.isoformat()}|{token_session}|{visit_category}"
        digest = md5(payload.encode("utf-8")).digest()
        key1 = int.from_bytes(digest[:4], "big", signed=True)
        key2 = int.from_bytes(digest[4:8], "big", signed=True)
        return key1, key2

    async def lock_slot(
        self,
        *,
        doctor_id: str,
        visit_category: str,
        token_session: str,
        token_date: date,
    ) -> None:
        """Serialize token issuance for one doctor/date/session/category queue."""
        key1, key2 = self._slot_lock_keys(
            doctor_id=doctor_id,
            visit_category=visit_category,
            token_session=token_session,
            token_date=token_date,
        )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
            {"k1": key1, "k2": key2},
        )

    def _slot_filters(
        self,
        *,
        doctor_id: str,
        visit_category: str,
        token_session: str,
        token_date: date,
    ):
        return (
            OpdToken.doctor_id == doctor_id,
            OpdToken.visit_category == visit_category,
            OpdToken.token_session == token_session,
            OpdToken.token_date == token_date,
        )

    async def count_active(
        self,
        *,
        doctor_id: str,
        visit_category: str,
        token_session: str,
        token_date: date,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(OpdToken)
            .where(OpdToken.is_active.is_(True))
            .where(*self._slot_filters(
                doctor_id=doctor_id,
                visit_category=visit_category,
                token_session=token_session,
                token_date=token_date,
            ))
        )
        return int(result.scalar_one())

    async def next_token_number(
        self,
        *,
        doctor_id: str,
        visit_category: str,
        token_session: str,
        token_date: date,
    ) -> int:
        """Next number for the slot. Uses MAX over all rows (active or not)
        because uq_opd_token_slot still applies to deactivated tokens.
        """
        result = await self.session.execute(
            select(func.coalesce(func.max(OpdToken.token_number), 0))
            .select_from(OpdToken)
            .where(*self._slot_filters(
                doctor_id=doctor_id,
                visit_category=visit_category,
                token_session=token_session,
                token_date=token_date,
            ))
        )
        return int(result.scalar_one()) + 1

    async def list_tokens(
        self,
        *,
        doctor_id: str | None = None,
        token_date: date | None = None,
        token_session: str | None = None,
        visit_category: str | None = None,
    ) -> list[OpdToken]:
        stmt = (
            select(OpdToken)
            .options(
                selectinload(OpdToken.doctor),
                selectinload(OpdToken.patient),
            )
            .where(OpdToken.is_active.is_(True))
        )
        if doctor_id:
            stmt = stmt.where(OpdToken.doctor_id == doctor_id)
        if token_date:
            stmt = stmt.where(OpdToken.token_date == token_date)
        if token_session:
            stmt = stmt.where(OpdToken.token_session == token_session)
        if visit_category:
            stmt = stmt.where(OpdToken.visit_category == visit_category)
        stmt = stmt.order_by(
            OpdToken.token_date.desc(),
            OpdToken.token_session,
            OpdToken.visit_category,
            OpdToken.token_number,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_bill_id(self, bill_id: str) -> OpdToken | None:
        result = await self.session.execute(
            select(OpdToken)
            .where(OpdToken.bill_id == bill_id)
            .where(OpdToken.is_active.is_(True))
        )
        return result.scalar_one_or_none()
