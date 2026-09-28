from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ipd_bill import IpdBill, IpdBillLine
from app.models.opd_bill import OpdBill, OpdBillLine
from app.models.pathology_bill import PathologyBill, PathologyBillLine
from app.repositories.billing_type import BillingTypeRepository
from app.schemas.form_3c_report import Form3CReportRead, Form3CReportRow

_BILL_SOURCE_BY_CODE = {
    "OPD": "opd",
    "IPD": "ipd",
    "LAB": "pathology",
}


class Form3CReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_type_repo = BillingTypeRepository(session)

    @staticmethod
    def _patient_name(parts: list[str | None]) -> str:
        return " ".join(part for part in parts if part) or "—"

    @staticmethod
    def _payment_mode_label(bill) -> str:
        if getattr(bill, "payment_mode", None) and bill.payment_mode:
            return bill.payment_mode.name
        return "Cash" if getattr(bill, "is_cash", True) else "Credit"

    async def _fetch_opd_rows(
        self,
        from_date: date,
        to_date: date,
    ) -> list[Form3CReportRow]:
        stmt = (
            select(OpdBill, OpdBillLine)
            .join(OpdBillLine, OpdBillLine.bill_id == OpdBill.id)
            .options(selectinload(OpdBill.patient), selectinload(OpdBill.payment_mode))
            .where(
                OpdBill.is_active.is_(True),
                OpdBillLine.is_active.is_(True),
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
            .order_by(OpdBill.bill_date, OpdBill.bill_no, OpdBillLine.sort_order)
        )
        result = await self.session.execute(stmt)
        rows: list[Form3CReportRow] = []
        seen_bills: set[str] = set()
        for bill, line in result.all():
            seen_bills.add(bill.id)
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name=line.service_name,
                    total_amount=Decimal(str(line.amount)),
                )
            )

        fallback_stmt = (
            select(OpdBill)
            .options(selectinload(OpdBill.patient), selectinload(OpdBill.payment_mode))
            .where(
                OpdBill.is_active.is_(True),
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
            .order_by(OpdBill.bill_date, OpdBill.bill_no)
        )
        fallback_result = await self.session.execute(fallback_stmt)
        for bill in fallback_result.scalars().all():
            if bill.id in seen_bills:
                continue
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name="Bill Total",
                    total_amount=Decimal(str(bill.net_amount)),
                )
            )
        return rows

    async def _fetch_ipd_rows(
        self,
        from_date: date,
        to_date: date,
    ) -> list[Form3CReportRow]:
        stmt = (
            select(IpdBill, IpdBillLine)
            .join(IpdBillLine, IpdBillLine.bill_id == IpdBill.id)
            .options(selectinload(IpdBill.patient), selectinload(IpdBill.payment_mode))
            .where(
                IpdBill.is_active.is_(True),
                IpdBillLine.is_active.is_(True),
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
            .order_by(IpdBill.bill_date, IpdBill.bill_no, IpdBillLine.sort_order)
        )
        result = await self.session.execute(stmt)
        rows: list[Form3CReportRow] = []
        seen_bills: set[str] = set()
        for bill, line in result.all():
            seen_bills.add(bill.id)
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name=line.service_name,
                    total_amount=Decimal(str(line.amount)),
                )
            )

        fallback_stmt = (
            select(IpdBill)
            .options(selectinload(IpdBill.patient), selectinload(IpdBill.payment_mode))
            .where(
                IpdBill.is_active.is_(True),
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
            .order_by(IpdBill.bill_date, IpdBill.bill_no)
        )
        fallback_result = await self.session.execute(fallback_stmt)
        for bill in fallback_result.scalars().all():
            if bill.id in seen_bills:
                continue
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name="Bill Total",
                    total_amount=Decimal(str(bill.net_amount)),
                )
            )
        return rows

    async def _fetch_pathology_rows(
        self,
        from_date: date,
        to_date: date,
    ) -> list[Form3CReportRow]:
        stmt = (
            select(PathologyBill, PathologyBillLine)
            .join(PathologyBillLine, PathologyBillLine.bill_id == PathologyBill.id)
            .options(selectinload(PathologyBill.patient), selectinload(PathologyBill.payment_mode))
            .where(
                PathologyBill.is_active.is_(True),
                PathologyBillLine.is_active.is_(True),
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
            )
            .order_by(
                PathologyBill.bill_date,
                PathologyBill.bill_no,
                PathologyBillLine.sort_order,
            )
        )
        result = await self.session.execute(stmt)
        rows: list[Form3CReportRow] = []
        seen_bills: set[str] = set()
        for bill, line in result.all():
            seen_bills.add(bill.id)
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name=line.service_name,
                    total_amount=Decimal(str(line.amount)),
                )
            )

        fallback_stmt = (
            select(PathologyBill)
            .options(selectinload(PathologyBill.patient), selectinload(PathologyBill.payment_mode))
            .where(
                PathologyBill.is_active.is_(True),
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
            )
            .order_by(PathologyBill.bill_date, PathologyBill.bill_no)
        )
        fallback_result = await self.session.execute(fallback_stmt)
        for bill in fallback_result.scalars().all():
            if bill.id in seen_bills:
                continue
            patient = bill.patient
            rows.append(
                Form3CReportRow(
                    serial_no=0,
                    bill_date=bill.bill_date,
                    bill_no=bill.bill_no,
                    payment_mode=self._payment_mode_label(bill),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    service_name="Bill Total",
                    total_amount=Decimal(str(bill.net_amount)),
                )
            )
        return rows

    async def build_report(
        self,
        *,
        billing_type_id: str,
        from_date: date,
        to_date: date,
    ) -> Form3CReportRead:
        if from_date > to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="From date cannot be after To date",
            )

        billing_type = await self.billing_type_repo.get_by_id(billing_type_id)
        if not billing_type or not billing_type.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing type not found",
            )

        source_key = _BILL_SOURCE_BY_CODE.get(billing_type.code.upper())
        if not source_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Form 3C report is not configured for billing type '{billing_type.name}'. "
                    "Supported types: OPD, IPD, Lab."
                ),
            )

        fetchers = {
            "opd": self._fetch_opd_rows,
            "ipd": self._fetch_ipd_rows,
            "pathology": self._fetch_pathology_rows,
        }
        raw_rows = await fetchers[source_key](from_date, to_date)

        numbered_rows: list[Form3CReportRow] = []
        for index, row in enumerate(raw_rows, start=1):
            numbered_rows.append(row.model_copy(update={"serial_no": index}))

        grand_total = sum((row.total_amount for row in numbered_rows), Decimal("0"))

        return Form3CReportRead(
            billing_type_id=billing_type.id,
            billing_type_code=billing_type.code,
            billing_type_name=billing_type.name,
            from_date=from_date,
            to_date=to_date,
            rows=numbered_rows,
            grand_total=grand_total,
        )
