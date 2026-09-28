from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_shortcut import DashboardShortcut
from app.models.menu import Menu
from app.models.user import User
from app.schemas.dashboard_shortcut import (
    DashboardShortcutBulkSave,
    DashboardShortcutCreate,
    DashboardShortcutRead,
)

DEFAULT_HOST = "dashboard"
EMPTY_MARKER = "_empty"
HIDDEN_FROM_PICKER = {"dashboard", "dashboard_shortcut_setup", "print_template_designer"}

DEFAULT_SHORTCUTS = (
    ("opd_bill", "OPD", "Outpatient billing", 1),
    ("ipd_bill", "IPD", "Inpatient billing", 2),
    ("pathology_bill", "Pathology", "Pathology billing", 3),
    ("doctor_wise_collection_report", "Doctor Collection", "Doctor wise collection report", 4),
)


def _norm_host(code: str | None) -> str:
    value = (code or DEFAULT_HOST).strip().lower()
    return value or DEFAULT_HOST


class DashboardShortcutService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_shortcuts(
        self,
        user: User,
        *,
        host_code: str = DEFAULT_HOST,
        active_only: bool = True,
    ) -> list[DashboardShortcutRead]:
        await self.ensure_defaults()
        host = _norm_host(host_code)
        rows = await self._rows_for_user(user.id, host)
        if active_only:
            rows = [row for row in rows if row.is_active]
        return [DashboardShortcutRead.model_validate(row) for row in rows]

    async def list_available_menus(self, *, host_code: str = DEFAULT_HOST) -> list[dict]:
        host = _norm_host(host_code)
        result = await self.session.execute(
            select(Menu).where(Menu.is_active.is_(True)).order_by(Menu.label)
        )
        menus = list(result.scalars().all())
        parent_ids = {menu.parent_id for menu in menus if menu.parent_id}
        leaves = []
        for menu in menus:
            if menu.id in parent_ids or menu.code in HIDDEN_FROM_PICKER or menu.code == host:
                continue
            leaves.append({"code": menu.code, "label": menu.label, "parent_id": menu.parent_id})
        return leaves

    async def ensure_defaults(self) -> None:
        result = await self.session.execute(
            select(DashboardShortcut.id).where(DashboardShortcut.user_id.is_(None)).limit(1)
        )
        if result.scalar_one_or_none():
            return
        any_row = await self.session.execute(select(DashboardShortcut.id).limit(1))
        if any_row.scalar_one_or_none():
            return
        for code, label, desc, order in DEFAULT_SHORTCUTS:
            self.session.add(
                DashboardShortcut(
                    user_id=None,
                    host_code=DEFAULT_HOST,
                    module_code=code,
                    button_label=label,
                    description=desc,
                    sort_order=order,
                    is_active=True,
                )
            )
        await self.session.flush()

    async def save_all(self, user: User, data: DashboardShortcutBulkSave) -> list[DashboardShortcutRead]:
        host = _norm_host(data.host_code)
        await self._replace_user_host(user.id, host, data.items)
        return await self.list_shortcuts(user, host_code=host, active_only=False)

    async def create_shortcut(self, user: User, data: DashboardShortcutCreate) -> DashboardShortcutRead:
        host = _norm_host(data.host_code)
        module_code = data.module_code.strip()
        if module_code in HIDDEN_FROM_PICKER or module_code.startswith("_") or module_code == host:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That menu cannot be pinned here")
        existing = await self._owned_rows(user.id, host)
        if not existing:
            shared = await self._shared_rows(host)
            for row in shared:
                if row.module_code == module_code:
                    continue
                self.session.add(self._copy_row(row, user.id))
        else:
            for row in existing:
                if row.module_code == module_code:
                    row.button_label = data.button_label.strip()
                    row.description = (data.description or "").strip() or None
                    row.is_active = data.is_active
                    await self.session.flush()
                    return DashboardShortcutRead.model_validate(row)
            for row in list(existing):
                if row.module_code.startswith("_"):
                    await self.session.delete(row)
        created = DashboardShortcut(
            user_id=user.id,
            host_code=host,
            module_code=module_code,
            button_label=data.button_label.strip(),
            description=(data.description or "").strip() or None,
            sort_order=data.sort_order or 999,
            is_active=data.is_active,
        )
        self.session.add(created)
        await self.session.flush()
        return DashboardShortcutRead.model_validate(created)

    async def delete_shortcut(self, user: User, shortcut_id: str) -> None:
        from fastapi import HTTPException, status

        row = await self.session.get(DashboardShortcut, shortcut_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found")
        host = row.host_code or DEFAULT_HOST
        if row.user_id and row.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found")
        if row.user_id is None:
            shared = [item for item in await self._shared_rows(host) if item.id != row.id and not item.module_code.startswith("_")]
            await self._replace_user_host(
                user.id,
                host,
                [
                    type("Item", (), {
                        "module_code": item.module_code,
                        "button_label": item.button_label,
                        "description": item.description,
                        "sort_order": item.sort_order,
                        "is_active": item.is_active,
                    })()
                    for item in shared
                ],
            )
            return
        await self.session.delete(row)
        await self.session.flush()
        remaining = [
            item
            for item in await self._owned_rows(user.id, host)
            if not item.module_code.startswith("_")
        ]
        if not remaining:
            self.session.add(
                DashboardShortcut(
                    user_id=user.id,
                    host_code=host,
                    module_code=EMPTY_MARKER,
                    button_label="(none)",
                    sort_order=0,
                    is_active=False,
                )
            )
            await self.session.flush()

    async def _rows_for_user(self, user_id: str, host: str) -> list[DashboardShortcut]:
        owned = await self._owned_rows(user_id, host)
        if owned:
            return [row for row in owned if not row.module_code.startswith("_")]
        return [row for row in await self._shared_rows(host) if not row.module_code.startswith("_")]

    async def _owned_rows(self, user_id: str, host: str) -> list[DashboardShortcut]:
        result = await self.session.execute(
            select(DashboardShortcut)
            .where(DashboardShortcut.user_id == user_id, DashboardShortcut.host_code == host)
            .order_by(DashboardShortcut.sort_order, DashboardShortcut.button_label)
        )
        return list(result.scalars().all())

    async def _shared_rows(self, host: str) -> list[DashboardShortcut]:
        result = await self.session.execute(
            select(DashboardShortcut)
            .where(DashboardShortcut.user_id.is_(None), DashboardShortcut.host_code == host)
            .order_by(DashboardShortcut.sort_order, DashboardShortcut.button_label)
        )
        return list(result.scalars().all())

    async def _replace_user_host(self, user_id: str, host: str, items: list) -> None:
        for row in await self._owned_rows(user_id, host):
            await self.session.delete(row)
        await self.session.flush()
        real = [item for item in items if (item.module_code or "").strip() and not item.module_code.startswith("_")]
        if not real:
            self.session.add(
                DashboardShortcut(
                    user_id=user_id,
                    host_code=host,
                    module_code=EMPTY_MARKER,
                    button_label="(none)",
                    sort_order=0,
                    is_active=False,
                )
            )
        for index, item in enumerate(real):
            self.session.add(
                DashboardShortcut(
                    user_id=user_id,
                    host_code=host,
                    module_code=item.module_code.strip(),
                    button_label=item.button_label.strip(),
                    description=(item.description or "").strip() or None,
                    sort_order=item.sort_order if item.sort_order else index + 1,
                    is_active=item.is_active,
                )
            )
        await self.session.flush()

    @staticmethod
    def _copy_row(row: DashboardShortcut, user_id: str) -> DashboardShortcut:
        return DashboardShortcut(
            user_id=user_id,
            host_code=row.host_code,
            module_code=row.module_code,
            button_label=row.button_label,
            description=row.description,
            sort_order=row.sort_order,
            is_active=row.is_active,
        )
