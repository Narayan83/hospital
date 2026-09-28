from datetime import date
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ipd_bill import IpdBill
from app.models.opd_bill import OpdBill
from app.models.pathology_bill import PathologyBill
from app.models.user import User
from app.schemas.cancellation_bill_report import (
    CancellationBillReportRead,
    CancellationBillReportRow,
)

_CANCEL_RE = re.compile(r"CANCELLED:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_BILL_TYPES = {"all", "opd", "ipd", "pathology"}


class CancellationBillReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _patient_name(patient) -> str:
        if not patient:
            return "—"
        return (
            " ".join(
                part
                for part in (patient.first_name, patient.middle_name, patient.last_name)
                if part
            ).strip()
            or "—"
        )

    @staticmethod
    def _cancellation_remarks(remarks: str | None) -> str:
        text = (remarks or "").strip()
        if not text:
            return "—"
        matches = _CANCEL_RE.findall(text)
        if matches:
            # Prefer the last CANCELLED: note (most recent append).
            return matches[-1].strip() or "—"
        return text

    @staticmethod
    def _patient_no(bill, patient) -> str:
        stored = getattr(bill, "patient_no", None)
        if stored:
            return str(stored)
        if patient and getattr(patient, "patient_no", None):
            return str(patient.patient_no)
        return "—"

    async def _user_names(self, user_ids: set[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return {user.id: user.full_name for user in result.scalars().all()}

    async def _fetch_opd(
        self, from_date: date, to_date: date
    ) -> list[tuple[str, OpdBill]]:
        stmt = (
            select(OpdBill)
            .options(selectinload(OpdBill.patient))
            .where(
                OpdBill.status == "cancelled",
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
            .order_by(OpdBill.bill_date, OpdBill.bill_no)
        )
        result = await self.session.execute(stmt)
        return [("OPD", bill) for bill in result.scalars().all()]

    async def _fetch_ipd(
        self, from_date: date, to_date: date
    ) -> list[tuple[str, IpdBill]]:
        stmt = (
            select(IpdBill)
            .options(selectinload(IpdBill.patient))
            .where(
                IpdBill.status == "cancelled",
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
            .order_by(IpdBill.bill_date, IpdBill.bill_no)
        )
        result = await self.session.execute(stmt)
        return [("IPD", bill) for bill in result.scalars().all()]

    async def _fetch_pathology(
        self, from_date: date, to_date: date
    ) -> list[tuple[str, PathologyBill]]:
        stmt = (
            select(PathologyBill)
            .options(selectinload(PathologyBill.patient))
            .where(
                PathologyBill.status == "cancelled",
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
            )
            .order_by(PathologyBill.bill_date, PathologyBill.bill_no)
        )
        result = await self.session.execute(stmt)
        return [("Pathology", bill) for bill in result.scalars().all()]

    async def build_report(
        self,
        *,
        from_date: date,
        to_date: date,
        bill_type: str = "all",
    ) -> CancellationBillReportRead:
        kind = (bill_type or "all").strip().lower()
        if kind not in _BILL_TYPES:
            kind = "all"

        rows_raw: list[tuple[str, object]] = []
        if kind in {"all", "opd"}:
            rows_raw.extend(await self._fetch_opd(from_date, to_date))
        if kind in {"all", "ipd"}:
            rows_raw.extend(await self._fetch_ipd(from_date, to_date))
        if kind in {"all", "pathology"}:
            rows_raw.extend(await self._fetch_pathology(from_date, to_date))

        rows_raw.sort(
            key=lambda item: (
                getattr(item[1], "bill_date"),
                item[0],
                getattr(item[1], "bill_no") or "",
            )
        )

        user_ids = {
            getattr(bill, "created_by_user_id")
            for _, bill in rows_raw
            if getattr(bill, "created_by_user_id", None)
        }
        user_names = await self._user_names(user_ids)

        rows: list[CancellationBillReportRow] = []
        grand_total = Decimal("0.00")
        for index, (label, bill) in enumerate(rows_raw, start=1):
            patient = getattr(bill, "patient", None)
            amount = Decimal(str(getattr(bill, "net_amount", 0) or 0))
            grand_total += amount
            user_id = getattr(bill, "created_by_user_id", None)
            rows.append(
                CancellationBillReportRow(
                    serial_no=index,
                    bill_type=label,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    patient_no=self._patient_no(bill, patient),
                    patient_name=self._patient_name(patient),
                    net_amount=amount,
                    cancellation_remarks=self._cancellation_remarks(bill.remarks),
                    cancelled_at=getattr(bill, "updated_at", None),
                    cancelled_by=user_names.get(user_id) if user_id else None,
                )
            )

        return CancellationBillReportRead(
            from_date=from_date,
            to_date=to_date,
            bill_type=kind,
            rows=rows,
            grand_total=grand_total,
        )
