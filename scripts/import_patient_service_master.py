r"""Replace patient services from the patient_service_master.xlsx export.

The worksheet has three columns: cd, cname, rate (a header row is auto-skipped).

This is a REPLACE, not a merge:
  - Existing PATIENT services (every patient_service_masters row whose category is
    NOT the pathology "LAB" category) are deleted first.
  - PATHOLOGY services (category code "LAB") are left completely untouched.
  - The worksheet rows are then inserted fresh with code PS{cd} (no clash with the
    pathology P{cd} codes), rate + service_charge from the file, under the GEN
    (General) category.

Safety: the script aborts if any of the patient services being deleted are still
referenced by a bill/package (they are not in a fresh setup). Use --dry-run to
preview without writing.

Usage (from the backend folder, using its venv):
  cd backend
  .\.venv\Scripts\python.exe ..\scripts\import_patient_service_master.py --dry-run
  .\.venv\Scripts\python.exe ..\scripts\import_patient_service_master.py
  .\.venv\Scripts\python.exe ..\scripts\import_patient_service_master.py --xlsx "C:\path\file.xlsx"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.patient_service_master import PatientServiceMaster  # noqa: E402
from app.models.service_category import ServiceCategory  # noqa: E402

DEFAULT_XLSX = r"C:\Users\tss\OneDrive\Desktop\patient_service_master.xlsx"

# Pathology services live under this category and must never be touched here.
PATHOLOGY_CATEGORY_CODE = "LAB"
# New patient services are filed under General by default (the file has no category).
TARGET_CATEGORY_CODE = "GEN"

# Tables that reference patient_service_masters.id. We refuse to hard-delete a
# patient service that is still referenced anywhere, to protect historical bills.
REFERENCING = [
    ("opd_bill_lines", "service_id"),
    ("ipd_bill_lines", "service_id"),
    ("short_bill_types", "default_service_id"),
    ("billing_package_items", "service_id"),
    ("pathology_bill_lines", "service_id"),
    ("pathology_service_members", "bundle_service_id"),
    ("pathology_service_members", "member_service_id"),
    ("pathology_service_parameters", "service_id"),
    ("pathology_result_templates", "service_id"),
    ("pathology_results", "service_id"),
]


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value).strip() or "0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def load_rows(path: Path) -> list[tuple[int, str, Decimal]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    rows: list[tuple[int, str, Decimal]] = []
    for raw in ws.iter_rows(values_only=True):
        if not raw or len(raw) < 2:
            continue
        cd_raw, name_raw = raw[0], raw[1]
        rate_raw = raw[2] if len(raw) > 2 else 0
        name = "" if name_raw is None else str(name_raw).strip()
        if not name:
            continue
        # Skip the header row.
        if str(cd_raw).strip().lower() == "cd" and name.lower() == "cname":
            continue
        try:
            cd = int(float(str(cd_raw).strip()))
        except (TypeError, ValueError):
            continue
        rows.append((cd, name[:200], _to_decimal(rate_raw)))
    return rows


async def _count_blocking_refs(session, service_ids: list[str]) -> dict[str, int]:
    """Return a map of referencing table -> count, for any blocking references."""
    if not service_ids:
        return {}
    from sqlalchemy import text

    blocking: dict[str, int] = {}
    for table, col in REFERENCING:
        try:
            n = (
                await session.execute(
                    text(
                        f"SELECT count(*) FROM {table} WHERE {col} = ANY(:ids)"
                    ),
                    {"ids": service_ids},
                )
            ).scalar() or 0
        except Exception:  # noqa: BLE001 — table may not exist on older schemas
            await session.rollback()
            continue
        if n:
            blocking[f"{table}.{col}"] = n
    return blocking


async def replace_services(
    rows: list[tuple[int, str, Decimal]], *, dry_run: bool = False
) -> dict:
    stats: dict = {
        "pathology_kept": 0,
        "patient_deleted": 0,
        "patient_created": 0,
        "blocking_refs": {},
        "aborted": False,
    }

    async with AsyncSessionLocal() as session:
        lab_cat = (
            await session.execute(
                select(ServiceCategory).where(
                    ServiceCategory.code == PATHOLOGY_CATEGORY_CODE
                )
            )
        ).scalar_one_or_none()
        if not lab_cat:
            raise RuntimeError(
                f"Pathology category '{PATHOLOGY_CATEGORY_CODE}' not found — run migrations first"
            )

        target_cat = (
            await session.execute(
                select(ServiceCategory).where(
                    ServiceCategory.code == TARGET_CATEGORY_CODE
                )
            )
        ).scalar_one_or_none()
        if not target_cat:
            raise RuntimeError(
                f"Target category '{TARGET_CATEGORY_CODE}' not found — run migrations first"
            )

        stats["pathology_kept"] = (
            await session.execute(
                select(func.count())
                .select_from(PatientServiceMaster)
                .where(PatientServiceMaster.category_id == lab_cat.id)
            )
        ).scalar() or 0

        # Old PATIENT services = everything that is not pathology (LAB).
        old_services = (
            await session.execute(
                select(PatientServiceMaster).where(
                    PatientServiceMaster.category_id.is_distinct_from(lab_cat.id)
                )
            )
        ).scalars().all()
        old_ids = [s.id for s in old_services]

        blocking = await _count_blocking_refs(session, old_ids)
        if blocking:
            stats["blocking_refs"] = blocking
            stats["aborted"] = True
            await session.rollback()
            return stats

        if old_ids:
            result = await session.execute(
                delete(PatientServiceMaster).where(
                    PatientServiceMaster.id.in_(old_ids)
                )
            )
            stats["patient_deleted"] = result.rowcount or 0

        # Insert the new patient services from the worksheet.
        for cd, name, rate in rows:
            session.add(
                PatientServiceMaster(
                    code=f"PS{cd}",
                    name=name,
                    service_charge=rate,
                    rate=rate,
                    is_sharing=False,
                    discount_apply=False,
                    is_renewal=False,
                    is_service_active=True,
                    is_active=True,
                    category_id=target_cat.id,
                )
            )
            stats["patient_created"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace patient services from patient_service_master.xlsx (keeps pathology)"
    )
    parser.add_argument("--xlsx", default=DEFAULT_XLSX, help="Path to the .xlsx worksheet")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    args = parser.parse_args()

    path = Path(args.xlsx)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return 1

    rows = load_rows(path)
    if not rows:
        print("ERROR: No service rows parsed from the worksheet")
        return 1

    # Guard against duplicate codes (duplicate cd) in the worksheet.
    codes = [cd for cd, _, _ in rows]
    dupes = {c for c in codes if codes.count(c) > 1}
    if dupes:
        print(f"ERROR: Duplicate 'cd' values in worksheet: {sorted(dupes)}")
        return 1

    print(f"Parsed {len(rows)} patient services from {path.name}")

    stats = asyncio.run(replace_services(rows, dry_run=args.dry_run))

    if stats["aborted"]:
        print("ABORTED — some old patient services are still referenced by bills/packages:")
        for ref, n in stats["blocking_refs"].items():
            print(f"  {ref}: {n} reference(s)")
        print("No changes were made. Resolve these references before re-running.")
        return 2

    action = "Would apply (dry-run)" if args.dry_run else "Applied"
    print(
        f"{action}: pathology services kept (untouched)={stats['pathology_kept']}; "
        f"old patient services deleted={stats['patient_deleted']}; "
        f"new patient services created={stats['patient_created']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
