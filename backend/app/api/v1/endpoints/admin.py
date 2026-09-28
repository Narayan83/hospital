"""Administrative / database-maintenance endpoints.

These power the "Clear Database" tool in the desktop Settings screen, used when
handing the software to a new hospital (or re-using masters for a similar one).
All operations are admin-only and additionally guarded by a maintenance
password so they can never run by accident.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User

router = APIRouter()

# Simple maintenance password gate. Anyone clearing the DB must type this.
CLEAR_DB_PASSWORD = "2015"

# Tables that must NEVER be cleared, even if asked. Hospital information lives
# in `hospital_profile`; `alembic_version` tracks the schema migration state.
# Users, roles, menus and permissions are also protected: without them nobody
# could log in or even reach Settings to use this tool.
PROTECTED_TABLES = {
    "hospital_profile",
    "alembic_version",
    "users",
    "user_types",
    "user_role_mappings",
    "roles",
    "role_menu_permissions",
    "menus",
}

# Group ordering for the UI (lower = shown first).
GROUP_ORDER = {
    "Patient Data": 10,
    "OPD / Billing": 20,
    "IPD / Admissions": 30,
    "Pathology Transactions": 40,
    "Pharmacy Transactions": 50,
    "Other Transactions": 60,
    "Patient & Number Setup": 70,
    "Service / Billing Masters": 80,
    "Pathology Masters": 90,
    "Pharmacy Masters": 100,
    "Hospital Configuration": 110,
    "Users & Security": 120,
    "Protected": 999,
    "Other": 500,
}

# table -> (Group, default_selected). default_selected=True means the table is
# pre-ticked for clearing (typically day-to-day transactional data). Master /
# configuration tables default to unticked so they survive a reset by default.
TABLE_CLASSIFICATION: dict[str, tuple[str, bool]] = {
    # --- Patient data -----------------------------------------------------
    "patients": ("Patient Data", True),
    "patient_documents": ("Patient Data", True),
    "patient_document_views": ("Patient Data", True),
    # --- OPD / billing ----------------------------------------------------
    "opd_bills": ("OPD / Billing", True),
    "opd_bill_lines": ("OPD / Billing", True),
    "opd_bill_payments": ("OPD / Billing", True),
    "opd_tokens": ("OPD / Billing", True),
    # --- IPD --------------------------------------------------------------
    "ipd_admissions": ("IPD / Admissions", True),
    "ipd_bills": ("IPD / Admissions", True),
    "ipd_bill_lines": ("IPD / Admissions", True),
    "ipd_bill_payments": ("IPD / Admissions", True),
    "ipd_discharge_summaries": ("IPD / Admissions", True),
    # --- Pathology transactions ------------------------------------------
    "pathology_bills": ("Pathology Transactions", True),
    "pathology_bill_lines": ("Pathology Transactions", True),
    "pathology_orders": ("Pathology Transactions", True),
    "pathology_results": ("Pathology Transactions", True),
    # --- Pharmacy transactions -------------------------------------------
    "pharmacy_sale_bills": ("Pharmacy Transactions", True),
    "pharmacy_sale_bill_lines": ("Pharmacy Transactions", True),
    "pharmacy_purchase_bills": ("Pharmacy Transactions", True),
    "pharmacy_purchase_bill_lines": ("Pharmacy Transactions", True),
    # --- Other transactions ----------------------------------------------
    "short_bills": ("Other Transactions", True),
    "cashbook_vouchers": ("Other Transactions", True),
    "cashbook_voucher_lines": ("Other Transactions", True),
    # --- Patient & number setup ------------------------------------------
    "number_sequences": ("Patient & Number Setup", False),
    "patient_no_formats": ("Patient & Number Setup", False),
    "prefixes": ("Patient & Number Setup", False),
    # --- Service / billing masters ---------------------------------------
    "service_categories": ("Service / Billing Masters", False),
    "service_sub_categories": ("Service / Billing Masters", False),
    "patient_service_masters": ("Service / Billing Masters", False),
    "billing_packages": ("Service / Billing Masters", False),
    "billing_package_items": ("Service / Billing Masters", False),
    "billing_structure_mappings": ("Service / Billing Masters", False),
    "billing_types": ("Service / Billing Masters", False),
    "procedure_types": ("Service / Billing Masters", False),
    "short_bill_types": ("Service / Billing Masters", False),
    "payment_modes": ("Service / Billing Masters", False),
    # --- Pathology masters -----------------------------------------------
    "pathology_units": ("Pathology Masters", False),
    "pathology_parameters": ("Pathology Masters", False),
    "pathology_service_parameters": ("Pathology Masters", False),
    "pathology_service_members": ("Pathology Masters", False),
    "pathology_normal_ranges": ("Pathology Masters", False),
    "pathology_result_templates": ("Pathology Masters", False),
    "service_notes": ("Pathology Masters", False),
    # --- Pharmacy masters -------------------------------------------------
    "pharmacy_code_masters": ("Pharmacy Masters", False),
    "pharmacy_items": ("Pharmacy Masters", False),
    "pharmacy_suppliers": ("Pharmacy Masters", False),
    "pharmacy_group_mappings": ("Pharmacy Masters", False),
    # --- Hospital configuration ------------------------------------------
    "hospital_sections": ("Hospital Configuration", False),
    "departments": ("Hospital Configuration", False),
    "wards": ("Hospital Configuration", False),
    "doctors": ("Hospital Configuration", False),
    "authorities": ("Hospital Configuration", False),
    "ledgers": ("Hospital Configuration", False),
    "letter_templates": ("Hospital Configuration", False),
    "print_configs": ("Hospital Configuration", False),
    "notification_setups": ("Hospital Configuration", False),
}


def _label(table_name: str) -> str:
    return table_name.replace("_", " ").title()


async def require_admin(user: User = Depends(get_current_user)) -> User:
    roles = {m.role.role_name for m in user.role_mappings if m.role}
    is_admin = "Super Admin" in roles or (
        user.user_type is not None and user.user_type.sort_order == 1
    )
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can perform database maintenance.",
        )
    return user


class TableInfo(BaseModel):
    name: str
    label: str
    group: str
    group_order: int
    row_count: int
    default_selected: bool
    protected: bool


class ClearTablesRequest(BaseModel):
    password: str = Field(..., description="Maintenance password")
    tables: list[str] = Field(default_factory=list)


class ClearTablesResponse(BaseModel):
    cleared: list[str]
    skipped_protected: list[str]
    total_rows_deleted: int
    message: str


async def _list_public_tables(session: AsyncSession) -> list[str]:
    result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
    )
    return [row[0] for row in result.fetchall()]


@router.get("/db-tables", response_model=list[TableInfo])
async def list_db_tables(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[TableInfo]:
    """List every table with its current row count and a suggested selection."""
    tables = await _list_public_tables(session)
    out: list[TableInfo] = []
    for name in tables:
        protected = name in PROTECTED_TABLES
        if protected:
            group, default_selected = "Protected", False
        else:
            group, default_selected = TABLE_CLASSIFICATION.get(name, ("Other", False))
        try:
            count_result = await session.execute(text(f'SELECT COUNT(*) FROM "{name}"'))
            row_count = int(count_result.scalar() or 0)
        except Exception:
            row_count = -1
        out.append(
            TableInfo(
                name=name,
                label=_label(name),
                group=group,
                group_order=GROUP_ORDER.get(group, 500),
                row_count=row_count,
                default_selected=default_selected and not protected,
                protected=protected,
            )
        )
    out.sort(key=lambda t: (t.group_order, t.label))
    return out


@router.post("/clear-tables", response_model=ClearTablesResponse)
async def clear_tables(
    payload: ClearTablesRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> ClearTablesResponse:
    """Empty the selected tables. Resets identity counters so numbering starts fresh.

    Tables are truncated together in a single statement so foreign keys between
    the selected tables are respected. Protected tables (hospital information,
    migration state) are always skipped.
    """
    if payload.password != CLEAR_DB_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect maintenance password.",
        )

    requested = {t.strip() for t in payload.tables if t and t.strip()}
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one table to clear.",
        )

    existing = set(await _list_public_tables(session))
    unknown = requested - existing
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown table(s): {', '.join(sorted(unknown))}",
        )

    skipped_protected = sorted(requested & PROTECTED_TABLES)
    to_clear = sorted(requested - PROTECTED_TABLES)
    if not to_clear:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only protected tables were selected; nothing to clear.",
        )

    total_rows = 0
    for name in to_clear:
        try:
            count_result = await session.execute(text(f'SELECT COUNT(*) FROM "{name}"'))
            total_rows += int(count_result.scalar() or 0)
        except Exception:
            pass

    table_list = ", ".join(f'"{name}"' for name in to_clear)
    try:
        await session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY"))
        await session.commit()
    except Exception as exc:  # noqa: BLE001 - surface DB detail to the operator
        await session.rollback()
        detail = str(getattr(exc, "orig", exc)).strip() or str(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Could not clear the selected tables because another table you "
                "chose to keep still depends on them. Either also select the "
                f"dependent table(s) or keep both.\n\nDatabase said: {detail}"
            ),
        ) from exc

    msg = f"Cleared {len(to_clear)} table(s); about {total_rows} row(s) removed."
    if skipped_protected:
        msg += f" Skipped protected: {', '.join(skipped_protected)}."
    return ClearTablesResponse(
        cleared=to_clear,
        skipped_protected=skipped_protected,
        total_rows_deleted=total_rows,
        message=msg,
    )
