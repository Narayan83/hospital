from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.ipd_admission import IpdAdmission
from app.models.ipd_bill import IpdBill, IpdBillLine
from app.models.ward import Ward
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.repositories.cashbook import CashbookRepository
from app.repositories.ipd_admission import IpdAdmissionRepository
from app.repositories.ipd_bill import IpdBillRepository
from app.repositories.patient import PatientRepository
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.ipd_discharge import (
    IpdDischargeCreate,
    IpdDischargeLineRead,
    IpdDischargeRead,
    IpdDischargeSummaryRead,
    IpdDischargeUpdate,
)
from app.schemas.opd_bill import BillingServiceCatalogItem
from app.services.bill_number import BillNumberService
from app.services.bill_payment import (
    build_ipd_payment_rows,
    payment_to_read,
    resolve_payment_entries,
    summarize_payment_names,
)
from app.services.billing_sharing import billing_rate_for_service_master, resolve_line_sharing_fields
from app.services.cashbook_posting import CashbookPostingService


class IpdDischargeService:
    PATHOLOGY_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.admission_repo = IpdAdmissionRepository(session)
        self.bill_repo = IpdBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.service_repo = PatientServiceMasterRepository(session)
        self.number_svc = BillNumberService(session)

    def _line_to_read(self, line: IpdBillLine) -> IpdDischargeLineRead:
        return IpdDischargeLineRead.model_validate(line)

    async def _require_advance_adjustment(
        self,
        *,
        patient_id: str,
        adjust_advance: Decimal,
        gross: Decimal,
        prior_adjust: Decimal = Decimal("0"),
    ) -> None:
        """Block save when patient has deposit that can be applied but adjust_advance is 0."""
        if gross <= 0:
            return
        available = await CashbookPostingService(self.session).get_patient_deposit_balance(patient_id)
        # On modify, the existing cashbook debit will be reversed before the new post.
        effective_available = available + max(Decimal("0"), prior_adjust)
        if effective_available > Decimal("0.01") and adjust_advance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Advance adjustment is required when the patient has an advance balance",
            )

    def _bill_to_read(self, bill: IpdBill) -> IpdDischargeRead:
        patient_name = None
        patient_no = None
        if bill.patient:
            patient_no = bill.patient.patient_no
            parts = [bill.patient.first_name, bill.patient.middle_name, bill.patient.last_name]
            patient_name = " ".join(p for p in parts if p)
        admission_no = bill.admission.admission_no if bill.admission else None
        read = IpdDischargeRead.model_validate(bill)
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
        return read.model_copy(
            update={
                "admission_no": admission_no,
                "patient_no": patient_no,
                "patient_name": patient_name,
                "ward_name": bill.ward.name if bill.ward else None,
                "doctor_name": bill.doctor.full_name if bill.doctor else None,
                "department_name": bill.department.name if bill.department else None,
                "payment_mode_name": payment_mode_name,
                "payments": active_payments,
                "lines": [
                    self._line_to_read(line)
                    for line in sorted(active_lines, key=lambda x: x.sort_order)
                ],
            }
        )

    async def _optional_admission(self, data: IpdDischargeCreate) -> IpdAdmission | None:
        """Link a selected admission when one is sent. Direct discharge needs none."""
        if not data.admission_id:
            return None
        admission = await self.admission_repo.get_with_details(data.admission_id)
        if not admission or not admission.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        if admission.patient_id != data.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admission does not belong to this patient",
            )
        return admission

    async def _department_id(
        self, doctor_id: str | None, admission: IpdAdmission | None
    ) -> str | None:
        if admission and admission.department_id:
            return admission.department_id
        if not doctor_id:
            return None
        doctor = await self.session.get(Doctor, doctor_id)
        return doctor.department_id if doctor else None

    async def _require_ward(self, ward_id: str | None) -> None:
        if not ward_id:
            return
        ward = await self.session.get(Ward, ward_id)
        if not ward or not ward.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ward not found")

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
        # the Pathology Bill screen — never mix them into IPD billing.
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
    ) -> IpdBillLine:
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
        return IpdBillLine(
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

    async def discharge(self, data: IpdDischargeCreate, *, entered_by_user_id: str | None = None) -> IpdDischargeRead:
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        admission = await self._optional_admission(data)
        if admission and admission.status != "admitted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Admission is not active for discharge (status: {admission.status})",
            )
        if admission:
            existing = await self.bill_repo.get_by_admission_id(admission.id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This admission has already been discharged",
                )

        discharge_date = data.discharge_date or date.today()
        bill_admission_date = data.admission_date or (
            admission.admission_date if admission else date.today()
        )
        bill_doctor_id = data.doctor_id or (admission.doctor_id if admission else None)
        if not bill_doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is required",
            )
        if discharge_date < bill_admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge date cannot be before admission date",
            )
        ward_id = data.ward_id or (admission.ward_id if admission else None)
        await self._require_ward(ward_id)
        bed_no = (data.bed_no or "").strip() or (admission.bed_no if admission else None)
        department_id = await self._department_id(bill_doctor_id, admission)

        stay_days = (discharge_date - bill_admission_date).days + 1
        bill_no = await self.number_svc.generate_ipd_bill_no(discharge_date)
        gross = Decimal("0")
        lines: list[IpdBillLine] = []

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

        await self._require_advance_adjustment(
            patient_id=data.patient_id,
            adjust_advance=data.adjust_advance,
            gross=gross,
        )

        payment_entries, primary_payment_mode_id, is_cash = await resolve_payment_entries(
            self.session,
            net_amount=net,
            payments=data.payments,
            legacy_payment_mode_id=data.payment_mode_id,
        )

        bill = IpdBill(
            bill_no=bill_no,
            bill_date=discharge_date,
            admission_id=admission.id if admission else None,
            patient_id=data.patient_id,
            ward_id=ward_id,
            doctor_id=bill_doctor_id,
            department_id=department_id,
            bed_no=bed_no,
            admission_date=bill_admission_date,
            discharge_date=discharge_date,
            stay_days=stay_days,
            payment_mode_id=primary_payment_mode_id,
            is_cash=is_cash,
            scheme=data.scheme,
            admin_charges=data.admin_charges,
            scheme_discount=data.scheme_discount,
            sanctioned_scheme_amount=data.sanctioned_scheme_amount,
            adjust_advance=data.adjust_advance,
            hide_advance_on_bill=data.hide_advance_on_bill,
            gross_amount=gross,
            net_amount=net,
            remarks=data.remarks,
            status="discharged",
            is_active=True,
            created_by_user_id=entered_by_user_id,
            lines=lines,
        )
        self.session.add(bill)
        await self.session.flush()
        for payment_row in build_ipd_payment_rows(bill.id, payment_entries):
            self.session.add(payment_row)
        await self.session.flush()

        patient_no = patient.patient_no if patient else ""
        await CashbookPostingService(self.session).post_bill(
            source_type="ipd_bill",
            source_id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            patient_id=data.patient_id,
            patient_no=patient_no,
            payment_entries=payment_entries,
            gross_amount=gross,
            net_amount=net,
            adjust_advance=data.adjust_advance,
            created_by_user_id=bill.created_by_user_id,
        )

        if admission:
            admission.status = "discharged"
            admission.discharge_date = discharge_date
        await self.session.flush()

        saved = await self.bill_repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    async def get_discharge(self, bill_id: str) -> IpdDischargeRead:
        bill = await self.bill_repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge bill not found")
        return self._bill_to_read(bill)

    async def get_discharge_by_no(self, bill_no: str) -> IpdDischargeRead:
        bill = await self.bill_repo.get_by_bill_no(bill_no.strip().upper())
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge bill not found")
        full = await self.bill_repo.get_with_lines(bill.id)
        return self._bill_to_read(full)  # type: ignore[arg-type]

    async def _build_lines(self, entries: list) -> tuple[list[IpdBillLine], Decimal]:
        gross = Decimal("0")
        lines: list[IpdBillLine] = []
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

    async def update_discharge(
        self,
        bill_id: str,
        data: IpdDischargeUpdate,
        *,
        entered_by_user_id: str | None = None,
    ) -> IpdDischargeRead:
        bill = await self.bill_repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge bill not found")

        discharge_date = data.discharge_date or bill.discharge_date
        if discharge_date < bill.admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge date cannot be before admission date",
            )
        stay_days = (discharge_date - bill.admission_date).days + 1

        new_lines, gross = await self._build_lines(data.lines)
        net = gross + data.admin_charges - data.scheme_discount - data.adjust_advance
        if net < 0:
            net = Decimal("0")

        await self._require_advance_adjustment(
            patient_id=bill.patient_id,
            adjust_advance=data.adjust_advance,
            gross=gross,
            prior_adjust=Decimal(str(bill.adjust_advance or 0)),
        )

        payment_entries, primary_payment_mode_id, is_cash = await resolve_payment_entries(
            self.session,
            net_amount=net,
            payments=data.payments,
            legacy_payment_mode_id=data.payment_mode_id,
        )

        for line in bill.lines:
            line.is_active = False
        for payment in bill.payments:
            payment.is_active = False

        for line in new_lines:
            bill.lines.append(line)
        for payment_row in build_ipd_payment_rows(bill.id, payment_entries):
            bill.payments.append(payment_row)

        bill.bill_date = discharge_date
        bill.discharge_date = discharge_date
        bill.stay_days = stay_days
        bill.payment_mode_id = primary_payment_mode_id
        bill.is_cash = is_cash
        bill.scheme = data.scheme
        bill.admin_charges = data.admin_charges
        bill.scheme_discount = data.scheme_discount
        bill.sanctioned_scheme_amount = data.sanctioned_scheme_amount
        bill.adjust_advance = data.adjust_advance
        bill.hide_advance_on_bill = data.hide_advance_on_bill
        if data.ward_id:
            await self._require_ward(data.ward_id)
        bill.ward_id = data.ward_id
        bill.bed_no = (data.bed_no or "").strip() or None
        bill.remarks = data.remarks
        bill.gross_amount = gross
        bill.net_amount = net
        bill.status = "modified"
        if entered_by_user_id:
            bill.created_by_user_id = entered_by_user_id

        await self.session.flush()

        patient = bill.patient or await self.patient_repo.get_by_id(bill.patient_id)
        patient_no = patient.patient_no if patient else ""
        await CashbookPostingService(self.session).repost_bill(
            source_type="ipd_bill",
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

        saved = await self.bill_repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    async def cancel_bill(
        self,
        bill_id: str,
        *,
        reason: str,
        cancelled_by_user_id: str | None = None,
    ) -> IpdDischargeRead:
        bill = await self.bill_repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge bill not found")
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

        await CashbookRepository(self.session).deactivate_by_source("ipd_bill", bill.id)

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

        admission = None
        if bill.admission_id:
            admission = bill.admission or await self.admission_repo.get_by_id(bill.admission_id)
        if admission and admission.is_active:
            admission.status = "admitted"
            admission.discharge_date = None

        await self.session.flush()
        saved = await self.bill_repo.get_with_lines(bill.id)
        return self._bill_to_read(saved or bill)

    def _summary_to_read(self, bill: IpdBill) -> IpdDischargeSummaryRead:
        active_payments = [p for p in bill.payments if p.is_active]
        payment_mode_name = summarize_payment_names(
            [payment_to_read(payment) for payment in sorted(active_payments, key=lambda item: item.sort_order)]
        )
        if payment_mode_name == "—" and bill.payment_mode:
            payment_mode_name = bill.payment_mode.name
        return IpdDischargeSummaryRead(
            id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            admission_no=bill.admission.admission_no if bill.admission else None,
            doctor_name=bill.doctor.full_name if bill.doctor else None,
            ward_name=bill.ward.name if bill.ward else None,
            net_amount=bill.net_amount,
            gross_amount=bill.gross_amount,
            discharge_date=bill.discharge_date,
            stay_days=bill.stay_days,
            payment_mode_name=payment_mode_name,
            created_at=bill.created_at,
        )

    async def list_discharges_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list[IpdDischargeSummaryRead]:
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
        bills = await self.bill_repo.list_by_patient_id(resolved_patient_id)
        return [self._summary_to_read(bill) for bill in bills]
