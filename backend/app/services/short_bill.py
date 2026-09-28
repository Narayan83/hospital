import re
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Menu
from app.models.role_menu_permission import RoleMenuPermission
from app.models.short_bill import ShortBill, ShortBillType
from app.repositories.patient import PatientRepository
from app.repositories.short_bill import ShortBillRepository, ShortBillTypeRepository
from app.schemas.short_bill import (
    ShortBillCreate,
    ShortBillRead,
    ShortBillReportRead,
    ShortBillReportRow,
    ShortBillTypeCreate,
    ShortBillTypeRead,
    ShortBillTypeUpdate,
    ShortBillUpdate,
)
from app.services.bill_number import BillNumberService


class ShortBillService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.type_repo = ShortBillTypeRepository(session)
        self.bill_repo = ShortBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.bill_no_svc = BillNumberService(session)

    @staticmethod
    def _type_to_read(item: ShortBillType) -> ShortBillTypeRead:
        return ShortBillTypeRead(
            id=item.id,
            code=item.code,
            name=item.name,
            menu_code=item.menu_code,
            default_service_id=item.default_service_id,
            default_service_name=(
                item.default_service_name
                or (item.default_service.name if item.default_service else None)
            ),
            default_rate=Decimal(str(item.default_rate)),
            default_doctor_id=item.default_doctor_id,
            default_doctor_name=item.default_doctor.full_name if item.default_doctor else None,
            bill_prefix=item.bill_prefix,
            sort_order=item.sort_order,
            is_active=item.is_active,
        )

    @staticmethod
    def _bill_to_read(bill: ShortBill) -> ShortBillRead:
        return ShortBillRead(
            id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            short_bill_type_id=bill.short_bill_type_id,
            short_bill_type_name=bill.bill_type.name if bill.bill_type else None,
            patient_id=bill.patient_id,
            patient_no=bill.patient.patient_no if bill.patient else None,
            patient_name=bill.patient_name,
            service_name=bill.service_name,
            amount=Decimal(str(bill.amount)),
            doctor_id=bill.doctor_id,
            doctor_name=bill.doctor.full_name if bill.doctor else None,
        )

    async def list_types(self) -> list[ShortBillTypeRead]:
        items = await self.type_repo.list_all()
        return [self._type_to_read(item) for item in items]

    async def get_type(self, type_id: str) -> ShortBillTypeRead:
        item = await self.type_repo.get_by_id(type_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")
        return self._type_to_read(item)

    async def get_type_by_menu(self, menu_code: str) -> ShortBillTypeRead:
        item = await self.type_repo.get_by_menu_code(menu_code)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No short bill master configured for menu '{menu_code}'",
            )
        return self._type_to_read(item)

    async def create_type(self, data: ShortBillTypeCreate) -> ShortBillTypeRead:
        existing_menu = None
        if data.menu_code:
            existing_menu = await self.type_repo.get_by_menu_code(data.menu_code)
        if existing_menu:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Menu code already mapped")
        payload = data.model_dump()
        payload["code"] = await self._unique_code(data.name, data.code)
        payload["menu_code"] = await self._unique_menu_code(data.name, data.menu_code)
        item = ShortBillType(**payload)
        self.session.add(item)
        await self.session.flush()
        await self._sync_transaction_menu(item, grant_permissions=True)
        await self.session.refresh(item)
        loaded = await self.type_repo.get_by_id(item.id)
        return self._type_to_read(loaded)  # type: ignore[arg-type]

    async def update_type(self, type_id: str, data: ShortBillTypeUpdate) -> ShortBillTypeRead:
        item = await self.type_repo.get_by_id(type_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.session.flush()
        await self._sync_transaction_menu(item, grant_permissions=False)
        loaded = await self.type_repo.get_by_id(type_id)
        return self._type_to_read(loaded)  # type: ignore[arg-type]

    async def delete_type(self, type_id: str) -> ShortBillTypeRead:
        item = await self.type_repo.get_by_id(type_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")
        snapshot = self._type_to_read(item)
        bill_count = await self.bill_repo.count_for_type(type_id)
        if bill_count:
            item.is_active = False
            await self._set_generated_menu_active(item.menu_code, False)
            await self.session.flush()
            return snapshot
        await self._remove_generated_menu(item.menu_code)
        await self.session.delete(item)
        await self.session.flush()
        return snapshot

    async def _set_generated_menu_active(self, menu_code: str, active: bool) -> None:
        if not (menu_code or "").startswith("sbt_"):
            return
        result = await self.session.execute(select(Menu).where(Menu.code == menu_code))
        menu = result.scalar_one_or_none()
        if menu is not None:
            menu.is_active = active

    async def _remove_generated_menu(self, menu_code: str) -> None:
        if not (menu_code or "").startswith("sbt_"):
            return
        result = await self.session.execute(select(Menu).where(Menu.code == menu_code))
        menu = result.scalar_one_or_none()
        if menu is None:
            return
        await self.session.execute(
            delete(RoleMenuPermission).where(RoleMenuPermission.menu_id == menu.id)
        )
        await self.session.delete(menu)

    async def _unique_menu_code(self, name: str, requested: str | None) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
        base = (requested or f"sbt_{slug or 'bill'}")[:50]
        candidate = base
        suffix = 2
        while True:
            taken = await self.type_repo.get_by_menu_any(candidate)
            menu_result = await self.session.execute(select(Menu).where(Menu.code == candidate))
            if taken is None and menu_result.scalar_one_or_none() is None:
                return candidate
            tail = f"_{suffix}"
            candidate = f"{base[: 50 - len(tail)]}{tail}"
            suffix += 1

    async def _sync_transaction_menu(
        self, item: ShortBillType, *, grant_permissions: bool
    ) -> None:
        """The saved name becomes a menu under Transactions, tied to the chosen service."""
        parent_result = await self.session.execute(select(Menu).where(Menu.code == "transactions"))
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transactions menu is not available",
            )
        menu_result = await self.session.execute(select(Menu).where(Menu.code == item.menu_code))
        menu = menu_result.scalar_one_or_none()
        if menu is None:
            menu = Menu(
                code=item.menu_code,
                label=item.name,
                parent_id=parent.id,
                sort_order=40 + int(item.sort_order or 0),
                legacy_form="SHRTBL",
                parameters=item.default_service_id,
                is_active=item.is_active,
            )
            self.session.add(menu)
            await self.session.flush()
            if grant_permissions:
                await self._copy_transaction_permissions(menu.id)
        else:
            menu.label = item.name
            menu.parent_id = parent.id
            menu.sort_order = 40 + int(item.sort_order or 0)
            menu.legacy_form = menu.legacy_form or "SHRTBL"
            menu.parameters = item.default_service_id
            menu.is_active = item.is_active
        await self.session.flush()

    async def _copy_transaction_permissions(self, menu_id: str) -> None:
        seen: set[str] = set()
        for source_code in ("opd_bill", "scan_bill"):
            source_result = await self.session.execute(select(Menu).where(Menu.code == source_code))
            source = source_result.scalar_one_or_none()
            if source is None:
                continue
            perm_result = await self.session.execute(
                select(RoleMenuPermission).where(RoleMenuPermission.menu_id == source.id)
            )
            for perm in perm_result.scalars().all():
                if perm.role_id in seen:
                    continue
                seen.add(perm.role_id)
                self.session.add(
                    RoleMenuPermission(
                        role_id=perm.role_id,
                        menu_id=menu_id,
                        can_view=perm.can_view,
                        can_create=perm.can_create,
                        can_update=perm.can_update,
                        can_delete=perm.can_delete,
                    )
                )
        await self.session.flush()

    async def _unique_code(self, name: str, requested: str | None) -> str:
        words = re.findall(r"[A-Za-z0-9]+", (name or "").upper())
        if len(words) >= 2:
            base = "".join(word[0] for word in words)
        elif words:
            base = words[0]
        else:
            base = "SB"
        typed = re.sub(r"[^A-Z0-9]", "", (requested or "").upper())
        base = (typed or base)[:20] or "SB"
        candidate = base
        suffix = 2
        while await self.type_repo.get_by_code(candidate):
            tail = str(suffix)
            candidate = f"{base[: 30 - len(tail)]}{tail}"
            suffix += 1
        return candidate

    async def create_bill(
        self,
        data: ShortBillCreate,
        *,
        user_id: str | None,
    ) -> ShortBillRead:
        bill_type = await self.type_repo.get_by_id(data.short_bill_type_id)
        if not bill_type or not bill_type.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")

        patient_name = data.patient_name.strip()
        if data.patient_id:
            patient = await self.patient_repo.get_by_id(data.patient_id)
            if not patient:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            if not patient_name:
                patient_name = " ".join(
                    part for part in [patient.first_name, patient.middle_name, patient.last_name] if part
                )

        bill_no = await self.bill_no_svc.generate_short_bill_no(
            bill_type.bill_prefix,
            bill_type.code,
            data.bill_date,
        )
        bill = ShortBill(
            bill_no=bill_no,
            bill_date=data.bill_date,
            short_bill_type_id=data.short_bill_type_id,
            patient_id=data.patient_id,
            patient_name=patient_name,
            service_name=data.service_name.strip(),
            amount=float(data.amount),
            doctor_id=data.doctor_id or bill_type.default_doctor_id,
            created_by_user_id=user_id,
        )
        self.session.add(bill)
        await self.session.flush()
        loaded = await self.bill_repo.get_by_id(bill.id)
        return self._bill_to_read(loaded)  # type: ignore[arg-type]

    async def update_bill(self, bill_id: str, data: ShortBillUpdate) -> ShortBillRead:
        bill = await self.bill_repo.get_by_id(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        payload = data.model_dump(exclude_unset=True)
        if "patient_id" in payload and payload["patient_id"]:
            patient = await self.patient_repo.get_by_id(payload["patient_id"])
            if not patient:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        for field, value in payload.items():
            if field == "amount" and value is not None:
                value = float(value)
            setattr(bill, field, value)
        await self.session.flush()
        loaded = await self.bill_repo.get_by_id(bill_id)
        return self._bill_to_read(loaded)  # type: ignore[arg-type]

    async def delete_bill(self, bill_id: str) -> ShortBillRead:
        bill = await self.bill_repo.get_by_id(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        bill.is_active = False
        await self.session.flush()
        return self._bill_to_read(bill)

    async def get_bill(self, bill_id: str) -> ShortBillRead:
        bill = await self.bill_repo.get_by_id(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return self._bill_to_read(bill)

    async def search_bills(self, *, short_bill_type_id: str, query: str) -> list[ShortBillRead]:
        text = query.strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a bill number or name")
        bill_type = await self.type_repo.get_by_id(short_bill_type_id)
        if not bill_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")
        bills = await self.bill_repo.search(short_bill_type_id, text)
        return [self._bill_to_read(bill) for bill in bills]

    async def build_report(
        self,
        *,
        short_bill_type_id: str,
        from_date: date,
        to_date: date,
    ) -> ShortBillReportRead:
        if from_date > to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="From date cannot be after To date",
            )
        bill_type = await self.type_repo.get_by_id(short_bill_type_id)
        if not bill_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short bill type not found")

        bills = await self.bill_repo.list_by_type_and_dates(short_bill_type_id, from_date, to_date)
        rows = [
            ShortBillReportRow(
                serial_no=index,
                bill_id=bill.id,
                bill_no=bill.bill_no,
                bill_date=bill.bill_date,
                patient_name=bill.patient_name,
                amount=Decimal(str(bill.amount)),
            )
            for index, bill in enumerate(bills, start=1)
        ]
        grand_total = sum((row.amount for row in rows), Decimal("0"))
        return ShortBillReportRead(
            short_bill_type_id=bill_type.id,
            short_bill_type_name=bill_type.name,
            from_date=from_date,
            to_date=to_date,
            rows=rows,
            grand_total=grand_total,
        )
