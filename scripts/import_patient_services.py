r"""Import patient services + their categories from an Excel/CSV worksheet.

The worksheet must have two columns: Service Name, Category (a header row is
optional and auto-skipped). Categories that do not yet exist are created.
Services are created with rate/service_charge = 0 (set prices later from the
Patient Service Master screen). Re-running is safe (idempotent): existing
categories/services are matched by name and only updated, never duplicated.

Usage (from the backend folder, using its venv):
  cd backend
  .\.venv\Scripts\python.exe ..\scripts\import_patient_services.py --xlsx "C:\path\file.xlsx"
  .\.venv\Scripts\python.exe ..\scripts\import_patient_services.py --xlsx "C:\path\file.xlsx" --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory

DEFAULT_XLSX = r"C:\Users\tss\OneDrive\Desktop\New Microsoft Excel Worksheet.xlsx"


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slug_code(name: str, maxlen: int = 30) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return code[:maxlen] or "CAT"


def _unique_code(base: str, used: set[str], maxlen: int = 30) -> str:
    base = base[:maxlen]
    if base not in used:
        return base
    i = 2
    while True:
        suffix = f"_{i}"
        cand = f"{base[: maxlen - len(suffix)]}{suffix}"
        if cand not in used:
            return cand
        i += 1


def load_rows(path: Path) -> list[tuple[str, str]]:
    raw: list[tuple[str, str]] = []
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        import openpyxl

        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            name = _cell(row[0]) if len(row) > 0 else ""
            cat = _cell(row[1]) if len(row) > 1 else ""
            raw.append((name, cat))
    elif suffix == ".csv":
        import csv

        with path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                name = _cell(row[0]) if len(row) > 0 else ""
                cat = _cell(row[1]) if len(row) > 1 else ""
                raw.append((name, cat))
    else:
        raise ValueError(f"Unsupported file type: {suffix} (use .xlsx or .csv)")

    rows: list[tuple[str, str]] = []
    for name, cat in raw:
        if not name or not cat:
            continue
        if name.lower() in {"service name", "service", "name"} and cat.lower() == "category":
            continue
        rows.append((name, cat))
    return rows


def _make_service_code_gen(used: set[str]):
    counter = {"n": 0}

    def gen() -> str:
        while True:
            counter["n"] += 1
            cand = f"PSM{counter['n']:04d}"
            if cand not in used:
                return cand

    return gen


async def import_data(rows: list[tuple[str, str]], *, dry_run: bool = False) -> dict[str, int]:
    stats = {
        "categories_created": 0,
        "categories_existing": 0,
        "services_created": 0,
        "services_updated": 0,
        "services_skipped": 0,
    }

    async with AsyncSessionLocal() as session:
        categories = (await session.execute(select(ServiceCategory))).scalars().all()
        cat_by_name = {c.name.strip().lower(): c for c in categories}
        used_cat_codes = {c.code for c in categories}
        max_sort = max((c.sort_order or 0 for c in categories), default=0)

        # Preserve first-seen order of categories from the worksheet.
        ordered_cats: list[str] = []
        seen_cat: set[str] = set()
        for _, cat in rows:
            key = cat.lower()
            if key not in seen_cat:
                seen_cat.add(key)
                ordered_cats.append(cat)

        for cat in ordered_cats:
            key = cat.lower()
            existing = cat_by_name.get(key)
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                stats["categories_existing"] += 1
                continue
            code = _unique_code(_slug_code(cat), used_cat_codes)
            used_cat_codes.add(code)
            max_sort += 1
            obj = ServiceCategory(code=code, name=cat, sort_order=max_sort, is_active=True)
            session.add(obj)
            await session.flush()
            cat_by_name[key] = obj
            stats["categories_created"] += 1

        services = (await session.execute(select(PatientServiceMaster))).scalars().all()
        svc_by_name = {s.name.strip().lower(): s for s in services}
        used_svc_codes = {s.code for s in services}
        next_code = _make_service_code_gen(used_svc_codes)

        for name, cat in rows:
            category = cat_by_name[cat.lower()]
            existing = svc_by_name.get(name.lower())
            if existing:
                changed = False
                if existing.category_id != category.id:
                    existing.category_id = category.id
                    changed = True
                if not existing.is_active:
                    existing.is_active = True
                    changed = True
                if not existing.is_service_active:
                    existing.is_service_active = True
                    changed = True
                if changed:
                    stats["services_updated"] += 1
                else:
                    stats["services_skipped"] += 1
                continue

            code = next_code()
            used_svc_codes.add(code)
            obj = PatientServiceMaster(
                code=code,
                name=name[:200],
                service_charge=0,
                rate=0,
                category_id=category.id,
                is_service_active=True,
                is_active=True,
            )
            session.add(obj)
            svc_by_name[name.lower()] = obj
            stats["services_created"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import patient services + categories from an Excel/CSV worksheet"
    )
    parser.add_argument("--xlsx", default=DEFAULT_XLSX, help="Path to the .xlsx/.csv worksheet")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    args = parser.parse_args()

    path = Path(args.xlsx)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return 1

    rows = load_rows(path)
    print(f"Parsed {len(rows)} services from {path.name}")
    cats = sorted({cat for _, cat in rows})
    print(f"Categories in file ({len(cats)}): {', '.join(cats)}")

    stats = asyncio.run(import_data(rows, dry_run=args.dry_run))
    action = "Would apply (dry-run)" if args.dry_run else "Applied"
    print(
        f"{action}: "
        f"categories created={stats['categories_created']}, existing={stats['categories_existing']}; "
        f"services created={stats['services_created']}, "
        f"updated={stats['services_updated']}, skipped={stats['services_skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
