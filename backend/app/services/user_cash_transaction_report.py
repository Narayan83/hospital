from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ipd_bill import IpdBill, IpdBillPayment
from app.models.opd_bill import OpdBill, OpdBillPayment
from app.models.pathology_bill import PathologyBill
from app.models.single_service_opd import SingleServiceOpdBill
from app.repositories.cashbook import CashbookRepository
from app.repositories.payment_mode import PaymentModeRepository
from app.repositories.user import UserRepository
from app.schemas.user_cash_transaction_report import (
    UserCashDayGroup,
    UserCashDayUserSummary,
    UserCashTransactionBillTypeGroup,
    UserCashTransactionPaymentGroup,
    UserCashTransactionReportRead,
    UserCashTransactionRow,
)

UNKNOWN_USER_ID = "__unattributed__"
UNKNOWN_USER_NAME = "Not attributed to a user"

ADVANCE_SECTION = "Advance Collection"
RECEIPT_SECTION = "Receipt Voucher"
PAYMENT_SECTION = "Payment / Refund"

# Cash out sections are subtracted from the collection so the report nets to
# the cash actually in hand at the end of the day.
DEBIT_SECTIONS = frozenset({PAYMENT_SECTION})


@dataclass(frozen=True)
class _CashRow:
    """One cash movement: a bill payment line, an advance, or a voucher line."""

    section: str
    user_id: str
    doc_no: str
    patient_no: str
    patient_name: str
    payment_mode_id: str | None
    payment_mode_name: str
    amount: Decimal
    entry_date: date

    @property
    def is_debit(self) -> bool:
        return self.section in DEBIT_SECTIONS

    @property
    def signed_amount(self) -> Decimal:
        return -self.amount if self.is_debit else self.amount


