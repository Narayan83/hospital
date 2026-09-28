"""Import legacy path.sql (pservice + pprmtr) into HMS pathology masters.

- pservice.CD  -> lab service + parameter (code P{cd})
- pservice.uncd -> pathology_units (64 remapped to 28 / TSH)
- pservice.RNG* / minrng / maxrng -> normal ranges (gender-aware)
- pprmtr.maincd / subcd -> panel mapping (both are service codes)

Usage:
  cd backend
  python ../scripts/import_legacy_pathology.py "C:/Users/tss/OneDrive/Desktop/path.sql"
  python ../scripts/import_legacy_pathology.py path.sql --dry-run
  python ../scripts/import_legacy_pathology.py path.sql --no-purge
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SHARED = ROOT / "shared"
for path in (BACKEND, SHARED, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sqlalchemy import delete, select, update

from app.core.database import AsyncSessionLocal
from app.models.pathology_normal_range import PathologyNormalRange
from app.models.pathology_order import PathologyResult
from app.models.pathology_parameter import PathologyParameter, PathologyServiceParameter
from app.models.pathology_service_member import PathologyServiceMember
from app.models.pathology_unit import PathologyUnit
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from pathology_legacy_units import (
    legacy_units_for_import,
    normalize_uncd,
    service_code_for_legacy_cd,
)
from pathology_ranges import parse_range_entries_from_row

PSERVICE_COLUMNS = [
    "MKEY",
    "MRK",
    "CD",
    "RATE",
    "CNAME",
    "REMARKS",
    "uncd",
    "STATUS",
    "USER1",
    "DATETIME1",
    "SYSNM",
    "RNG1",
    "rng2",
    "rng3",
    "rng4",
    "rng5",
    "rng6",
    "rng7",
    "rng8",
    "rng9",
    "rng10",
    "rng11",
    "rng12",
    "rng13",
    "rng14",
    "rng15",
    "minrng1",
    "maxrng1",
    "nrng2",
    "nrng3",
    "nrng4",
    "nrng5",
]

QUALITATIVE_TOKENS = (
    "POSITIVE",
    "NEGATIVE",
    "REACTIVE",
    "NON - REACTIVE",
    "NON-REACTIVE",
    "OGCT",
    "NEUTROPHILS",
    "LYMPHOCYTES",
    "MONOCYTES",
    "EOSINOPHILS",
)


def _unquote(value: str) -> str:
    value = value.strip()
    if value.upper() == "NULL":
        return ""
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'").replace("\\'", "'")
    return value


def _split_fields(row_txt: str) -> list[str]:
    fields: list[str] = []
    cur = ""
    in_str = False
    for ch in row_txt:
        if in_str:
            cur += ch
            if ch == "'" and not cur.endswith("\\'"):
                in_str = False
        elif ch == "'":
            in_str = True
            cur += ch
        elif ch == ",":
            fields.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur:
        fields.append(cur.strip())
    return fields


def _parse_insert_rows(sql: str, table: str) -> list[list[str]]:
    match = re.search(
        rf"insert\s+into\s+`{table}`\s*\(([^)]+)\)\s+values\s*(.+?);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        match = re.search(
            rf"insert\s+into\s+`{table}`.*?values\s*(.+?);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []
        blob = match.group(1).strip()
    else:
        blob = match.group(2).strip()

    rows: list[list[str]] = []
    i = 0
    n = len(blob)
    while i < n:
        while i < n and blob[i] != "(":
            i += 1
        if i >= n:
            break
        i += 1
        depth = 1
        buf: list[str] = []
        in_str = False
        while i < n and depth:
            ch = blob[i]
            if in_str:
                buf.append(ch)
                if ch == "'" and (len(buf) < 2 or buf[-2] != "\\"):
                    in_str = False
            elif ch == "'":
                in_str = True
                buf.append(ch)
            elif ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                if depth:
                    buf.append(ch)
            else:
                buf.append(ch)
            i += 1
        row_txt = "".join(buf)
        fields = _split_fields(row_txt)
        if fields:
            rows.append(fields)
    return rows


def _to_int(value: str, default: int = 0) -> int:
    value = _unquote(value)
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _to_decimal(value: str) -> Decimal | None:
    value = _unquote(value).strip()
    if not value:
        return None
    try:
        dec = Decimal(value)
        if dec == 0:
            return None
        return dec
    except InvalidOperation:
        return None


def _infer_data_type(unit_name: str | None, range_text: str) -> str:
    text_blob = f"{unit_name or ''} {range_text}".upper()
    if any(token in text_blob for token in QUALITATIVE_TOKENS):
        return "text"
    return "numeric"


def parse_pservice_sql(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    raw_rows = _parse_insert_rows(text, "pservice")
    parsed: list[dict] = []
    for fields in raw_rows:
        if len(fields) < len(PSERVICE_COLUMNS):
            continue
        row = {col: _unquote(fields[i]) for i, col in enumerate(PSERVICE_COLUMNS)}
        name = (row.get("CNAME") or "").strip()
        if not name:
            continue
        cd = _to_int(row.get("CD", "0"))
        if cd <= 0:
            continue
        status = (row.get("STATUS") or "").strip().upper()
        rate_raw = _unquote(row.get("RATE", ""))
        try:
            rate = Decimal(rate_raw or "0")
        except InvalidOperation:
            rate = Decimal("0")

        uncd = normalize_uncd(_to_int(row.get("uncd", "0")))
        minrng1 = _to_decimal(row.get("minrng1", ""))
        maxrng1 = _to_decimal(row.get("maxrng1", ""))

        parsed.append(
            {
                "legacy_mkey": row.get("MKEY", ""),
                "legacy_cd": cd,
                "code": service_code_for_legacy_cd(cd),
                "name": name[:200],
                "rate": rate,
                "uncd": uncd,
                "is_active": status == "Y",
                "min_value": minrng1,
                "max_value": maxrng1,
                "range_entries": parse_range_entries_from_row(
                    {
                        **{k.lower(): v for k, v in row.items()},
                        "min_value": minrng1,
                        "max_value": maxrng1,
                    }
                ),
                "remarks": (row.get("REMARKS") or "").strip()[:150] or None,
            }
        )

    return parsed


def parse_pprmtr_sql(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    raw_rows = _parse_insert_rows(text, "pprmtr")
    mappings: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for fields in raw_rows:
        if len(fields) < 4:
            continue
        maincd = _to_int(fields[2])
        subcd = _to_int(fields[3])
        if maincd <= 0 or subcd <= 0 or maincd == subcd:
            continue
        key = (maincd, subcd)
        if key in seen:
            continue
        seen.add(key)
        mappings.append({"maincd": maincd, "subcd": subcd})
    return mappings


async def purge_pathology_masters(session, lab_cat_id: str) -> dict[str, int]:
    """Remove old pathology master data before a full re-import."""
    counts = {
        "normal_ranges_deleted": 0,
        "service_parameters_deleted": 0,
        "service_members_deleted": 0,
        "parameters_deleted": 0,
        "units_deleted": 0,
        "lab_services_deactivated": 0,
    }

    # Result rows reference parameters; clear them first to avoid FK violations.
    await session.execute(delete(PathologyResult))

    result = await session.execute(delete(PathologyNormalRange))
    counts["normal_ranges_deleted"] = result.rowcount or 0

    result = await session.execute(delete(PathologyServiceMember))
    counts["service_members_deleted"] = result.rowcount or 0

    result = await session.execute(delete(PathologyServiceParameter))
    counts["service_parameters_deleted"] = result.rowcount or 0

    result = await session.execute(delete(PathologyParameter))
    counts["parameters_deleted"] = result.rowcount or 0

    result = await session.execute(delete(PathologyUnit))
    counts["units_deleted"] = result.rowcount or 0

    result = await session.execute(
        update(PatientServiceMaster)
        .where(PatientServiceMaster.category_id == lab_cat_id)
        .values(is_service_active=False, is_active=False)
    )
    counts["lab_services_deactivated"] = result.rowcount or 0
    await session.flush()
    return counts


async def import_pathology(
    path: Path,
    *,
    dry_run: bool = False,
    purge: bool = True,
) -> dict[str, int]:
    services = parse_pservice_sql(path)
    mappings = parse_pprmtr_sql(path)
    mains_with_children = {m["maincd"] for m in mappings}
    mapped_subs = {m["subcd"] for m in mappings}

    stats: dict[str, int] = {
        "purge": 0,
        "units_created": 0,
        "services_created": 0,
        "services_updated": 0,
        "parameters_created": 0,
        "parameters_updated": 0,
        "ranges_created": 0,
        "bundle_members_created": 0,
        "self_mappings_created": 0,
        "panel_parents_created": 0,
        "skipped_blank_name": 0,
        "skipped_inactive": 0,
    }

    async with AsyncSessionLocal() as session:
        lab_cat = (
            await session.execute(select(ServiceCategory).where(ServiceCategory.code == "LAB"))
        ).scalar_one_or_none()
        if not lab_cat:
            raise RuntimeError("LAB service category not found — run migrations first")

        if purge:
            purge_stats = await purge_pathology_masters(session, lab_cat.id)
            for key, val in purge_stats.items():
                stats[key] = val

        unit_by_legacy: dict[int, PathologyUnit] = {}
        for legacy_cd, (code, name) in legacy_units_for_import().items():
            item = PathologyUnit(
                code=code,
                name=name,
                sort_order=legacy_cd,
                is_active=True,
            )
            session.add(item)
            await session.flush()
            unit_by_legacy[legacy_cd] = item
            stats["units_created"] += 1

        service_by_legacy_cd: dict[int, PatientServiceMaster] = {}
        param_by_legacy_cd: dict[int, PathologyParameter] = {}

        for row in services:
            if not row["is_active"]:
                stats["skipped_inactive"] += 1
                continue

            legacy_cd = row["legacy_cd"]
            unit = unit_by_legacy.get(row["uncd"]) if row["uncd"] > 0 else None
            unit_name = unit.name if unit else None
            range_preview = (
                row["range_entries"][0]["text_range"]
                if row["range_entries"] and row["range_entries"][0].get("text_range")
                else ""
            )
            data_type = _infer_data_type(unit_name, range_preview)

            svc = (
                await session.execute(
                    select(PatientServiceMaster).where(PatientServiceMaster.code == row["code"])
                )
            ).scalar_one_or_none()
            if svc:
                svc.name = row["name"]
                svc.rate = row["rate"]
                svc.service_charge = row["rate"]
                svc.category_id = lab_cat.id
                svc.is_service_active = True
                svc.is_active = True
                stats["services_updated"] += 1
            else:
                svc = PatientServiceMaster(
                    code=row["code"],
                    name=row["name"],
                    rate=row["rate"],
                    service_charge=row["rate"],
                    category_id=lab_cat.id,
                    is_sharing=False,
                    discount_apply=False,
                    is_renewal=False,
                    is_service_active=True,
                    is_active=True,
                )
                session.add(svc)
                stats["services_created"] += 1
            await session.flush()
            service_by_legacy_cd[legacy_cd] = svc

            param_code = row["code"]
            param = (
                await session.execute(
                    select(PathologyParameter).where(PathologyParameter.code == param_code)
                )
            ).scalar_one_or_none()
            if param:
                param.name = row["name"]
                param.unit_id = unit.id if unit else None
                param.data_type = data_type
                param.sort_order = legacy_cd
                param.is_active = True
                stats["parameters_updated"] += 1
            else:
                param = PathologyParameter(
                    code=param_code,
                    name=row["name"],
                    unit_id=unit.id if unit else None,
                    data_type=data_type,
                    sort_order=legacy_cd,
                    is_active=True,
                )
                session.add(param)
                stats["parameters_created"] += 1
            await session.flush()
            param_by_legacy_cd[legacy_cd] = param

            for range_entry in row["range_entries"]:
                session.add(
                    PathologyNormalRange(
                        parameter_id=param.id,
                        gender=range_entry["gender"],
                        age_from_days=range_entry.get("age_from_days", 0),
                        age_to_days=range_entry.get("age_to_days", 36500),
                        min_value=range_entry.get("min_value"),
                        max_value=range_entry.get("max_value"),
                        text_range=range_entry.get("text_range"),
                        unit_id=unit.id if unit else None,
                        sort_order=range_entry.get("sort_order", 0),
                        is_active=True,
                    )
                )
                stats["ranges_created"] += 1

        # Some legacy panels exist only in pprmtr (no pservice row) — create billable parent.
        for main_cd in mains_with_children:
            if main_cd in service_by_legacy_cd:
                continue
            code = service_code_for_legacy_cd(main_cd)
            svc = (
                await session.execute(
                    select(PatientServiceMaster).where(PatientServiceMaster.code == code)
                )
            ).scalar_one_or_none()
            if not svc:
                svc = PatientServiceMaster(
                    code=code,
                    name=f"LAB PANEL {main_cd}",
                    rate=Decimal("0"),
                    service_charge=Decimal("0"),
                    category_id=lab_cat.id,
                    is_sharing=False,
                    discount_apply=False,
                    is_renewal=False,
                    is_service_active=True,
                    is_active=True,
                )
                session.add(svc)
                stats["services_created"] += 1
                stats["panel_parents_created"] += 1
            else:
                svc.name = svc.name or f"LAB PANEL {main_cd}"
                svc.category_id = lab_cat.id
                svc.is_service_active = True
                svc.is_active = True
                stats["services_updated"] += 1
            await session.flush()
            service_by_legacy_cd[main_cd] = svc

        for mapping in mappings:
            main_svc = service_by_legacy_cd.get(mapping["maincd"])
            sub_svc = service_by_legacy_cd.get(mapping["subcd"])
            if not main_svc or not sub_svc:
                continue
            session.add(
                PathologyServiceMember(
                    bundle_service_id=main_svc.id,
                    member_service_id=sub_svc.id,
                    sort_order=mapping["subcd"],
                    is_active=True,
                )
            )
            stats["bundle_members_created"] += 1

        for legacy_cd, svc in service_by_legacy_cd.items():
            if legacy_cd in mapped_subs:
                continue
            if legacy_cd in mains_with_children:
                continue
            param = param_by_legacy_cd.get(legacy_cd)
            if not param:
                continue
            session.add(
                PathologyServiceParameter(
                    service_id=svc.id,
                    parameter_id=param.id,
                    sort_order=0,
                    is_required=True,
                    is_active=True,
                )
            )
            stats["self_mappings_created"] += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy path.sql into pathology masters")
    parser.add_argument(
        "sql",
        nargs="?",
        default=r"c:\Users\tss\OneDrive\Desktop\path.sql",
        help="Path to legacy path.sql",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to DB")
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Do not delete existing pathology masters before import",
    )
    args = parser.parse_args()

    sql_path = Path(args.sql)
    if not sql_path.exists():
        print(f"ERROR: File not found: {sql_path}")
        return 1

    services = parse_pservice_sql(sql_path)
    mappings = parse_pprmtr_sql(sql_path)
    text = sql_path.read_text(encoding="utf-8", errors="ignore")
    raw_rows = _parse_insert_rows(text, "pservice")
    blank_name = sum(
        1
        for fields in raw_rows
        if len(fields) >= len(PSERVICE_COLUMNS)
        and not (_unquote(fields[PSERVICE_COLUMNS.index("CNAME")]) or "").strip()
    )
    print(f"Parsed {len(services)} named pservice rows, {len(mappings)} pprmtr mappings from {sql_path.name}")
    print(
        f"  Legacy SQL has {len(raw_rows)} pservice rows total; "
        f"{blank_name} skipped (blank/whitespace CNAME); "
        f"{len(services)} importable named services"
    )
    print(
        f"  After import: ~{len(services)} parameters + panel parents from pprmtr; "
        f"bundles appear on Bundle/Panel screen, leaf tests on Test Master"
    )
    if services[:3]:
        for sample in services[:3]:
            ranges = len(sample.get("range_entries") or [])
            print(
                f"  sample: cd={sample['legacy_cd']} {sample['code']} | "
                f"{sample['name'][:40]} | uncd={sample['uncd']} | ranges={ranges}"
            )

    stats = asyncio.run(
        import_pathology(sql_path, dry_run=args.dry_run, purge=not args.no_purge)
    )
    prefix = "Would import" if args.dry_run else "Imported"
    print(f"{prefix}: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
