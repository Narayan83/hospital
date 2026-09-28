from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient import Patient
from app.models.patient_service_master import PatientServiceMaster
from app.models.pathology_bill import PathologyBill, PathologyBillLine
from app.models.pathology_service_member import PathologyServiceMember
from app.models.pathology_unit import PathologyUnit
from app.models.service_category import ServiceCategory
from app.repositories.pathology_bill import PathologyBillRepository
from app.repositories.pathology_masters import (
    PathologyNormalRangeRepository,
    PathologyParameterRepository,
    PathologyServiceParameterRepository,
    format_range_text,
)
from app.repositories.patient import PatientRepository
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.opd_bill import BillingServiceCatalogItem
from app.schemas.pathology_bill import (
    PathologyBillCreate,
    PathologyBillExpandLine,
    PathologyBillLineRead,
    PathologyBillRead,
    PathologyBillSummaryRead,
    PathologyBillUpdate,
)
from app.services.bill_number import BillNumberService
from app.services.pathology_masters import PathologyOrderService


def _patient_age_label(patient: Patient) -> str | None:
    if not patient.date_of_birth:
        return None
    today = date.today()
    dob = patient.date_of_birth
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if years >= 1:
        return f"{years} Y"
    months = (today.year - dob.year) * 12 + today.month - dob.month
    if months >= 1:
        return f"{months} M"
    days = (today - dob).days
    return f"{days} D"