class UserCashTransactionReportService:
    BILL_TYPES = (
        ("OPD", "opd"),
        ("IPD", "ipd"),
        ("Pathology", "pathology"),
    )
    VOUCHER_SECTIONS = (ADVANCE_SECTION, RECEIPT_SECTION, PAYMENT_SECTION)

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.cashbook_repo = CashbookRepository(session)
        self.payment_mode_repo = PaymentModeRepository(session)

    def _sections(self) -> tuple[str, ...]:
        return tuple(label for label, _key in self.BILL_TYPES) + self.VOUCHER_SECTIONS

    @staticmethod
    def _patient_name(parts: list[str | None]) -> str:
        return " ".join(part for part in parts if part) or "—"

    @staticmethod
    def _build_groups(rows: list[_CashRow]) -> list[UserCashTransactionPaymentGroup]:
        grouped: dict[str, list[_CashRow]] = defaultdict(list)
        for row in rows:
            grouped[row.payment_mode_name].append(row)

        payment_groups: list[UserCashTransactionPaymentGroup] = []
        for payment_mode_name in sorted(grouped.keys(), key=lambda value: value.lower()):
            mode_rows = grouped[payment_mode_name]
            payment_groups.append(
                UserCashTransactionPaymentGroup(
                    payment_mode_name=payment_mode_name,
                    rows=[
                        UserCashTransactionRow(
                            bill_no=row.doc_no,
                            patient_no=row.patient_no or "—",
                            patient_name=row.patient_name or "—",
                            amount=row.amount,
                            bill_date=row.entry_date,
                            is_debit=row.is_debit,
                        )
                        for row in mode_rows
                    ],
                    subtotal=sum((row.amount for row in mode_rows), Decimal("0")),
                )
            )
        return payment_groups

    def _user_filter(self, column, user_ids: list[str] | None):
        if user_ids is None:
            return column.is_not(None)
        if len(user_ids) == 1:
            return column == user_ids[0]
        return column.in_(user_ids)

    async def _fetch_opd_rows(
        self,
        user_ids: list[str] | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[_CashRow]:
        stmt = (
            select(OpdBill, OpdBillPayment)
            .join(OpdBillPayment, OpdBillPayment.bill_id == OpdBill.id)
            .options(selectinload(OpdBill.patient), selectinload(OpdBillPayment.payment_mode))
            .where(
                OpdBill.is_active.is_(True),
                self._user_filter(OpdBill.created_by_user_id, user_ids),
                OpdBillPayment.is_active.is_(True),
            )
        )
        if from_date:
            stmt = stmt.where(OpdBill.bill_date >= from_date)
        if to_date:
            stmt = stmt.where(OpdBill.bill_date <= to_date)
        stmt = stmt.order_by(OpdBill.bill_date, OpdBill.bill_no, OpdBillPayment.sort_order)

        result = await self.session.execute(stmt)
        rows: list[_CashRow] = []
        seen_bills_with_payments: set[str] = set()
        for bill, payment in result.all():
            if not bill.created_by_user_id:
                continue
            seen_bills_with_payments.add(bill.id)
            patient = bill.patient
            rows.append(
                _CashRow(
                    section="OPD",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=bill.patient_no or (patient.patient_no if patient else ""),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    payment_mode_id=payment.payment_mode.id if payment.payment_mode else None,
                    payment_mode_name=payment.payment_mode.name if payment.payment_mode else "—",
                    amount=Decimal(str(payment.amount)),
                    entry_date=bill.bill_date,
                )
            )

        fallback_stmt = (
            select(OpdBill)
            .options(selectinload(OpdBill.patient), selectinload(OpdBill.payment_mode))
            .where(
                OpdBill.is_active.is_(True),
                self._user_filter(OpdBill.created_by_user_id, user_ids),
            )
        )
        if from_date:
            fallback_stmt = fallback_stmt.where(OpdBill.bill_date >= from_date)
        if to_date:
            fallback_stmt = fallback_stmt.where(OpdBill.bill_date <= to_date)
        fallback_result = await self.session.execute(fallback_stmt)
        for bill in fallback_result.scalars().all():
            if bill.id in seen_bills_with_payments or not bill.created_by_user_id:
                continue
            patient = bill.patient
            rows.append(
                _CashRow(
                    section="OPD",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=bill.patient_no or (patient.patient_no if patient else ""),
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    payment_mode_id=bill.payment_mode.id if bill.payment_mode else None,
                    payment_mode_name=bill.payment_mode.name if bill.payment_mode else "—",
                    amount=Decimal(str(bill.net_amount)),
                    entry_date=bill.bill_date,
                )
            )
        return rows

    async def _fetch_ipd_rows(
        self,
        user_ids: list[str] | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[_CashRow]:
        stmt = (
            select(IpdBill, IpdBillPayment)
            .join(IpdBillPayment, IpdBillPayment.bill_id == IpdBill.id)
            .options(selectinload(IpdBill.patient), selectinload(IpdBillPayment.payment_mode))
            .where(
                IpdBill.is_active.is_(True),
                self._user_filter(IpdBill.created_by_user_id, user_ids),
                IpdBillPayment.is_active.is_(True),
            )
        )
        if from_date:
            stmt = stmt.where(IpdBill.bill_date >= from_date)
        if to_date:
            stmt = stmt.where(IpdBill.bill_date <= to_date)
        stmt = stmt.order_by(IpdBill.bill_date, IpdBill.bill_no, IpdBillPayment.sort_order)

        result = await self.session.execute(stmt)
        rows: list[_CashRow] = []
        seen_bills_with_payments: set[str] = set()
        for bill, payment in result.all():
            if not bill.created_by_user_id:
                continue
            seen_bills_with_payments.add(bill.id)
            patient = bill.patient
            rows.append(
                _CashRow(
                    section="IPD",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=patient.patient_no if patient else "",
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    payment_mode_id=payment.payment_mode.id if payment.payment_mode else None,
                    payment_mode_name=payment.payment_mode.name if payment.payment_mode else "—",
                    amount=Decimal(str(payment.amount)),
                    entry_date=bill.bill_date,
                )
            )

        fallback_stmt = (
            select(IpdBill)
            .options(selectinload(IpdBill.patient), selectinload(IpdBill.payment_mode))
            .where(
                IpdBill.is_active.is_(True),
                self._user_filter(IpdBill.created_by_user_id, user_ids),
            )
        )
        if from_date:
            fallback_stmt = fallback_stmt.where(IpdBill.bill_date >= from_date)
        if to_date:
            fallback_stmt = fallback_stmt.where(IpdBill.bill_date <= to_date)
        fallback_result = await self.session.execute(fallback_stmt)
        for bill in fallback_result.scalars().all():
            if bill.id in seen_bills_with_payments or not bill.created_by_user_id:
                continue
            patient = bill.patient
            rows.append(
                _CashRow(
                    section="IPD",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=patient.patient_no if patient else "",
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    payment_mode_id=bill.payment_mode.id if bill.payment_mode else None,
                    payment_mode_name=bill.payment_mode.name if bill.payment_mode else "—",
                    amount=Decimal(str(bill.net_amount)),
                    entry_date=bill.bill_date,
                )
            )
        return rows

    async def _fetch_pathology_rows(
        self,
        user_ids: list[str] | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[_CashRow]:
        stmt = (
            select(PathologyBill)
            .options(selectinload(PathologyBill.patient), selectinload(PathologyBill.payment_mode))
            .where(
                PathologyBill.is_active.is_(True),
                self._user_filter(PathologyBill.created_by_user_id, user_ids),
            )
        )
        if from_date:
            stmt = stmt.where(PathologyBill.bill_date >= from_date)
        if to_date:
            stmt = stmt.where(PathologyBill.bill_date <= to_date)
        stmt = stmt.order_by(PathologyBill.bill_date, PathologyBill.bill_no)

        result = await self.session.execute(stmt)
        rows: list[_CashRow] = []
        for bill in result.scalars().all():
            if not bill.created_by_user_id:
                continue
            patient = bill.patient
            rows.append(
                _CashRow(
                    section="Pathology",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=patient.patient_no if patient else "",
                    patient_name=self._patient_name(
                        [patient.first_name, patient.middle_name, patient.last_name]
                        if patient
                        else []
                    ),
                    payment_mode_id=bill.payment_mode.id if bill.payment_mode else None,
                    payment_mode_name=bill.payment_mode.name if bill.payment_mode else "—",
                    amount=Decimal(str(bill.net_amount)),
                    entry_date=bill.bill_date,
                )
            )
        return rows

    async def _fetch_single_service_rows(
        self,
        user_ids: list[str] | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[_CashRow]:
        stmt = (
            select(SingleServiceOpdBill)
            .options(selectinload(SingleServiceOpdBill.option))
            .where(
                SingleServiceOpdBill.is_active.is_(True),
                self._user_filter(SingleServiceOpdBill.created_by_user_id, user_ids),
            )
        )
        if from_date:
            stmt = stmt.where(SingleServiceOpdBill.bill_date >= from_date)
        if to_date:
            stmt = stmt.where(SingleServiceOpdBill.bill_date <= to_date)
        stmt = stmt.order_by(SingleServiceOpdBill.bill_date, SingleServiceOpdBill.bill_no)
        result = await self.session.execute(stmt)
        rows: list[_CashRow] = []
        for bill in result.scalars().all():
            if not bill.created_by_user_id:
                continue
            rows.append(
                _CashRow(
                    section=bill.option.name if bill.option else "Single Service OPD",
                    user_id=bill.created_by_user_id,
                    doc_no=bill.bill_no,
                    patient_no=bill.patient_no or "",
                    patient_name=bill.patient_name or "—",
                    payment_mode_id=bill.payment_mode_id,
                    payment_mode_name=bill.payment_mode_name or "Cash",
                    amount=Decimal(str(bill.rate or 0)),
                    entry_date=bill.bill_date,
                )
            )
        return rows

    async def _fetch_voucher_rows(
        self,
        user_ids: list[str] | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[_CashRow]:
        """Advance collections and payment/receipt vouchers from the cashbook.

        A voucher line only moves real money when its ledger is mapped to a payment
        mode; the counter leg (patient deposit, income, expense) is ignored. A debit
        on that ledger is cash in, a credit is cash going back out.
        """
        modes_by_ledger = {}
        for mode in await self.payment_mode_repo.list_active():
            if mode.ledger_id:
                modes_by_ledger.setdefault(mode.ledger_id, mode)

        vouchers = await self.cashbook_repo.list_active_by_source_types(
            ("advance_collection", "payment_voucher"),
            user_ids=user_ids,
            from_date=from_date,
            to_date=to_date,
        )

        rows: list[_CashRow] = []
        for voucher in vouchers:
            patient = voucher.patient
            patient_name = self._patient_name(
                [patient.first_name, patient.middle_name, patient.last_name] if patient else []
            )
            for line in voucher.lines or []:
                if not line.is_active:
                    continue
                mode = modes_by_ledger.get(line.ledger_id)
                if not mode:
                    continue
                debit = Decimal(str(line.debit_amount or 0))
                credit = Decimal(str(line.credit_amount or 0))
                if debit > 0:
                    section = (
                        ADVANCE_SECTION
                        if voucher.source_type == "advance_collection"
                        else RECEIPT_SECTION
                    )
                    amount = debit
                elif credit > 0:
                    section = PAYMENT_SECTION
                    amount = credit
                else:
                    continue
                rows.append(
                    _CashRow(
                        section=section,
                        user_id=voucher.created_by_user_id or UNKNOWN_USER_ID,
                        doc_no=voucher.voucher_no,
                        patient_no=voucher.patient_no
                        or (patient.patient_no if patient else "")
                        or "—",
                        patient_name=patient_name,
                        payment_mode_id=mode.id,
                        payment_mode_name=mode.name,
                        amount=amount,
                        entry_date=voucher.voucher_date,
                    )
                )
        return rows

    async def _resolve_users(
        self, user_id: str | None
    ) -> tuple[list[str] | None, str, dict[str, str]]:
        if user_id and user_id.lower() != "all":
            user = await self.user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            return [user.id], user.full_name, {user.id: user.full_name}

        users = await self.user_repo.list_users(active_only=True)
        name_map = {u.id: u.full_name for u in users}
        return None, "All Users", name_map

    async def _resolve_payment_mode(self, payment_mode_id: str | None) -> tuple[str | None, str]:
        if not payment_mode_id or payment_mode_id.lower() == "all":
            return None, "All Modes"
        mode = await self.payment_mode_repo.get_by_id(payment_mode_id)
        if not mode or not mode.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Payment mode not found"
            )
        return mode.id, mode.name

    async def build_report(
        self,
        *,
        user_id: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        report_type: str = "detail",
        payment_mode_id: str | None = None,
    ) -> UserCashTransactionReportRead:
        normalized = (report_type or "detail").strip().lower()
        if normalized not in {"detail", "day_wise"}:
            normalized = "detail"

        user_ids, display_name, name_map = await self._resolve_users(user_id)
        single_user_id = user_ids[0] if user_ids and len(user_ids) == 1 else None
        mode_filter_id, mode_label = await self._resolve_payment_mode(payment_mode_id)

        rows: list[_CashRow] = []
        for fetch in (
            self._fetch_opd_rows,
            self._fetch_ipd_rows,
            self._fetch_pathology_rows,
            self._fetch_single_service_rows,
            self._fetch_voucher_rows,
        ):
            rows.extend(await fetch(user_ids, from_date, to_date))

        if mode_filter_id:
            rows = [row for row in rows if row.payment_mode_id == mode_filter_id]

        if not single_user_id and any(row.user_id == UNKNOWN_USER_ID for row in rows):
            name_map = {**name_map, UNKNOWN_USER_ID: UNKNOWN_USER_NAME}

        if normalized == "day_wise":
            return self._build_day_wise(
                rows,
                name_map=name_map,
                display_name=display_name,
                single_user_id=single_user_id,
                from_date=from_date,
                to_date=to_date,
                mode_label=mode_label,
            )

        return self._build_detail(
            rows,
            name_map=name_map,
            display_name=display_name,
            single_user_id=single_user_id,
            from_date=from_date,
            to_date=to_date,
            mode_label=mode_label,
        )

    @staticmethod
    def _section_totals(rows: list[_CashRow]) -> tuple[Decimal, Decimal, Decimal]:
        bills = sum(
            (
                row.amount
                for row in rows
                if row.section not in UserCashTransactionReportService.VOUCHER_SECTIONS
            ),
            Decimal("0"),
        )
        advances = sum(
            (row.amount for row in rows if row.section in (ADVANCE_SECTION, RECEIPT_SECTION)),
            Decimal("0"),
        )
        payments = sum(
            (row.amount for row in rows if row.section == PAYMENT_SECTION), Decimal("0")
        )
        return bills, advances, payments

    def _section_order(self, rows: list[_CashRow]) -> list[str]:
        fixed = list(self._sections())
        fixed_set = set(fixed)
        extras: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if row.section not in fixed_set and row.section not in seen:
                seen.add(row.section)
                extras.append(row.section)
        extras.sort(key=str.casefold)
        voucher = set(self.VOUCHER_SECTIONS)
        head = [section for section in fixed if section not in voucher]
        tail = [section for section in fixed if section in voucher]
        return head + extras + tail

    def _build_detail(
        self,
        rows: list[_CashRow],
        *,
        name_map: dict[str, str],
        display_name: str,
        single_user_id: str | None,
        from_date: date | None,
        to_date: date | None,
        mode_label: str,
    ) -> UserCashTransactionReportRead:
        bill_type_groups: list[UserCashTransactionBillTypeGroup] = []
        overall_total = Decimal("0")

        def make_group(label: str, section: str, section_rows: list[_CashRow]):
            payment_groups = self._build_groups(section_rows)
            grand_total = sum((g.subtotal for g in payment_groups), Decimal("0"))
            is_debit = section in DEBIT_SECTIONS
            return (
                UserCashTransactionBillTypeGroup(
                    bill_type=label,
                    payment_groups=payment_groups,
                    grand_total=grand_total,
                    is_debit=is_debit,
                ),
                -grand_total if is_debit else grand_total,
            )

        if single_user_id:
            by_section: dict[str, list[_CashRow]] = defaultdict(list)
            for row in rows:
                by_section[row.section].append(row)
            for section in self._section_order(rows):
                section_rows = by_section.get(section, [])
                fixed_bill_types = {label for label, _key in self.BILL_TYPES}
                if not section_rows and section not in fixed_bill_types:
                    continue
                group, signed_total = make_group(section, section, section_rows)
                overall_total += signed_total
                bill_type_groups.append(group)
        else:
            by_user_section: dict[tuple[str, str], list[_CashRow]] = defaultdict(list)
            for row in rows:
                by_user_section[(row.user_id, row.section)].append(row)
            for uid in sorted(
                name_map.keys(), key=lambda value: name_map.get(value, value).casefold()
            ):
                for section in self._section_order(rows):
                    section_rows = by_user_section.get((uid, section), [])
                    if not section_rows:
                        continue
                    group, signed_total = make_group(
                        f"{name_map.get(uid, uid)} — {section}", section, section_rows
                    )
                    overall_total += signed_total
                    bill_type_groups.append(group)

        bills, advances, payments = self._section_totals(rows)
        return UserCashTransactionReportRead(
            user_id=single_user_id,
            user_name=display_name,
            from_date=from_date,
            to_date=to_date,
            report_type="detail",
            payment_mode_label=mode_label,
            bill_type_groups=bill_type_groups,
            day_groups=[],
            bill_collection_total=bills,
            advance_collection_total=advances,
            payment_debit_total=payments,
            overall_grand_total=overall_total,
        )

    def _build_day_wise(
        self,
        rows: list[_CashRow],
        *,
        name_map: dict[str, str],
        display_name: str,
        single_user_id: str | None,
        from_date: date | None,
        to_date: date | None,
        mode_label: str,
    ) -> UserCashTransactionReportRead:
        section_buckets: dict[date, dict[str, dict[str, Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: Decimal("0")))
        )
        mode_buckets: dict[date, dict[str, dict[str, Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: Decimal("0")))
        )

        for row in rows:
            section_buckets[row.entry_date][row.user_id][row.section] += row.signed_amount
            mode_buckets[row.entry_date][row.user_id][row.payment_mode_name] += row.signed_amount

        day_groups: list[UserCashDayGroup] = []
        overall = Decimal("0")
        for entry_date in sorted(section_buckets.keys()):
            users: list[UserCashDayUserSummary] = []
            day_total = Decimal("0")
            for uid in sorted(
                section_buckets[entry_date].keys(),
                key=lambda value: name_map.get(value, value).casefold(),
            ):
                type_totals = dict(section_buckets[entry_date][uid])
                mode_totals = dict(mode_buckets[entry_date][uid])
                user_day_total = sum(type_totals.values(), Decimal("0"))
                day_total += user_day_total
                users.append(
                    UserCashDayUserSummary(
                        user_id=uid,
                        user_name=name_map.get(uid, uid),
                        bill_type_totals=type_totals,
                        payment_mode_totals=mode_totals,
                        day_total=user_day_total,
                    )
                )
            day_groups.append(
                UserCashDayGroup(bill_date=entry_date, users=users, day_total=day_total)
            )
            overall += day_total

        bills, advances, payments = self._section_totals(rows)
        return UserCashTransactionReportRead(
            user_id=single_user_id,
            user_name=display_name,
            from_date=from_date,
            to_date=to_date,
            report_type="day_wise",
            payment_mode_label=mode_label,
            bill_type_groups=[],
            day_groups=day_groups,
            bill_collection_total=bills,
            advance_collection_total=advances,
            payment_debit_total=payments,
            overall_grand_total=overall,
        )
