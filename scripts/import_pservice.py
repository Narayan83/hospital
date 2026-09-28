"""Import legacy pservice.sql rows into patient_service_masters.

Deprecated: use import_legacy_pathology.py for full pathology setup
(units, parameters, normal ranges, service-parameter mappings).
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.patient_service_master import PatientServiceMaster


def _unquote(value: str) -> str:
    value = value.strip()
    if value.upper() == "NULL":
        return ""
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'").replace("\\'", "'")
    return value


def parse_pservice_sql(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    values_idx = lower.find("values")
    if values_idx < 0:
        raise ValueError("No VALUES clause found in SQL file")
    blob = text[values_idx + 6 :].strip().rstrip(";")

    rows: list[dict] = []
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
        if len(fields) < 8:
            continue

        mkey = _unquote(fields[0])
        mrk = _unquote(fields[1]).upper()
        cd = _unquote(fields[2])
        rate_raw = _unquote(fields[3])
        name = _unquote(fields[4]).strip()
        status = _unquote(fields[7]).upper()

        if not name:
            continue

        try:
            rate = Decimal(rate_raw or "0")
        except Exception:
            rate = Decimal("0")

        code = f"{mrk}{cd}" if mrk else f"S{mkey}"
        if len(code) > 30:
            code = f"S{mkey}"[:30]

        rows.append(
            {
                "legacy_mkey": mkey,
                "code": code.upper(),
                "name": name[:200],
                "service_charge": rate,
                "rate": rate,
                "is_service_active": status == "Y",
                "is_sharing": False,
                "discount_apply": False,
                "is_renewal": False,
                "is_active": True,
            }
        )

    # Ensure unique codes — suffix with MKEY on collision
    seen: dict[str, int] = {}
    for row in rows:
        base = row["code"]
        if base not in seen:
            seen[base] = 1
            continue
        seen[base] += 1
        suffix = row["legacy_mkey"]
        row["code"] = f"{base[:24]}{suffix}"[:30]

    return rows


async def import_rows(rows: list[dict], *, dry_run: bool = False) -> tuple[int, int, int]:
    created = updated = skipped = 0
    async with AsyncSessionLocal() as session:
        existing = {
            item.code: item
            for item in (await session.execute(select(PatientServiceMaster))).scalars().all()
        }
        for row in rows:
            item = existing.get(row["code"])
            if item:
                changed = (
                    item.name != row["name"]
                    or Decimal(str(item.rate)) != row["rate"]
                    or Decimal(str(item.service_charge)) != row["service_charge"]
                    or item.is_service_active != row["is_service_active"]
                    or not item.is_active
                )
                if changed:
                    item.name = row["name"]
                    item.rate = row["rate"]
                    item.service_charge = row["service_charge"]
                    item.is_service_active = row["is_service_active"]
                    item.is_active = True
                    updated += 1
                else:
                    skipped += 1
                continue

            payload = {k: v for k, v in row.items() if k != "legacy_mkey"}
            session.add(PatientServiceMaster(**payload))
            created += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return created, updated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Import pservice.sql into patient_service_masters")
    parser.add_argument(
        "--sql",
        default=r"c:\Users\tss\OneDrive\Desktop\pservice.sql",
        help="Path to legacy pservice.sql",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to DB")
    args = parser.parse_args()

    sql_path = Path(args.sql)
    if not sql_path.exists():
        print(f"ERROR: File not found: {sql_path}")
        return 1

    rows = parse_pservice_sql(sql_path)
    print(f"Parsed {len(rows)} services from {sql_path.name}")
    if rows[:3]:
        for sample in rows[:3]:
            print(f"  sample: {sample['code']} | {sample['name'][:50]} | rate={sample['rate']}")

    created, updated, skipped = asyncio.run(import_rows(rows, dry_run=args.dry_run))
    action = "Would import" if args.dry_run else "Imported"
    print(f"{action}: created={created}, updated={updated}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
