#!/usr/bin/env python3
"""Import legacy MySQL dump (details, dmaster, pmaster) into PostgreSQL.

Only rows with MRK IS NULL are imported.
- details  -> hospital_profile (hospital settings)
- dmaster  -> doctors
- pmaster  -> patients

All transactional data is cleared first, including users. A fresh Super Admin
(admin@admin.com / admin123) is created after import. Other master config
(menus, departments, etc.) is kept.

Usage:
  cd backend
  python ../scripts/import_legacy_customer.py "C:/path/to/22062026.sql"
  python ../scripts/import_legacy_customer.py "C:/path/to/22062026.sql" --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

# Allow running from repo root or backend folder.
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

# Transactional / operational tables to empty before import.
TABLES_TO_TRUNCATE = [
    "pharmacy_sale_bill_lines",
    "pharmacy_sale_bills",
    "pharmacy_purchase_bill_lines",
    "pharmacy_purchase_bills",
    "cashbook_voucher_lines",
    "cashbook_vouchers",
    "opd_bill_lines",
    "opd_bill_payments",
    "opd_bills",
    "ipd_bill_lines",
    "ipd_bill_payments",
    "ipd_bills",
    "pathology_bill_lines",
    "pathology_bills",
    "pathology_results",
    "pathology_orders",
    "short_bills",
    "opd_tokens",
    "ipd_discharge_summaries",
    "ipd_admissions",
    "patient_document_views",
    "patient_documents",
    "notification_setups",
    "number_sequences",
    "patients",
    "doctors",
    "hospital_profile",
    "user_role_mappings",
    "users",
]


def parse_insert(sql: str, table: str) -> tuple[list[str], list[str]]:
    match = re.search(
        rf"insert\s+into\s+`{table}`\(([^)]+)\)\s+values\s*(.+?);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return [], []

    columns = [part.strip().strip("`") for part in match.group(1).split(",")]
    raw = match.group(2).strip()
    rows: list[str] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(raw):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                rows.append(raw[start:index])
    return columns, rows


def split_fields(row: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    in_string = False
    escaped = False
    for char in row:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if char == "'":
            in_string = not in_string
            current.append(char)
            continue
        if char == "," and not in_string:
            fields.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    fields.append("".join(current).strip())
    return fields


def unquote(value: str):
    if value.upper() == "NULL":
        return None
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def row_dict(columns: list[str], row: str) -> dict[str, object | None]:
    values = split_fields(row)
    return {columns[index]: unquote(values[index]) for index in range(len(columns))}


def is_mrk_null(row: dict[str, object | None]) -> bool:
    mrk = row.get("MRK")
    return mrk is None or str(mrk).strip() == ""


def parse_legacy_date(value: object | None) -> date | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value or text_value.startswith("0000-"):
        return None
    try:
        return datetime.strptime(text_value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_gender(value: object | None) -> str:
    text_value = (str(value).strip().upper() if value else "") or "U"
    if text_value in {"M", "F", "O", "U"}:
        return text_value
    if text_value in {"MALE"}:
        return "M"
    if text_value in {"FEMALE"}:
        return "F"
    return "U"


def clip(value: object | None, max_len: int) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    return text_value[:max_len]


def parse_int(value: object | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def load_legacy_rows(sql_path: Path) -> dict[str, list[dict[str, object | None]]]:
    sql = sql_path.read_text(encoding="utf-8", errors="replace")
    result: dict[str, list[dict[str, object | None]]] = {}
    for table in ("details", "dmaster", "pmaster"):
        columns, rows = parse_insert(sql, table)
        filtered = [row_dict(columns, row) for row in rows if is_mrk_null(row_dict(columns, row))]
        result[table] = filtered
    return result


def map_hospital_profile(row: dict[str, object | None]) -> dict[str, object]:
    add1 = str(row.get("ADD1") or "").strip()
    phone1 = str(row.get("PHONE1") or "").strip()
    addph = str(row.get("ADDPH") or "").strip()
    return {
        "code": "MAIN",
        "name": str(row.get("MHD") or "Hospital").strip() or "Hospital",
        "address_line1": add1 or None,
        "address_line2": str(row.get("HD") or "").strip() or None,
        "address_line3": str(row.get("SHD") or "").strip() or None,
        "phone": phone1 or None,
        "mobile": addph or None,
        "email": str(row.get("EMAIL") or "").strip() or None,
        "gstin": str(row.get("GSTIN") or "").strip() or None,
        "software_id": str(row.get("SFTCD") or "").strip() or None,
    }


def map_doctor(row: dict[str, object | None], department_by_sort: dict[int, str]) -> dict[str, object]:
    did = parse_int(row.get("DID"))
    dept_sort = parse_int(row.get("DPRTCD"), default=-1)
    status = str(row.get("STATUS") or "Y").strip().upper()
    pdoc = str(row.get("pdoc") or "N").strip().upper()
    return {
        "doctor_code": clip(f"D{did:04d}" if did else f"LEG{parse_int(row.get('MKEY')):04d}", 20),
        "title": clip(row.get("SLTN"), 20),
        "first_name": clip(row.get("FRST"), 100) or "Doctor",
        "second_name": clip(row.get("SEND"), 100),
        "third_name": clip(row.get("THRD"), 100),
        "date_of_birth": parse_legacy_date(row.get("DOB")),
        "sex": parse_gender(row.get("SEX")) if row.get("SEX") else None,
        "perm_village": str(row.get("VILG") or "").strip() or None,
        "perm_post": str(row.get("POST") or "").strip() or None,
        "perm_taluk": str(row.get("TALUK") or "").strip() or None,
        "perm_district": str(row.get("DIST") or "").strip() or None,
        "perm_pincode": str(row.get("PIN") or "").strip() or None,
        "temp_village": str(row.get("PVILG") or "").strip() or None,
        "temp_post": str(row.get("PPOST") or "").strip() or None,
        "temp_taluk": str(row.get("PTALUK") or "").strip() or None,
        "temp_district": str(row.get("PDIST") or "").strip() or None,
        "temp_pincode": str(row.get("PPIN") or "").strip() or None,
        "remarks": str(row.get("REMARKS") or "").strip() or None,
        "phone": clip(row.get("PHONE"), 20),
        "mobile": clip(row.get("MOB1"), 20),
        "mobile2": clip(row.get("MOB2"), 20),
        "join_date": parse_legacy_date(row.get("DOA")),
        "qualification": str(row.get("QLFTION") or "").strip() or None,
        "department_id": department_by_sort.get(dept_sort),
        "register_no": str(row.get("REGNO") or "").strip() or None,
        "release_date": parse_legacy_date(row.get("DOR")),
        "morning_token_start": parse_int(row.get("STKNNO")),
        "evening_token_start": parse_int(row.get("ESTKNNO")),
        "is_pathology_doctor": pdoc == "Y",
        "is_active": status in {"", "Y", "YES", "1"},
        "is_existing": True,
        "is_reference_doctor": parse_int(row.get("REFDOC")) > 0,
    }


def map_patient(
    row: dict[str, object | None],
    section_by_sort: dict[int, str],
    patient_no: str,
) -> dict[str, object]:
    status = str(row.get("STATUS") or "").strip().upper()
    return {
        "patient_no": clip(patient_no, 20),
        "hospital_section_id": section_by_sort.get(parse_int(row.get("HSPSEC"), default=-1)),
        "title": clip(row.get("SLTN"), 10),
        "first_name": clip(row.get("FRST"), 100) or "Patient",
        "middle_name": clip(row.get("SEND"), 100),
        "last_name": clip(row.get("THRD"), 100),
        "date_of_birth": parse_legacy_date(row.get("DOB")),
        "age": (f"{parse_int(row.get('AGE'), default=0)} Years" if str(row.get("AGE") or "").strip() else None),
        "gender": clip(parse_gender(row.get("SEX")), 10) or "U",
        "blood_group": clip(row.get("BLDGRP"), 10),
        "contact_address1": clip(row.get("VILG"), 200),
        "contact_address2": clip(row.get("POST"), 200),
        "contact_address3": clip(row.get("TALUK"), 200),
        "contact_address4": clip(row.get("DIST"), 200),
        "contact_address5": clip(row.get("PIN"), 20),
        "perm_address1": clip(row.get("PVILG"), 200),
        "perm_address2": clip(row.get("PPOST"), 200),
        "perm_address3": clip(row.get("PTALUK"), 200),
        "perm_address4": clip(row.get("PDIST"), 200),
        "perm_address5": clip(row.get("PPIN"), 20),
        "old_software_id": clip(row.get("opid") or row.get("PID"), 50),
        "remarks": clip(row.get("REMARKS"), 5000),
        "phone": clip(row.get("PHONE"), 20),
        "mobile": clip(row.get("MOB1"), 20),
        "mobile2": clip(row.get("MOB2"), 20),
        "scheme": clip(row.get("SCHM"), 100),
        "is_existing_patient": status in {"Y", "YES", "1"},
        "patient_type": clip(row.get("PTYPE"), 50),
        "is_active": status not in {"N", "NO", "0"},
    }


def unique_patient_numbers(rows: list[dict[str, object | None]]) -> list[tuple[dict[str, object | None], str]]:
    used: Counter[str] = Counter()
    result: list[tuple[dict[str, object | None], str]] = []
    for index, row in enumerate(rows, start=1):
        raw_pid = str(row.get("PID") or "").strip()
        base = raw_pid or f"LEG{parse_int(row.get('MKEY'), default=index):06d}"
        base = base[:20]
        patient_no = base
        if used[patient_no]:
            suffix = 2
            while True:
                candidate = f"{base[:17]}-{suffix}"
                if not used[candidate]:
                    patient_no = candidate
                    break
                suffix += 1
        used[patient_no] += 1
        result.append((row, patient_no))
    return result


async def ensure_admin_user(session: AsyncSession) -> None:
    import app.models  # noqa: F401 — register all ORM mappers before bootstrap

    from app.core.security import get_password_hash
    from app.seeds.bootstrap import _seed_roles, _seed_super_admin, _seed_user_types

    role_map = await _seed_roles(session)
    user_type_map = await _seed_user_types(session)
    await _seed_super_admin(session, role_map["Super Admin"], user_type_map["admin"])
    await session.execute(
        text(
            """
            UPDATE users
            SET hashed_password = :hashed_password,
                full_name = 'Super Admin',
                is_active = true
            WHERE email = :email
            """
        ),
        {
            "hashed_password": get_password_hash("admin123"),
            "email": "admin@admin.com",
        },
    )


async def clear_operational_data(session: AsyncSession, dry_run: bool) -> None:
    if dry_run:
        return
    await session.execute(text("UPDATE users SET doctor_id = NULL WHERE doctor_id IS NOT NULL"))
    existing = await session.execute(
        text(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY(:names)
            """
        ),
        {"names": TABLES_TO_TRUNCATE},
    )
    present = [row[0] for row in existing.fetchall()]
    ordered = [name for name in TABLES_TO_TRUNCATE if name in present]
    if ordered:
        table_list = ", ".join(ordered)
        await session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))


