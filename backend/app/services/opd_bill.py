from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.opd_bill import OpdBill, OpdBillLine
from app.models.patient import Patient
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.repositories.cashbook import CashbookRepository
from app.repositories.doctor import DoctorRepository
from app.repositories.opd_bill import OpdBillRepository
from app.repositories.patient import PatientRepository
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.opd_bill import (
    SCHEDULED_VISIT_CATEGORIES,
    BillingServiceCatalogItem,
    OpdBillCreate,
    OpdBillLineRead,
    OpdBillRead,
    OpdBillSummaryRead,
    OpdBillUpdate,
)
from app.services.bill_number import BillNumberService
from app.services.bill_payment import (
    build_opd_payment_rows,
    payment_to_read,
    resolve_payment_entries,
    summarize_payment_names,
)
from app.services.billing_sharing import billing_rate_for_service_master, resolve_line_sharing_fields
from app.services.cashbook_posting import CashbookPostingService
from app.services.opd_token import OpdTokenService


class OpdBillService:
    PATHOLOGY_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OpdBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.service_repo = PatientServiceMasterRepository(session)
        self.doctor_repo = DoctorRepository(session)
        self.number_svc = BillNumberService(session)
        self.token_svc = OpdTokenService(session)

    def _line_to_read(self, line: OpdBillLine) -> OpdBillLineRead:
        return OpdBillLineRead.model_validate(line)

    def _bill_to_read(self, bill: OpdBill) -> OpdBillRead:
        patient_name = None
        patient_no = None
        if bill.patient:
            patient_no = bill.patient.patient_no
            parts = [bill.patient.first_name, bill.patient.middle_name, bill.patient.last_name]
            patient_name = " ".join(p for p in parts if p)
        token_number = None
        token_session = None
        if bill.token and bill.token.is_active:
            token_number = bill.token.token_number
            token_session = bill.token.token_session
        read = OpdBillRead.model_validate(bill)
        active_lines = [line for line in bill.lines if line.is_active]
        active_payments = [
            payment_to_read(payment)
            for payment in sorted(
                [p for p in bill.payments if p.is_active],
                key=lambda item: item.sort_order,
            )
        ]
        payment_mode_name = summarize_payment_names(active_payments)
        if payment_mode_name == "—" and bill.payment_mode:
            payment_mode_name = bill.payment_mode.name
        stored_patient_no = bill.patient_no or patient_no
        return read.model_copy(
            update={
                "patient_no": stored_patient_no,
                "patient_name": patient_name,
                "doctor_name": bill.doctor.full_name if bill.doctor else None,
                "payment_mode_name": payment_mode_name,
                "payments": active_payments,
                "department_name": bill.department.name if bill.department else None,
                "token_number": token_number,
                "token_session": token_session,
                "lines": [self._line_to_read(line) for line in sorted(active_lines, key=lambda x: x.sort_order)],
            }
        )

    async def list_catalog(
        self,
        *,
        category_id: str | None = None,
        sub_category_id: str | None = None,
        search: str | None = None,
    ) -> list[BillingServiceCatalogItem]:
        stmt = (
            select(PatientServiceMaster)
            .options(
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
                selectinload(PatientServiceMaster.doctor),
            )
            .where(PatientServiceMaster.is_active.is_(True))
            .where(PatientServiceMaster.is_service_active.is_(True))
        )
        # Pathology services live in their own (LAB) category and are billed from
        # the Pathology Bill screen — never mix them into OPD billing.
        lab_category_ids = select(ServiceCategory.id).where(
            ServiceCategory.code == self.PATHOLOGY_CATEGORY_CODE
        )
        stmt = stmt.where(
            or_(
                PatientServiceMaster.category_id.is_(None),
                PatientServiceMaster.category_id.notin_(lab_category_ids),
            )
        )
        if category_id:
            stmt = stmt.where(PatientServiceMaster.category_id == category_id)
        if sub_category_id:
            stmt = stmt.where(PatientServiceMaster.sub_category_id == sub_category_id)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                PatientServiceMaster.code.ilike(term) | PatientServiceMaster.name.ilike(term)
            )
        stmt = stmt.order_by(PatientServiceMaster.name)
        result = await self.session.execute(stmt)
        items = []
        for row in result.scalars().all():
            billing_rate = billing_rate_for_service_master(row)
            items.append(
                BillingServiceCatalogItem(
                    id=row.id,
                    code=row.code,
                    name=row.name,
                    rate=billing_rate,
                    service_charge=row.service_charge,
                    is_sharing=row.is_sharing,
                    doctor_id=row.doctor_id,
                    doctor_name=row.doctor.full_name if row.doctor else None,
                    category_id=row.category_id,
                    category_name=row.category.name if row.category else None,
                    sub_category_id=row.sub_category_id,
                    sub_category_name=row.sub_category.name if row.sub_category else None,
                    is_renewal=row.is_renewal,
                    renewal_days=row.renewal_days,
                )
            )
        return items

    async def _make_bill_line(
        self,
        service: PatientServiceMaster,
        entry,
        *,
        index: int,
    ) -> OpdBillLine:
        default_rate = billing_rate_for_service_master(service)
        rate = entry.rate if entry.rate is not None else default_rate
        amount = rate * entry.quantity
        line_name = (
            entry.service_name.strip()
            if entry.service_name and entry.service_name.strip()
            else service.name
        )
        original_rate, hospital_amount, doctor_amount, sharing_doctor_id = resolve_line_sharing_fields(
            service,
            rate=rate,
            amount=amount,
            hospital_amount=entry.hospital_amount,
            doctor_amount=entry.doctor_amount,
            original_rate=entry.original_rate,
            sharing_doctor_id=entry.sharing_doctor_id,
        )
        return OpdBillLine(
            service_id=service.id,
            service_code=service.code,
            service_name=line_name,
            category_name=service.category.name if service.category else None,
            sub_category_name=service.sub_category.name if service.sub_category else None,
            rate=rate,
            quantity=entry.quantity,
            amount=amount,
            original_rate=original_rate,
            hospital_amount=hospital_amount,
            doctor_amount=doctor_amount,
            sharing_doctor_id=sharing_doctor_id,
            line_source=entry.line_source,
            package_id=entry.package_id,
            sort_order=index,
            is_active=True,
        )

    async def create_bill(self, data: OpdBillCreate, *, entered_by_user_id: str | None = None) -> OpdBillRead:
        if not data.lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one service line is required",
            )
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient not found")

        bill_date = data.bill_date or date.today()
        bill_no = await self.number_svc.generate_opd_bill_no(bill_date)
        gross = Decimal("0")
        lines: list[OpdBillLine] = []

        for index, entry in enumerate(data.lines):
            service = await self.service_repo.get_by_id(entry.service_id)
            if not service or not service.is_active or not service.is_service_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service not found: {entry.service_id}",
                )
            line = await self._make_bill_line(service, entry, index=index)
            gross += Decimal(str(line.amount))
            lines.append(line)

        net = gross + data.admin_charges - data.scheme_discount - data.adjust_advance
        if net < 0:
            net = Decimal("0")

        payment_entries, primary_payment_mode_id, is_cash = await resolve_payment_entries(
            self.session,
            net_amount=net,
            payments=data.payments,
            legacy_payment_mode_id=data.payment_mode_id,
        )

        appointment_date = data.appointment_date
        if not data.doctor_id or not data.token_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor and session are required for OPD bills",
            )
        doctor = await self.doctor_repo.get_by_id(data.doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor not found")

        bill = OpdBill(
            bill_no=bill_no,
            bill_date=bill_date,
            patient_id=data.patient_id,
            patient_no=patient.patient_no,
            doctor_id=data.doctor_id,
            payment_mode_id=primary_payment_mode_id,
            department_id=data.department_id or doctor.department_id,
            is_cash=is_cash,
            scheme=data.scheme,
            admin_charges=data.admin_charges,
            scheme_discount=data.scheme_discount,
            sanctioned_scheme_amount=data.sanctioned_scheme_amount,
            adjust_advance=data.adjust_advance,
            gross_amount=gross,
            net_amount=net,
            remarks=data.remarks,
            visit_category=data.visit_category,
            appointment_date=appointment_date if data.visit_category in SCHEDULED_VISIT_CATEGORIES else None,
            status="saved",
            is_active=True,
            created_by_user_id=entered_by_user_id,
            lines=lines,
        )
        self.session.add(bill)
        await self.session.flush()
        for payment_row in build_opd_payment_rows(bill.id, payment_entries):
            self.session.add(payment_row)
        await self.session.flush()

        await CashbookPostingService(self.session).post_bill(
            source_type="opd_bill",
            source_id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            patient_id=patient.id,
            patient_no=patient.patient_no,
            payment_entries=payment_entries,
            gross_amount=gross,
            net_amount=net,
            adjust_advance=data.adjust_advance,
            created_by_user_id=bill.created_by_user_id,
        )

        await self.token_svc.sync_for_bill(
            bill=bill,
            doctor=doctor,
            token_session=data.token_session,
            visit_category=data.visit_category,
            appointment_date=appointment_date,
        )

        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    async def get_bill(self, bill_id: str) -> OpdBillRead:
        bill = await self.repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return self._bill_to_read(bill)

    async def get_bill_by_no(self, bill_no: str) -> OpdBillRead:
        bill = await self.repo.get_by_bill_no(bill_no.strip().upper())
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        full = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(full)  # type: ignore[arg-type]

    async def _build_lines(
        self, entries: list
    ) -> tuple[list[OpdBillLine], Decimal]:
        gross = Decimal("0")
        lines: list[OpdBillLine] = []
        for index, entry in enumerate(entries):
            service = await self.service_repo.get_by_id(entry.service_id)
            if not service or not service.is_active or not service.is_service_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service not found: {entry.service_id}",
                )
            line = await self._make_bill_line(service, entry, index=index)
            gross += Decimal(str(line.amount))
            lines.append(line)
        return lines, gross

    async def update_bill(
        self,
        bill_id: str,
        data: OpdBillUpdate,
        *,
        entered_by_user_id: str | None = None,
    ) -> OpdBillRead:
        bill = await self.repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        new_lines, gross = await self._build_lines(data.lines)
        net = gross + data.admin_charges - data.scheme_discount - data.adjust_advance
        if net < 0:
            net = Decimal("0")

        payment_entries, primary_payment_mode_id, is_cash = await resolve_payment_entries(
            self.session,
            net_amount=net,
            payments=data.payments,
            legacy_payment_mode_id=data.payment_mode_id,
        )

        visit_category = data.visit_category or bill.visit_category
        if not data.doctor_id or not data.token_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor and session are required for OPD bills",
            )
        doctor = await self.doctor_repo.get_by_id(data.doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor not found")

        for line in bill.lines:
            line.is_active = False
        for payment in bill.payments:
            payment.is_active = False

        for line in new_lines:
            bill.lines.append(line)
        for payment_row in build_opd_payment_rows(bill.id, payment_entries):
            bill.payments.append(payment_row)

        if data.doctor_id is not None:
            bill.doctor_id = data.doctor_id
        if data.department_id is not None:
            bill.department_id = data.department_id
        elif doctor.department_id and not bill.department_id:
            bill.department_id = doctor.department_id
        bill.payment_mode_id = primary_payment_mode_id
        bill.is_cash = is_cash
        bill.scheme = data.scheme
        bill.admin_charges = data.admin_charges
        bill.scheme_discount = data.scheme_discount
        bill.sanctioned_scheme_amount = data.sanctioned_scheme_amount
        bill.adjust_advance = data.adjust_advance
        bill.remarks = data.remarks
        bill.gross_amount = gross
        bill.net_amount = net
        bill.visit_category = visit_category
        if entered_by_user_id:
            bill.created_by_user_id = entered_by_user_id
        if data.appointment_date is not None:
            bill.appointment_date = data.appointment_date
        elif visit_category not in SCHEDULED_VISIT_CATEGORIES:
            bill.appointment_date = None
        bill.status = "modified"

        await self.session.flush()

        appointment_date = bill.appointment_date
        if visit_category in SCHEDULED_VISIT_CATEGORIES and not appointment_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking date is required for appointment and online booking visits",
            )

        await self.token_svc.sync_for_bill(
            bill=bill,
            doctor=doctor,
            token_session=data.token_session,
            visit_category=visit_category,
            appointment_date=appointment_date,
        )

        patient = bill.patient or await self.patient_repo.get_by_id(bill.patient_id)
        patient_no = bill.patient_no or (patient.patient_no if patient else "")
        await CashbookPostingService(self.session).repost_bill(
            source_type="opd_bill",
            source_id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            patient_id=bill.patient_id,
            patient_no=patient_no,
            payment_entries=payment_entries,
            gross_amount=gross,
            net_amount=net,
            adjust_advance=data.adjust_advance,
            created_by_user_id=bill.created_by_user_id,
        )

        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    async def cancel_bill(
        self,
        bill_id: str,
        *,
        reason: str,
        cancelled_by_user_id: str | None = None,
    ) -> OpdBillRead:
        bill = await self.repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        if bill.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bill is already cancelled",
            )

        reason = (reason or "").strip()
        if not reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A cancellation reason is required",
            )

        # Reverse the cashbook posting so receipts no longer count this bill.
        await CashbookRepository(self.session).deactivate_by_source("opd_bill", bill.id)

        # Release the OPD token tied to this bill, if any.
        token = await self.token_svc.repo.get_by_bill_id(bill.id)
        if token and token.is_active:
            token.is_active = False
        elif bill.token and bill.token.is_active:
            bill.token.is_active = False

        for line in bill.lines:
            line.is_active = False
        for payment in bill.payments:
            payment.is_active = False

        note = f"CANCELLED: {reason}"
        bill.remarks = f"{bill.remarks}\n{note}" if bill.remarks else note
        bill.status = "cancelled"
        bill.is_active = False
        if cancelled_by_user_id:
            bill.created_by_user_id = bill.created_by_user_id or cancelled_by_user_id

        await self.session.flush()
        # Re-load so response building does not hit stale relationship state.
        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved or bill)

    def _summary_to_read(self, bill: OpdBill) -> OpdBillSummaryRead:
        token_number = None
        token_session = None
        if bill.token and bill.token.is_active:
            token_number = bill.token.token_number
            token_session = bill.token.token_session
        active_payments = [p for p in bill.payments if p.is_active]
        payment_mode_name = summarize_payment_names(
            [payment_to_read(payment) for payment in sorted(active_payments, key=lambda item: item.sort_order)]
        )
        if payment_mode_name == "—" and bill.payment_mode:
            payment_mode_name = bill.payment_mode.name
        return OpdBillSummaryRead(
            id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            doctor_name=bill.doctor.full_name if bill.doctor else None,
            department_name=bill.department.name if bill.department else None,
            net_amount=bill.net_amount,
            gross_amount=bill.gross_amount,
            token_number=token_number,
            token_session=token_session,
            visit_category=bill.visit_category,
            payment_mode_name=payment_mode_name,
            created_at=bill.created_at,
        )

    async def list_bills_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list[OpdBillSummaryRead]:
        if patient_no and patient_no.strip():
            bills = await self.repo.list_by_patient_no(patient_no.strip())
            if bills:
                return [self._summary_to_read(bill) for bill in bills]
        resolved_patient_id = patient_id
        if not resolved_patient_id:
            if not patient_no or not patient_no.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="patient_id or patient_no is required",
                )
            patient = await self.patient_repo.get_by_patient_no(patient_no.strip())
            if not patient:
                items, _total = await self.patient_repo.advanced_search(
                    patient_no=patient_no.strip(),
                    page=1,
                    page_size=10,
                )
                patient = next(
                    (
                        item
                        for item in items
                        if item.patient_no.strip().upper() == patient_no.strip().upper()
                    ),
                    None,
                )
            if not patient or not patient.is_active:
                return []
            resolved_patient_id = patient.id
        bills = await self.repo.list_by_patient_id(resolved_patient_id)
        return [self._summary_to_read(bill) for bill in bills]
