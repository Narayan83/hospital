import re
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.menu import Menu
from app.models.patient_service_master import PatientServiceMaster
from app.models.payment_mode import PaymentMode
from app.models.role_menu_permission import RoleMenuPermission
from app.models.single_service_opd import SingleServiceOpdBill, SingleServiceOpdOption
from app.repositories.patient import PatientRepository
from app.repositories.single_service_opd import (
    SingleServiceOpdBillRepository,
    SingleServiceOpdOptionRepository,
)
from app.schemas.single_service_opd import (
    SingleServiceOpdBillCreate,
    SingleServiceOpdBillRead,
    SingleServiceOpdOptionCreate,
    SingleServiceOpdOptionRead,
    SingleServiceOpdOptionUpdate,
)
from app.services.bill_number import BillNumberService

MENU_CODE_PREFIX = "sso_"


def suggest_prefix(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", (name or "").upper())
    if not words:
        return "SSO"
    if len(words) == 1:
        return words[0][:6]
    return "".join(word[0] for word in words)[:6] or "SSO"


def suggest_menu_code(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    slug = (slug[:40] or "bill")
    return f"{MENU_CODE_PREFIX}{slug}"


class SingleServiceOpdService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.option_repo = SingleServiceOpdOptionRepository(session)
        self.bill_repo = SingleServiceOpdBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.bill_no_svc = BillNumberService(session)

    @staticmethod
    def _option_to_read(item: SingleServiceOpdOption) -> SingleServiceOpdOptionRead:
        service_name = item.service_name or (item.service.name if item.service else "")
        return SingleServiceOpdOptionRead(
            id=item.id,
            name=item.name,
            menu_code=item.menu_code,
            service_id=item.service_id,
            service_name=service_name,
            use_patient_id=item.use_patient_id,
            default_rate=Decimal(str(item.default_rate or 0)),
            bill_prefix=item.bill_prefix,
            sort_order=item.sort_order,
            is_active=item.is_active,
        )

    @staticmethod
    def _bill_to_read(bill: SingleServiceOpdBill) -> SingleServiceOpdBillRead:
        return SingleServiceOpdBillRead(
            id=bill.id,
            bill_no=bill.bill_no,
            bill_date=bill.bill_date,
            option_id=bill.option_id,
            option_name=bill.option.name if bill.option else None,
            patient_id=bill.patient_id,
            patient_no=bill.patient_no,
            patient_name=bill.patient_name,
            doctor_id=bill.doctor_id,
            doctor_name=bill.doctor.full_name if bill.doctor else None,
            service_id=bill.service_id,
            service_name=bill.service_name,
            rate=Decimal(str(bill.rate)),
            payment_mode_name=bill.payment_mode_name or "Cash",
        )

    async def list_options(self) -> list[SingleServiceOpdOptionRead]:
        items = await self.option_repo.list_all()
        return [self._option_to_read(item) for item in items]

    async def get_option_by_menu(self, menu_code: str) -> SingleServiceOpdOptionRead:
        item = await self.option_repo.get_by_menu_code(menu_code)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This billing option is not set up or is inactive.",
            )
        return self._option_to_read(item)

    async def create_option(self, data: SingleServiceOpdOptionCreate) -> SingleServiceOpdOptionRead:
        name = data.name.strip()
        if await self.option_repo.get_by_name(name):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Option name already exists")
        service = await self._require_service(data.service_id)
        prefix = await self._unique_prefix(data.bill_prefix or suggest_prefix(name))
        menu_code = await self._unique_menu_code(suggest_menu_code(name))
        item = SingleServiceOpdOption(
            name=name,
            menu_code=menu_code,
            service_id=service.id,
            service_name=service.name,
            use_patient_id=data.use_patient_id,
            default_rate=float(data.default_rate),
            bill_prefix=prefix,
            sort_order=await self.option_repo.next_sort_order(),
            is_active=data.is_active,
        )
        self.session.add(item)
        await self.session.flush()
        await self._sync_menu(item, grant_permissions=True)
        loaded = await self.option_repo.get_by_id(item.id)
        return self._option_to_read(loaded)  # type: ignore[arg-type]

    async def update_option(
        self, option_id: str, data: SingleServiceOpdOptionUpdate
    ) -> SingleServiceOpdOptionRead:
        item = await self.option_repo.get_by_id(option_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
        payload = data.model_dump(exclude_unset=True)
        if "name" in payload and payload["name"]:
            other = await self.option_repo.get_by_name(payload["name"])
            if other and other.id != item.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Option name already exists"
                )
            item.name = payload["name"].strip()
        if "service_id" in payload and payload["service_id"]:
            service = await self._require_service(payload["service_id"])
            item.service_id = service.id
            item.service_name = service.name
        if "use_patient_id" in payload and payload["use_patient_id"] is not None:
            item.use_patient_id = payload["use_patient_id"]
        if "default_rate" in payload and payload["default_rate"] is not None:
            item.default_rate = float(payload["default_rate"])
        if "bill_prefix" in payload and payload["bill_prefix"]:
            prefix = payload["bill_prefix"].strip().upper()
            self._validate_prefix(prefix)
            other = await self.option_repo.get_by_prefix(prefix)
            if other and other.id != item.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Bill prefix already used"
                )
            item.bill_prefix = prefix
        if "is_active" in payload and payload["is_active"] is not None:
            item.is_active = payload["is_active"]
        await self.session.flush()
        await self._sync_menu(item, grant_permissions=False)
        loaded = await self.option_repo.get_by_id(item.id)
        return self._option_to_read(loaded)  # type: ignore[arg-type]

    async def create_bill(
        self, data: SingleServiceOpdBillCreate, *, user_id: str | None
    ) -> SingleServiceOpdBillRead:
        option = await self.option_repo.get_by_id(data.option_id)
        if not option or not option.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing option not found")
        doctor = await self.session.get(Doctor, data.doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        patient_id, patient_no, patient_name = await self._resolve_patient(option, data)
        payment_mode_id, payment_mode_name = await self._cash_payment_mode()
        bill_no = await self.bill_no_svc.generate_single_service_opd_no(
            option.id,
            option.bill_prefix,
            data.bill_date,
        )
        bill = SingleServiceOpdBill(
            bill_no=bill_no,
            bill_date=data.bill_date,
            option_id=option.id,
            patient_id=patient_id,
            patient_no=patient_no,
            patient_name=patient_name,
            doctor_id=doctor.id,
            service_id=option.service_id,
            service_name=option.service_name,
            rate=float(data.rate),
            payment_mode_id=payment_mode_id,
            payment_mode_name=payment_mode_name,
            created_by_user_id=user_id,
        )
        self.session.add(bill)
        await self.session.flush()
        loaded = await self.bill_repo.get_by_id(bill.id)
        return self._bill_to_read(loaded)  # type: ignore[arg-type]

    async def list_bills(self, option_id: str, bill_date: date) -> list[SingleServiceOpdBillRead]:
        option = await self.option_repo.get_by_id(option_id)
        if not option:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing option not found")
        bills = await self.bill_repo.list_for_option_on_date(option_id, bill_date)
        return [self._bill_to_read(bill) for bill in bills]

    async def cancel_bill(self, bill_id: str) -> SingleServiceOpdBillRead:
        bill = await self.bill_repo.get_by_id(bill_id)
        if not bill or not bill.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        bill.is_active = False
        await self.session.flush()
        return self._bill_to_read(bill)

    async def _resolve_patient(
        self, option: SingleServiceOpdOption, data: SingleServiceOpdBillCreate
    ) -> tuple[str | None, str | None, str]:
        if option.use_patient_id:
            patient_no = (data.patient_no or "").strip()
            patient = None
            if data.patient_id:
                patient = await self.patient_repo.get_by_id(data.patient_id)
            if patient is None and patient_no:
                patient = await self.patient_repo.get_by_patient_no(patient_no)
            if patient is None or not patient.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            return patient.id, patient.patient_no, patient.full_name
        name = (data.patient_name or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Patient name is required"
            )
        return None, None, name

    async def _require_service(self, service_id: str) -> PatientServiceMaster:
        service = await self.session.get(PatientServiceMaster, service_id)
        if not service or not service.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        return service

    async def _cash_payment_mode(self) -> tuple[str | None, str]:
        result = await self.session.execute(
            select(PaymentMode)
            .where(PaymentMode.is_active.is_(True), PaymentMode.is_cash.is_(True))
            .order_by(PaymentMode.sort_order, PaymentMode.name)
        )
        mode = result.scalars().first()
        if mode:
            return mode.id, mode.name
        return None, "Cash"

    @staticmethod
    def _validate_prefix(prefix: str) -> None:
        if not re.fullmatch(r"[A-Z0-9]{1,10}", prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bill prefix must be 1–10 letters or digits",
            )

    async def _unique_prefix(self, prefix: str) -> str:
        base = re.sub(r"[^A-Z0-9]", "", (prefix or "SSO").upper())[:6] or "SSO"
        candidate = base
        suffix = 2
        while await self.option_repo.get_by_prefix(candidate):
            tail = str(suffix)
            candidate = f"{base[: 10 - len(tail)]}{tail}"
            suffix += 1
        self._validate_prefix(candidate)
        return candidate

    async def _unique_menu_code(self, menu_code: str) -> str:
        candidate = menu_code[:80]
        suffix = 2
        while True:
            taken_option = await self.option_repo.get_by_menu(candidate)
            menu_result = await self.session.execute(select(Menu).where(Menu.code == candidate))
            if taken_option is None and menu_result.scalar_one_or_none() is None:
                return candidate
            tail = f"_{suffix}"
            candidate = f"{menu_code[: 80 - len(tail)]}{tail}"
            suffix += 1

    async def _sync_menu(self, option: SingleServiceOpdOption, *, grant_permissions: bool) -> None:
        parent_result = await self.session.execute(select(Menu).where(Menu.code == "billing"))
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Billing menu is not available",
            )
        menu_result = await self.session.execute(select(Menu).where(Menu.code == option.menu_code))
        menu = menu_result.scalar_one_or_none()
        if menu is None:
            menu = Menu(
                code=option.menu_code,
                label=option.name,
                parent_id=parent.id,
                sort_order=100 + option.sort_order,
                is_active=option.is_active,
            )
            self.session.add(menu)
            await self.session.flush()
            if grant_permissions:
                await self._copy_opd_permissions(menu.id)
        else:
            menu.label = option.name
            menu.parent_id = parent.id
            menu.sort_order = 100 + option.sort_order
            menu.is_active = option.is_active
        await self.session.flush()

    async def _copy_opd_permissions(self, menu_id: str) -> None:
        opd_result = await self.session.execute(select(Menu).where(Menu.code == "opd_bill"))
        opd = opd_result.scalar_one_or_none()
        if opd is None:
            return
        perm_result = await self.session.execute(
            select(RoleMenuPermission).where(RoleMenuPermission.menu_id == opd.id)
        )
        for perm in perm_result.scalars().all():
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