async def load_lookup_maps(session: AsyncSession) -> tuple[dict[int, str], dict[int, str]]:
    dept_rows = await session.execute(text("SELECT id, sort_order FROM departments"))
    department_by_sort = {int(row.sort_order): str(row.id) for row in dept_rows.fetchall()}

    section_rows = await session.execute(text("SELECT id, sort_order, code FROM hospital_sections"))
    section_by_sort: dict[int, str] = {}
    for row in section_rows.fetchall():
        section_by_sort[int(row.sort_order)] = str(row.id)
        if str(row.code).isdigit():
            section_by_sort[int(row.code)] = str(row.id)
    return department_by_sort, section_by_sort


async def import_legacy(sql_path: Path, dry_run: bool) -> None:
    legacy = load_legacy_rows(sql_path)
    details_rows = legacy["details"]
    doctor_rows = legacy["dmaster"]
    patient_rows = legacy["pmaster"]

    print(f"Legacy rows (MRK IS NULL): details={len(details_rows)}, doctors={len(doctor_rows)}, patients={len(patient_rows)}")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        department_by_sort, section_by_sort = await load_lookup_maps(session)
        await clear_operational_data(session, dry_run)

        if details_rows:
            profile_data = map_hospital_profile(details_rows[0])
            print(f"Hospital: {profile_data['name']}")
            if not dry_run:
                await session.execute(
                    text(
                        """
                        INSERT INTO hospital_profile (
                            id, code, name, address_line1, address_line2, address_line3,
                            phone, mobile, email, gstin, software_id,
                            created_at, updated_at
                        ) VALUES (
                            :id, :code, :name, :address_line1, :address_line2, :address_line3,
                            :phone, :mobile, :email, :gstin, :software_id,
                            NOW(), NOW()
                        )
                        """
                    ),
                    {"id": str(uuid4()), **profile_data},
                )
        elif not dry_run:
            print("Warning: no details row with MRK NULL — hospital_profile not updated.")

        for row in doctor_rows:
            doctor_data = map_doctor(row, department_by_sort)
            print(f"Doctor: {doctor_data['doctor_code']} {doctor_data['first_name']}")
            if not dry_run:
                await session.execute(
                    text(
                        """
                        INSERT INTO doctors (
                            id, doctor_code, title, first_name, second_name, third_name,
                            date_of_birth, sex, perm_village, perm_post, perm_taluk, perm_district, perm_pincode,
                            temp_village, temp_post, temp_taluk, temp_district, temp_pincode,
                            remarks, phone, mobile, mobile2, join_date, qualification, department_id,
                            register_no, release_date, morning_token_start, evening_token_start,
                            is_pathology_doctor, is_active, is_existing, is_reference_doctor,
                            created_at, updated_at
                        ) VALUES (
                            :id, :doctor_code, :title, :first_name, :second_name, :third_name,
                            :date_of_birth, :sex, :perm_village, :perm_post, :perm_taluk, :perm_district, :perm_pincode,
                            :temp_village, :temp_post, :temp_taluk, :temp_district, :temp_pincode,
                            :remarks, :phone, :mobile, :mobile2, :join_date, :qualification, :department_id,
                            :register_no, :release_date, :morning_token_start, :evening_token_start,
                            :is_pathology_doctor, :is_active, :is_existing, :is_reference_doctor,
                            NOW(), NOW()
                        )
                        """
                    ),
                    {"id": str(uuid4()), **doctor_data},
                )

        patient_pairs = unique_patient_numbers(patient_rows)
        if not dry_run:
            batch: list[dict[str, object]] = []
            insert_sql = text(
                """
                INSERT INTO patients (
                    id, patient_no, hospital_section_id, title, first_name, middle_name, last_name,
                    date_of_birth, age, gender, blood_group,
                    contact_address1, contact_address2, contact_address3, contact_address4, contact_address5,
                    perm_address1, perm_address2, perm_address3, perm_address4, perm_address5,
                    old_software_id, remarks, phone, mobile, mobile2, scheme,
                    is_existing_patient, patient_type, is_active,
                    created_at, updated_at
                ) VALUES (
                    :id, :patient_no, :hospital_section_id, :title, :first_name, :middle_name, :last_name,
                    :date_of_birth, :age, :gender, :blood_group,
                    :contact_address1, :contact_address2, :contact_address3, :contact_address4, :contact_address5,
                    :perm_address1, :perm_address2, :perm_address3, :perm_address4, :perm_address5,
                    :old_software_id, :remarks, :phone, :mobile, :mobile2, :scheme,
                    :is_existing_patient, :patient_type, :is_active,
                    NOW(), NOW()
                )
                """
            )
            for row, patient_no in patient_pairs:
                patient_data = map_patient(row, section_by_sort, patient_no)
                batch.append({"id": str(uuid4()), **patient_data})
                if len(batch) >= 500:
                    await session.execute(insert_sql, batch)
                    batch.clear()
            if batch:
                await session.execute(insert_sql, batch)
        else:
            print(f"Patients ready to import: {len(patient_pairs)}")

        if dry_run:
            await session.rollback()
            print("Dry run complete — no database changes made.")
        else:
            await ensure_admin_user(session)
            await session.commit()
            print("Import complete.")
            print("Admin user: admin@admin.com / admin123")

    await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy HMS MySQL dump into PostgreSQL.")
    parser.add_argument("sql_file", type=Path, help="Path to legacy .sql dump (e.g. 22062026.sql)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report only; do not change DB.")
    args = parser.parse_args()

    if not args.sql_file.is_file():
        print(f"File not found: {args.sql_file}", file=sys.stderr)
        return 1

    asyncio.run(import_legacy(args.sql_file.resolve(), args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