class PathologyBillService:
    LAB_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PathologyBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.service_repo = PatientServiceMasterRepository(session)
        self.map_repo = PathologyServiceParameterRepository(session)
        self.range_repo = PathologyNormalRangeRepository(session)
        self.param_repo = PathologyParameterRepository(session)
        self.number_svc = BillNumberService(session)

    @staticmethod
    def _normalize_service_code(code: str) -> str:
        raw = code.strip().upper()
        if not raw:
            return raw
        if raw.startswith("P"):
            return raw[:30]
        if raw.isdigit():
            return f"P{raw}"[:30]
        return raw[:30]

    async def expand_service(
        self,
        service_code: str,
        *,
        patient_id: str | None = None,
    ) -> list[PathologyBillExpandLine]:
        code = self._normalize_service_code(service_code)
        service = await self.service_repo.get_by_code(code)
        if not service or not service.is_active or not service.is_service_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lab service not found: {service_code}",
            )

        patient = None
        if patient_id:
            patient = await self.patient_repo.get_by_id(patient_id)

        members = await self._bundle_members(service.id)
        if not members:
            return [await self._expand_line_for_service(service, patient=patient)]

        # Bundle/package: expand recursively into unique leaf tests.
        leaves = await self._collect_leaf_services(service.id, set())
        if not leaves:
            return [await self._expand_line_for_service(service, patient=patient)]

        # Bundle parent always carries the charge; member sub-tests are always rate 0.
        # Fixed bundle price > 0 uses that price; price 0 bills the sum of member rates
        # on the parent only (members still show blank/zero in billing).
        member_total = sum((Decimal(str(leaf.rate)) for leaf in leaves), Decimal("0"))
        bundle_rate = Decimal(str(service.rate))
        if bundle_rate <= 0:
            bundle_rate = member_total
        lines: list[PathologyBillExpandLine] = [
            PathologyBillExpandLine(
                service_id=service.id,
                service_code=service.code,
                service_name=service.name,
                rate=bundle_rate,
                quantity=1,
                amount=bundle_rate,
                is_panel_parent=True,
            )
        ]
        for leaf in leaves:
            lines.append(
                await self._leaf_bill_line(
                    leaf, parent=service, patient=patient, zero=True
                )
            )
        return lines

    async def _bundle_members(self, service_id: str) -> list[PathologyServiceMember]:
        rows = (
            await self.session.execute(
                select(PathologyServiceMember)
                .where(PathologyServiceMember.bundle_service_id == service_id)
                .where(PathologyServiceMember.is_active.is_(True))
                .order_by(PathologyServiceMember.sort_order)
            )
        ).scalars().all()
        return list(rows)

    async def _collect_leaf_services(
        self, bundle_id: str, seen: set[str]
    ) -> list[PatientServiceMaster]:
        """Flatten a bundle (and any nested bundles) into unique leaf tests."""
        result: list[PatientServiceMaster] = []
        for member in await self._bundle_members(bundle_id):
            sub = await self.service_repo.get_by_id(member.member_service_id)
            if not sub or not sub.is_active or not sub.is_service_active:
                continue
            if await self._bundle_members(sub.id):
                result.extend(await self._collect_leaf_services(sub.id, seen))
            elif sub.id not in seen:
                seen.add(sub.id)
                result.append(sub)
        return result

    async def _leaf_bill_line(
        self,
        leaf: PatientServiceMaster,
        *,
        parent: PatientServiceMaster,
        patient,
        zero: bool,
    ) -> PathologyBillExpandLine:
        param = await self.param_repo.get_by_code(leaf.code)
        rng = None
        unit_name = None
        if param:
            if patient:
                rng = await self.range_repo.find_for_patient(param.id, patient)
            unit_name = await self._unit_name_for(param, rng)
        rate = Decimal("0") if zero else Decimal(str(leaf.rate))
        return PathologyBillExpandLine(
            service_id=leaf.id,
            service_code=leaf.code,
            service_name=leaf.name,
            panel_service_id=parent.id,
            panel_code=parent.code,
            panel_name=parent.name,
            rate=rate,
            quantity=1,
            amount=rate,
            reference_range_text=format_range_text(rng, unit_name) if param else None,
            unit_name=unit_name,
            min_value=rng.min_value if rng else None,
            max_value=rng.max_value if rng else None,
            is_panel_parent=False,
        )

    async def _unit_name_for(self, param, rng) -> str | None:
        """Resolve a unit name without triggering async lazy-loads."""
        if rng is not None and getattr(rng, "unit", None) is not None:
            return rng.unit.name
        if param is not None and param.unit_id:
            unit = await self.session.get(PathologyUnit, param.unit_id)
            return unit.name if unit else None
        return None

    async def _expand_line_for_service(self, service, *, patient=None) -> PathologyBillExpandLine:
        param = await self.param_repo.get_by_code(service.code)
        rng = None
        unit_name = None
        if param and patient:
            rng = await self.range_repo.find_for_patient(param.id, patient)
            unit_name = await self._unit_name_for(param, rng)
        rate = Decimal(str(service.rate))
        return PathologyBillExpandLine(
            service_id=service.id,
            service_code=service.code,
            service_name=service.name,
            rate=rate,
            quantity=1,
            amount=rate,
            reference_range_text=format_range_text(rng, unit_name) if param else None,
            unit_name=unit_name,
            min_value=rng.min_value if rng else None,
            max_value=rng.max_value if rng else None,
            is_panel_parent=False,
        )

    def _line_to_read(self, line: PathologyBillLine) -> PathologyBillLineRead:
        return PathologyBillLineRead.model_validate(line)

    def _bill_to_read(self, bill: PathologyBill) -> PathologyBillRead:
        patient_no = None
        patient_name = None
        patient_gender = None
        patient_age = None
        if bill.patient:
            patient_no = bill.patient.patient_no
            parts = [bill.patient.first_name, bill.patient.middle_name, bill.patient.last_name]
            patient_name = " ".join(p for p in parts if p)
            patient_gender = bill.patient.gender
            patient_age = _patient_age_label(bill.patient)
        read = PathologyBillRead.model_validate(bill)
        active_lines = [line for line in bill.lines if line.is_active]
        order_status = None
        sample_no = None
        sample_date = None
        if bill.order and bill.order.is_active:
            order_status = bill.order.status
            sample_no = bill.order.sample_no
            sample_date = bill.order.sample_date
        return read.model_copy(
            update={
                "patient_no": patient_no,
                "patient_name": patient_name,
                "patient_gender": patient_gender,
                "patient_age": patient_age,
                "doctor_name": bill.doctor.full_name if bill.doctor else None,
                "doctor_qualification": bill.doctor.qualification if bill.doctor else None,
                "payment_mode_name": bill.payment_mode.name if bill.payment_mode else None,
                "department_name": bill.department.name if bill.department else None,
                "order_status": order_status,
                "sample_no": sample_no,
                "sample_date": sample_date,
                "lines": [
                    self._line_to_read(line)
                    for line in sorted(active_lines, key=lambda x: x.sort_order)
                ],
            }
        )

    async def list_catalog(
        self,
        *,
        sub_category_id: str | None = None,
        search: str | None = None,
    ) -> list[BillingServiceCatalogItem]:
        stmt = (
            select(PatientServiceMaster)
            .join(ServiceCategory, PatientServiceMaster.category_id == ServiceCategory.id)
            .options(
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
            )
            .where(PatientServiceMaster.is_active.is_(True))
            .where(PatientServiceMaster.is_service_active.is_(True))
            .where(ServiceCategory.code == self.LAB_CATEGORY_CODE)
        )
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
            items.append(
                BillingServiceCatalogItem(
                    id=row.id,
                    code=row.code,
                    name=row.name,
                    rate=row.rate,
                    service_charge=row.service_charge,
                    category_id=row.category_id,
                    category_name=row.category.name if row.category else None,
                    sub_category_id=row.sub_category_id,
                    sub_category_name=row.sub_category.name if row.sub_category else None,
                )
            )
        return items

    async def create_bill(self, data: PathologyBillCreate, *, entered_by_user_id: str | None = None) -> PathologyBillRead:
        if not data.lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one test/service line is required",
            )
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient not found")

        bill_no = await self.number_svc.generate_pathology_bill_no()
        bill_date = data.bill_date or date.today()
        lines, gross = await self._build_lines(data.lines)

        net = gross + data.admin_charges - data.scheme_discount - data.adjust_advance
        if net < 0:
            net = Decimal("0")

        bill = PathologyBill(
            bill_no=bill_no,
            bill_date=bill_date,
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            referring_doctor=data.referring_doctor,
            payment_mode_id=data.payment_mode_id,
            department_id=data.department_id,
            is_cash=data.is_cash,
            scheme=data.scheme,
            admin_charges=data.admin_charges,
            scheme_discount=data.scheme_discount,
            adjust_advance=data.adjust_advance,
            gross_amount=gross,
            net_amount=net,
            remarks=data.remarks,
            status="saved",
            is_active=True,
            created_by_user_id=entered_by_user_id,
            lines=lines,
        )
        self.session.add(bill)
        await self.session.flush()

        await PathologyOrderService(self.session).create_order_for_bill(
            bill_id=bill.id,
            patient_id=data.patient_id,
            order_date=bill_date,
            sample_date=data.sample_date or bill_date,
            sample_no=data.sample_no,
            pathologist_id=data.doctor_id,
        )

        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    async def _build_lines(
        self, entries: list
    ) -> tuple[list[PathologyBillLine], Decimal]:
        gross = Decimal("0")
        lines: list[PathologyBillLine] = []
        for index, entry in enumerate(entries):
            service = await self.service_repo.get_by_id(entry.service_id)
            if not service or not service.is_active or not service.is_service_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service not found: {entry.service_id}",
                )
            rate = entry.rate if entry.rate is not None else Decimal(str(service.rate))
            # Bundle sub-tests never carry a charge — only the parent line does.
            if getattr(entry, "panel_service_id", None) and not getattr(
                entry, "is_panel_parent", False
            ):
                rate = Decimal("0")
            amount = rate * entry.quantity
            gross += amount
            line_name = (
                entry.service_name.strip()
                if entry.service_name and entry.service_name.strip()
                else service.name
            )
            lines.append(
                PathologyBillLine(
                    service_id=service.id,
                    service_code=service.code,
                    service_name=line_name,
                    category_name=service.category.name if service.category else None,
                    sub_category_name=service.sub_category.name if service.sub_category else None,
                    rate=rate,
                    quantity=entry.quantity,
                    amount=amount,
                    line_source=entry.line_source,
                    package_id=entry.package_id,
                    panel_service_id=getattr(entry, "panel_service_id", None),
                    panel_name=getattr(entry, "panel_name", None),
                    is_panel_parent=getattr(entry, "is_panel_parent", False),
                    reference_range_text=getattr(entry, "reference_range_text", None),
                    result_value=(
                        (entry.result_value or "").strip() or None
                        if getattr(entry, "result_value", None) is not None
                        else None
                    ),
                    is_abnormal=bool(getattr(entry, "is_abnormal", False)),
                    sort_order=index,
                    is_active=True,
                )
            )
        return lines, gross

    async def update_bill(
        self,
        bill_id: str,
        data: PathologyBillUpdate,
        *,
        entered_by_user_id: str | None = None,
    ) -> PathologyBillRead:
        bill = await self.repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        new_lines, gross = await self._build_lines(data.lines)
        net = gross + data.admin_charges - data.scheme_discount - data.adjust_advance
        if net < 0:
            net = Decimal("0")

        # Soft-deactivate old lines, then attach replacements on the relationship
        # collection. Using session.add() alone leaves the identity-mapped
        # bill.lines collection stale, so resync_order_results would see zero
        # active lines and wipe the pathology order/results.
        for line in bill.lines:
            line.is_active = False
        for line in new_lines:
            bill.lines.append(line)

        if data.doctor_id is not None:
            bill.doctor_id = data.doctor_id
        if data.referring_doctor is not None:
            bill.referring_doctor = data.referring_doctor
        if data.payment_mode_id is not None:
            bill.payment_mode_id = data.payment_mode_id
        if data.department_id is not None:
            bill.department_id = data.department_id
        if data.is_cash is not None:
            bill.is_cash = data.is_cash
        bill.scheme = data.scheme
        bill.admin_charges = data.admin_charges
        bill.scheme_discount = data.scheme_discount
        bill.adjust_advance = data.adjust_advance
        bill.remarks = data.remarks
        bill.gross_amount = gross
        bill.net_amount = net
        bill.status = "modified"
        if entered_by_user_id:
            bill.created_by_user_id = entered_by_user_id
        if data.sample_no is not None and bill.order and bill.order.is_active:
            bill.order.sample_no = data.sample_no
        if data.sample_date is not None and bill.order and bill.order.is_active:
            bill.order.sample_date = data.sample_date

        await self.session.flush()
        # Rebuild the order's result rows so the report matches the edited lines
        # and reflects any result values entered on the bill.
        await PathologyOrderService(self.session).resync_order_results(bill.id)
        # Resync may expire related attributes via populate_existing; reload fully.
        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved)  # type: ignore[arg-type]

    def _summary_to_read(self, bill: PathologyBill) -> PathologyBillSummaryRead:
        order_status = None
        sample_no = None
        sample_date = None
        if bill.order and bill.order.is_active:
            order_status = bill.order.status
            sample_no = bill.order.sample_no
            sample_date = bill.order.sample_date
        return PathologyBillSummaryRead(
            id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            doctor_name=bill.doctor.full_name if bill.doctor else None,
            department_name=bill.department.name if bill.department else None,
            net_amount=bill.net_amount,
            gross_amount=bill.gross_amount,
            order_status=order_status,
            sample_no=sample_no,
            sample_date=sample_date,
            payment_mode_name=bill.payment_mode.name if bill.payment_mode else None,
            created_at=bill.created_at,
        )

    async def list_bills_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list[PathologyBillSummaryRead]:
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
                return []
            resolved_patient_id = patient.id
        bills = await self.repo.list_by_patient_id(resolved_patient_id)
        return [self._summary_to_read(bill) for bill in bills]

    async def get_bill(self, bill_id: str) -> PathologyBillRead:
        bill = await self.repo.get_with_lines(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return self._bill_to_read(bill)

    async def cancel_bill(
        self,
        bill_id: str,
        *,
        reason: str,
        cancelled_by_user_id: str | None = None,
    ) -> PathologyBillRead:
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

        for line in bill.lines:
            line.is_active = False
        if bill.order and bill.order.is_active:
            bill.order.is_active = False

        note = f"CANCELLED: {reason}"
        bill.remarks = f"{bill.remarks}\n{note}" if bill.remarks else note
        bill.status = "cancelled"
        bill.is_active = False
        if cancelled_by_user_id:
            bill.created_by_user_id = bill.created_by_user_id or cancelled_by_user_id

        await self.session.flush()
        # Reload so server-side onupdate fields (updated_at) are available for response.
        saved = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(saved or bill)

    async def get_bill_by_no(self, bill_no: str) -> PathologyBillRead:
        bill = await self.repo.get_by_bill_no(bill_no.strip().upper())
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        full = await self.repo.get_with_lines(bill.id)
        return self._bill_to_read(full)  # type: ignore[arg-type]

    async def list_bills(
        self,
        *,
        bill_date: date | None = None,
        search: str | None = None,
    ) -> list[PathologyBillRead]:
        stmt = (
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.doctor),
                selectinload(PathologyBill.payment_mode),
                selectinload(PathologyBill.department),
                selectinload(PathologyBill.lines),
                selectinload(PathologyBill.order),
            )
            .where(PathologyBill.is_active.is_(True))
            .order_by(PathologyBill.created_at.desc())
            .limit(200)
        )
        if bill_date:
            stmt = stmt.where(PathologyBill.bill_date == bill_date)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.join(PathologyBill.patient).where(
                or_(
                    PathologyBill.bill_no.ilike(term),
                    Patient.patient_no.ilike(term),
                    Patient.first_name.ilike(term),
                    Patient.last_name.ilike(term),
                )
            )
        result = await self.session.execute(stmt)
        bills = list(result.scalars().unique().all())
        return [self._bill_to_read(bill) for bill in bills]
