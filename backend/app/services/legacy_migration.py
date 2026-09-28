"""Live MySQL (legacy HMS) → PostgreSQL migration helpers.

Default table mappings follow the old software:
  pmaster  → patients          (MRK IS NULL)
  dmaster  → doctors           (MRK IS NULL)
  osrmstr  → patient_service_masters (MRK IS NULL)
  rcd      → patient_documents (MRK IS NULL)
  cshYYYY  → cashbook_vouchers (+ lines)
  trnYYYY  → opd_bills (SW=1) / ipd bills (SW=2)
  pservice/pprmtr → pathology masters (optional; often already imported)
"""
from __future__ import annotations

import contextvars
import logging
import re
import traceback
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_logger = logging.getLogger("hms.legacy_migration")

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
_progress_cb: contextvars.ContextVar[ProgressCallback | None] = contextvars.ContextVar(
    "legacy_migration_progress",
    default=None,
)
_table_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "legacy_migration_table",
    default=None,
)


async def _emit_progress(event: dict[str, Any]) -> None:
    callback = _progress_cb.get()
    if callback is not None:
        await callback(event)


def _tick_every(total: int, *, slow: bool = False) -> int:
    """How many rows to process between UI progress updates."""
    if slow or total <= 80:
        return 1
    return min(200, max(1, total // 40))


class _RowTicker:
    """Emit processed / total counts while a table is written."""

    def __init__(self, total: int, *, unit: str = "rows", slow: bool = False):
        self.total = max(int(total), 0)
        self.unit = unit
        self.step = _tick_every(self.total, slow=slow)
        self.index = 0

    async def __call__(self, **counts: Any) -> None:
        self.index += 1
        if self.total and self.index != self.total and self.index % self.step != 0:
            return
        ctx = dict(_table_ctx.get() or {})
        await _emit_progress(
            {
                "type": "rows",
                **ctx,
                "processed": self.index,
                "total": self.total,
                "unit": self.unit,
                **counts,
            }
        )

DEFAULT_MYSQL_ODBC = (
    "Driver={MySQL ODBC 3.51 Driver};Server=localhost;Database=hsp;User=root;Password=;"
)

# Default MySQL WHERE clause for active (non-deleted) legacy rows.
DEFAULT_SOURCE_FILTER = "(MRK IS NULL OR TRIM(MRK) = '')"

# Catalog shown in the UI. `legacy_table` and `source_filter` are editable.
DEFAULT_MAPPINGS: list[dict[str, Any]] = [
    {
        "key": "hospital",
        "label": "Hospital Profile",
        "legacy_table": "details",
        "target_tables": ["hospital_profile"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Masters",
        "notes": "Hospital name / address from legacy details.",
    },
    {
        "key": "doctors",
        "label": "Doctor Master",
        "legacy_table": "dmaster",
        "target_tables": ["doctors"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Masters",
        "notes": "DID → doctor_code D####.",
    },
    {
        "key": "patients",
        "label": "Patient Master",
        "legacy_table": "pmaster",
        "target_tables": ["patients"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Masters",
        "notes": "PID kept as patient_no; stored also in old_software_id.",
    },
    {
        "key": "services",
        "label": "Patient Service Master",
        "legacy_table": "osrmstr",
        "target_tables": ["patient_service_masters"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Masters",
        "notes": "CD → service code PS{cd}.",
    },
    {
        "key": "pathology",
        "label": "Pathology Masters",
        "legacy_table": "pservice",
        "target_tables": [
            "pathology_units",
            "pathology_parameters",
            "pathology_service_parameters",
            "pathology_service_members",
            "pathology_normal_ranges",
            "patient_service_masters",
        ],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL (also uses pprmtr)",
        "default_selected": False,
        "group": "Pathology (already mapped)",
        "notes": "Optional re-import. pservice + pprmtr → lab tests / panels / ranges.",
    },
    {
        "key": "opd_ipd_bills",
        "label": "OPD / IPD Bills",
        "legacy_table": "trn2627",
        "target_tables": ["opd_bills", "opd_bill_lines", "ipd_admissions", "ipd_bills", "ipd_bill_lines"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "SW 1=OPD, SW 2=IPD (SW 3 counted as IPD-related)",
        "default_selected": True,
        "group": "Transactions",
        "notes": "Year table (trnYYZZ). Edit name for other years (trn2526, trn2425, …).",
    },
    {
        "key": "cashbook",
        "label": "Cashbook",
        "legacy_table": "csh2627",
        "target_tables": ["cashbook_vouchers", "cashbook_voucher_lines"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Transactions",
        "notes": "Year table (cshYYZZ). Maps to cash ledger vouchers.",
    },
    {
        "key": "documents",
        "label": "Patient Documents",
        "legacy_table": "rcd",
        "target_tables": ["patient_documents"],
        "source_filter": DEFAULT_SOURCE_FILTER,
        "filter_note": "MRK IS NULL",
        "default_selected": True,
        "group": "Transactions",
        "notes": "DOC blob saved under patient-documents storage.",
    },
]

MIGRATE_ORDER = [
    "hospital",
    "doctors",
    "patients",
    "services",
    "pathology",
    "opd_ipd_bills",
    "cashbook",
    "documents",
]


def display_postgres_url(database_url: str | None = None) -> str:
    """Human-editable PostgreSQL URL (without asyncpg driver suffix)."""
    url = database_url or get_settings().database_url
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    # strip ssl=disable query used for Windows asyncpg
    url = re.sub(r"[?&]ssl=disable", "", url)
    url = url.rstrip("?&")
    return url


def parse_mysql_connection(conn_str: str) -> dict[str, Any]:
    """Parse ODBC-style or mysql:// URL into pymysql connect kwargs."""
    raw = (conn_str or "").strip()
    if not raw:
        raise ValueError("MySQL connection string is empty.")

    if raw.lower().startswith("mysql://") or raw.lower().startswith("mysql+"):
        # mysql://user:pass@host:port/db
        m = re.match(
            r"mysql(?:\+\w+)?://([^:@]+)(?::([^@]*))?@([^:/]+)(?::(\d+))?/([^?]+)",
            raw,
            re.IGNORECASE,
        )
        if not m:
            raise ValueError("Could not parse MySQL URL.")
        user, password, host, port, database = m.groups()
        return {
            "host": host,
            "port": int(port or 3306),
            "user": user,
            "password": password or "",
            "database": database,
            "charset": "utf8",
        }

    parts: dict[str, str] = {}
    # ODBC: Driver={...};Server=...;Database=...;User=...;Password=...;
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    host = parts.get("server") or parts.get("host") or "localhost"
    database = parts.get("database") or parts.get("db")
    user = parts.get("user") or parts.get("uid") or "root"
    password = parts.get("password") or parts.get("pwd") or ""
    port = int(parts.get("port") or 3306)
    if not database:
        raise ValueError("MySQL connection string must include Database=...")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "charset": "utf8",
    }


def _connect_mysql(conn_str: str):
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:
        raise RuntimeError(
            "pymysql is required for live MySQL migration. "
            "Install it with: pip install pymysql"
        ) from exc

    kwargs = parse_mysql_connection(conn_str)
    return pymysql.connect(cursorclass=DictCursor, connect_timeout=8, **kwargs)


def test_mysql_connection(conn_str: str) -> dict[str, Any]:
    conn = _connect_mysql(conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version, DATABASE() AS db")
            row = cur.fetchone() or {}
            cur.execute("SHOW TABLES")
            tables = [list(r.values())[0] for r in cur.fetchall()]
        return {
            "ok": True,
            "message": f"Connected to MySQL {row.get('version')} / database {row.get('db')}",
            "version": row.get("version"),
            "database": row.get("db"),
            "table_count": len(tables),
            "tables": sorted(tables),
        }
    finally:
        conn.close()


def test_postgres_connection(pg_url: str) -> dict[str, Any]:
    """Sync-style check via async engine (run from async endpoint)."""
    url = (pg_url or "").strip()
    if not url:
        raise ValueError("PostgreSQL connection string is empty.")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = url.replace("@localhost:", "@127.0.0.1:")
    if "127.0.0.1" in url and "ssl=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}ssl=disable"
    return {"normalized_url": url, "display_url": display_postgres_url(url)}


def _mrk_null_sql(alias: str = "") -> str:
    if not alias:
        return DEFAULT_SOURCE_FILTER
    col = f"{alias}.MRK"
    # MySQL 5.6: treat blank MRK as active too
    return f"({col} IS NULL OR TRIM({col}) = '')"


def _safe_where(clause: str | None) -> str:
    """Validate a user-supplied WHERE fragment (no multi-statement injection)."""
    raw = (clause or "").strip()
    if not raw:
        return _mrk_null_sql()
    lowered = raw.lower()
    if ";" in raw or "--" in raw or "/*" in raw or "*/" in raw:
        raise ValueError(f"Invalid filter condition: {raw!r}")
    for banned in (
        " into ",
        " outfile",
        " dumpfile",
        " load_file",
        " sleep(",
        "benchmark(",
        " information_schema",
        " performance_schema",
    ):
        if banned in f" {lowered}":
            raise ValueError(f"Invalid filter condition: {raw!r}")
    return raw


def _clip(value: Any, max_len: int) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    return text_value[:max_len]


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text_value = str(value).strip()
    if not text_value or text_value.startswith("0000-"):
        return None
    try:
        return datetime.strptime(text_value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_gender(value: Any) -> str:
    text_value = (str(value).strip().upper() if value else "") or "U"
    if text_value in {"M", "F", "O", "U"}:
        return text_value
    if text_value == "MALE":
        return "M"
    if text_value == "FEMALE":
        return "F"
    return "U"


def _parse_int(value: Any, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _parse_decimal(value: Any, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _safe_ident(name: str) -> str:
    cleaned = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned):
        raise ValueError(f"Invalid table name: {name!r}")
    return cleaned


def preview_legacy_counts(
    mysql_conn_str: str,
    mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conn = _connect_mysql(mysql_conn_str)
    out: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            existing = {list(r.values())[0].lower() for r in cur.fetchall()}
            for item in mappings:
                table = _safe_ident(str(item.get("legacy_table") or ""))
                key = item.get("key")
                where = _safe_where(item.get("source_filter"))
                present = table.lower() in existing
                count = None
                extra = {}
                if present:
                    if key == "opd_ipd_bills":
                        cur.execute(
                            f"SELECT SW, COUNT(*) AS c FROM `{table}` "
                            f"WHERE {where} GROUP BY SW"
                        )
                        by_sw = {int(r["SW"]): int(r["c"]) for r in cur.fetchall()}
                        count = sum(by_sw.values())
                        extra = {
                            "opd_rows": by_sw.get(1, 0),
                            "ipd_rows": by_sw.get(2, 0) + sum(
                                v for k, v in by_sw.items() if k not in (1, 2)
                            ),
                        }
                    elif key == "pathology":
                        cur.execute(
                            f"SELECT COUNT(*) AS c FROM `{table}` WHERE {where}"
                        )
                        count = int((cur.fetchone() or {}).get("c") or 0)
                        pprmtr = "pprmtr" if "pprmtr" in existing else None
                        if pprmtr:
                            cur.execute(
                                f"SELECT COUNT(*) AS c FROM `pprmtr` WHERE {where}"
                            )
                            extra["pprmtr_rows"] = int((cur.fetchone() or {}).get("c") or 0)
                    else:
                        cur.execute(
                            f"SELECT COUNT(*) AS c FROM `{table}` WHERE {where}"
                        )
                        count = int((cur.fetchone() or {}).get("c") or 0)
                out.append(
                    {
                        "key": key,
                        "label": item.get("label"),
                        "legacy_table": table,
                        "exists": present,
                        "source_rows": count,
                        **extra,
                    }
                )
    finally:
        conn.close()
    return out


async def load_lookups(session: AsyncSession) -> dict[str, Any]:
    dept_rows = await session.execute(text("SELECT id, sort_order FROM departments"))
    department_by_sort = {int(row.sort_order): str(row.id) for row in dept_rows.fetchall()}

    section_rows = await session.execute(
        text("SELECT id, sort_order, code FROM hospital_sections")
    )
    section_by_sort: dict[int, str] = {}
    for row in section_rows.fetchall():
        section_by_sort[int(row.sort_order)] = str(row.id)
        if str(row.code).isdigit():
            section_by_sort[int(row.code)] = str(row.id)

    patient_rows = await session.execute(
        text("SELECT id, patient_no, old_software_id FROM patients")
    )
    patient_by_no: dict[str, str] = {}
    for row in patient_rows.fetchall():
        patient_by_no[str(row.patient_no)] = str(row.id)
        if row.old_software_id:
            patient_by_no[str(row.old_software_id)] = str(row.id)

    doctor_rows = await session.execute(text("SELECT id, doctor_code FROM doctors"))
    doctor_by_code = {str(row.doctor_code): str(row.id) for row in doctor_rows.fetchall()}
    doctor_by_did: dict[int, str] = {}
    for code, doc_id in doctor_by_code.items():
        m = re.fullmatch(r"D(\d+)", code, re.IGNORECASE)
        if m:
            doctor_by_did[int(m.group(1))] = doc_id

    svc_rows = await session.execute(
        text("SELECT id, code, name FROM patient_service_masters WHERE is_active = true")
    )
    service_by_code = {
        str(row.code): {"id": str(row.id), "name": str(row.name)} for row in svc_rows.fetchall()
    }

    cash = await session.execute(
        text(
            "SELECT id FROM ledgers WHERE is_cash = true AND is_active = true "
            "ORDER BY sort_order LIMIT 1"
        )
    )
    cash_ledger_id = cash.scalar()
    if not cash_ledger_id:
        cash = await session.execute(
            text("SELECT id FROM ledgers WHERE is_active = true ORDER BY sort_order LIMIT 1")
        )
        cash_ledger_id = cash.scalar()

    cat = await session.execute(
        text(
            "SELECT id FROM service_categories "
            "WHERE UPPER(code) = 'GEN' OR UPPER(name) LIKE 'GEN%%' "
            "ORDER BY sort_order LIMIT 1"
        )
    )
    gen_category_id = cat.scalar()

    return {
        "department_by_sort": department_by_sort,
        "section_by_sort": section_by_sort,
        "patient_by_no": patient_by_no,
        "doctor_by_code": doctor_by_code,
        "doctor_by_did": doctor_by_did,
        "service_by_code": service_by_code,
        "cash_ledger_id": str(cash_ledger_id) if cash_ledger_id else None,
        "gen_category_id": str(gen_category_id) if gen_category_id else None,
    }


def _error_text(exc: BaseException) -> str:
    """Readable failure text. MemoryError's message is often empty."""
    raw = str(getattr(exc, "orig", exc) or exc).strip()
    name = type(exc).__name__
    if name == "MemoryError":
        return (
            "MemoryError: not enough memory to load every patient document at once. "
            "Documents are converted one at a time."
        )
    if not raw:
        return name
    if name.lower() in raw.lower():
        return raw
    return f"{name}: {raw}"


def _normalize_row(row: dict) -> dict[str, Any]:
    return {str(key).upper(): value for key, value in row.items()}


def _fetch_rows(conn, table: str, source_filter: str | None = None) -> list[dict[str, Any]]:
    table = _safe_ident(table)
    where = _safe_where(source_filter)
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table}` WHERE {where}")
        rows = cur.fetchall() or []
    return [_normalize_row(row) for row in rows]


def _count_rows(conn, table: str, source_filter: str | None = None) -> int:
    table = _safe_ident(table)
    where = _safe_where(source_filter)
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM `{table}` WHERE {where}")
        row = cur.fetchone() or {}
        return int(row.get("c") or row.get("C") or 0)


def _iter_rows(conn, table: str, source_filter: str | None = None):
    """Yield one source row at a time so large blobs are not all held in memory."""
    from pymysql.cursors import SSDictCursor

    table = _safe_ident(table)
    where = _safe_where(source_filter)
    cursor = conn.cursor(SSDictCursor)
    try:
        cursor.execute(f"SELECT * FROM `{table}` WHERE {where}")
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            yield _normalize_row(row)
    finally:
        cursor.close()


async def _migrate_hospital(session: AsyncSession, rows: list[dict], replace: bool) -> dict:
    if not rows:
        return {"imported": 0, "message": "No hospital details rows."}
    row = rows[0]
    data = {
        "code": "MAIN",
        "name": _clip(row.get("MHD") or "Hospital", 150) or "Hospital",
        "address_line1": _clip(row.get("ADD1"), 250),
        "address_line2": _clip(row.get("HD"), 250),
        "address_line3": _clip(row.get("SHD"), 250),
        "phone": _clip(row.get("PHONE1"), 20),
        "mobile": _clip(row.get("ADDPH"), 20),
        "email": _clip(row.get("EMAIL"), 100),
        "gstin": _clip(row.get("GSTIN"), 30),
        "software_id": _clip(row.get("SFTCD"), 50),
    }
    if replace:
        await session.execute(text("DELETE FROM hospital_profile"))
    existing = await session.execute(text("SELECT id FROM hospital_profile LIMIT 1"))
    hid = existing.scalar()
    if hid:
        await session.execute(
            text(
                """
                UPDATE hospital_profile SET
                    name=:name, address_line1=:address_line1, address_line2=:address_line2,
                    address_line3=:address_line3, phone=:phone, mobile=:mobile,
                    email=:email, gstin=:gstin, software_id=:software_id, updated_at=NOW()
                WHERE id=:id
                """
            ),
            {"id": str(hid), **data},
        )
    else:
        await session.execute(
            text(
                """
                INSERT INTO hospital_profile (
                    id, code, name, address_line1, address_line2, address_line3,
                    phone, mobile, email, gstin, software_id, created_at, updated_at
                ) VALUES (
                    :id, :code, :name, :address_line1, :address_line2, :address_line3,
                    :phone, :mobile, :email, :gstin, :software_id, NOW(), NOW()
                )
                """
            ),
            {"id": str(uuid4()), **data},
        )
    return {"imported": 1, "message": f"Hospital profile → {data['name']}"}


async def _migrate_doctors(session: AsyncSession, rows: list[dict], lookups: dict, replace: bool) -> dict:
    if replace:
        # only clear if safe — doctors may be referenced; use truncate cascade carefully
        await session.execute(text("UPDATE users SET doctor_id = NULL WHERE doctor_id IS NOT NULL"))
        await session.execute(text("TRUNCATE TABLE doctors RESTART IDENTITY CASCADE"))
        lookups["doctor_by_code"].clear()
        lookups["doctor_by_did"].clear()

    imported = 0
    skipped = 0
    tick = _RowTicker(len(rows))
    for row in rows:
        did = _parse_int(row.get("DID"))
        code = _clip(f"D{did:04d}" if did else f"LEG{_parse_int(row.get('MKEY')):04d}", 20) or "D0000"
        if code in lookups["doctor_by_code"] and not replace:
            skipped += 1
            await tick(imported=imported, skipped=skipped)
            continue
        dept_sort = _parse_int(row.get("DPRTCD"), default=-1)
        status = str(row.get("STATUS") or "Y").strip().upper()
        payload = {
            "id": str(uuid4()),
            "doctor_code": code,
            "title": _clip(row.get("SLTN"), 20),
            "first_name": _clip(row.get("FRST"), 100) or "Doctor",
            "second_name": _clip(row.get("SEND"), 100),
            "third_name": _clip(row.get("THRD"), 100),
            "date_of_birth": _parse_date(row.get("DOB")),
            "sex": _parse_gender(row.get("SEX")) if row.get("SEX") else None,
            "perm_village": _clip(row.get("VILG"), 150),
            "perm_post": _clip(row.get("POST"), 150),
            "perm_taluk": _clip(row.get("TALUK"), 150),
            "perm_district": _clip(row.get("DIST"), 150),
            "perm_pincode": _clip(row.get("PIN"), 20),
            "temp_village": _clip(row.get("PVILG"), 150),
            "temp_post": _clip(row.get("PPOST"), 150),
            "temp_taluk": _clip(row.get("PTALUK"), 150),
            "temp_district": _clip(row.get("PDIST"), 150),
            "temp_pincode": _clip(row.get("PPIN"), 20),
            "remarks": _clip(row.get("REMARKS"), 5000),
            "phone": _clip(row.get("PHONE"), 20),
            "mobile": _clip(row.get("MOB1"), 20),
            "mobile2": _clip(row.get("MOB2"), 20),
            "join_date": _parse_date(row.get("DOA")),
            "qualification": _clip(row.get("QLFTION"), 255),
            "department_id": lookups["department_by_sort"].get(dept_sort),
            "register_no": _clip(row.get("REGNO"), 80),
            "release_date": _parse_date(row.get("DOR")),
            "morning_token_start": _parse_int(row.get("STKNNO")),
            "evening_token_start": _parse_int(row.get("ESTKNNO")),
            "is_pathology_doctor": False,
            "is_active": status in {"", "Y", "YES", "1"},
            "is_existing": True,
            "is_reference_doctor": _parse_int(row.get("REFDID")) > 0,
        }
        result = await session.execute(
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
                ON CONFLICT (doctor_code) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    second_name = EXCLUDED.second_name,
                    third_name = EXCLUDED.third_name,
                    mobile = EXCLUDED.mobile,
                    updated_at = NOW()
                RETURNING id
                """
            ),
            payload,
        )
        real_id = str(result.scalar() or payload["id"])
        lookups["doctor_by_code"][code] = real_id
        if did:
            lookups["doctor_by_did"][did] = real_id
        imported += 1
        await tick(imported=imported, skipped=skipped)
    return {"imported": imported, "skipped": skipped}


async def _migrate_patients(session: AsyncSession, rows: list[dict], lookups: dict, replace: bool) -> dict:
    if replace:
        await session.execute(
            text(
                "TRUNCATE TABLE patient_document_views, patient_documents, "
                "opd_bill_payments, opd_bill_lines, opd_bills, opd_tokens, "
                "ipd_bill_payments, ipd_bill_lines, ipd_bills, ipd_discharge_summaries, "
                "ipd_admissions, patients RESTART IDENTITY CASCADE"
            )
        )
        lookups["patient_by_no"].clear()

    imported = 0
    skipped = 0
    used: dict[str, int] = defaultdict(int)
    tick = _RowTicker(len(rows))
    for index, row in enumerate(rows, start=1):
        raw_pid = str(row.get("PID") or "").strip()
        base = (raw_pid or f"LEG{_parse_int(row.get('MKEY'), default=index):06d}")[:20]
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

        if patient_no in lookups["patient_by_no"] and not replace:
            skipped += 1
            await tick(imported=imported, skipped=skipped)
            continue

        status = str(row.get("STATUS") or "").strip().upper()
        age_raw = str(row.get("AGE") or "").strip()
        payload = {
            "id": str(uuid4()),
            "patient_no": patient_no,
            "hospital_section_id": lookups["section_by_sort"].get(
                _parse_int(row.get("HSPSEC"), default=-1)
            ),
            "title": _clip(row.get("SLTN"), 10),
            "first_name": _clip(row.get("FRST"), 100) or "Patient",
            "middle_name": _clip(row.get("SEND"), 100),
            "last_name": _clip(row.get("THRD"), 100),
            "date_of_birth": _parse_date(row.get("DOB")),
            "age": f"{_parse_int(row.get('AGE'))} Years" if age_raw else None,
            "gender": _clip(_parse_gender(row.get("SEX")), 10) or "U",
            "blood_group": _clip(row.get("BLDGRP"), 10),
            "contact_address1": _clip(row.get("VILG"), 200),
            "contact_address2": _clip(row.get("POST"), 200),
            "contact_address3": _clip(row.get("TALUK"), 200),
            "contact_address4": _clip(row.get("DIST"), 200),
            "contact_address5": _clip(row.get("PIN"), 20),
            "perm_address1": _clip(row.get("PVILG"), 200),
            "perm_address2": _clip(row.get("PPOST"), 200),
            "perm_address3": _clip(row.get("PTALUK"), 200),
            "perm_address4": _clip(row.get("PDIST"), 200),
            "perm_address5": _clip(row.get("PPIN"), 20),
            "old_software_id": _clip(row.get("OPID") or row.get("PID"), 50),
            "remarks": _clip(row.get("REMARKS"), 5000),
            "phone": _clip(row.get("PHONE"), 20),
            "mobile": _clip(row.get("MOB1"), 20),
            "mobile2": _clip(row.get("MOB2"), 20),
            "scheme": _clip(row.get("SCHM"), 100),
            "is_existing_patient": status in {"Y", "YES", "1"},
            "patient_type": _clip(row.get("PTYPE"), 50),
            "is_active": status not in {"N", "NO", "0"},
        }
        await session.execute(
            text(
                """
                INSERT INTO patients (
                    id, patient_no, hospital_section_id, title, first_name, middle_name, last_name,
                    date_of_birth, age, gender, blood_group,
                    contact_address1, contact_address2, contact_address3, contact_address4, contact_address5,
                    perm_address1, perm_address2, perm_address3, perm_address4, perm_address5,
                    old_software_id, remarks, phone, mobile, mobile2, scheme,
                    is_existing_patient, patient_type, is_active, created_at, updated_at
                ) VALUES (
                    :id, :patient_no, :hospital_section_id, :title, :first_name, :middle_name, :last_name,
                    :date_of_birth, :age, :gender, :blood_group,
                    :contact_address1, :contact_address2, :contact_address3, :contact_address4, :contact_address5,
                    :perm_address1, :perm_address2, :perm_address3, :perm_address4, :perm_address5,
                    :old_software_id, :remarks, :phone, :mobile, :mobile2, :scheme,
                    :is_existing_patient, :patient_type, :is_active, NOW(), NOW()
                )
                ON CONFLICT (patient_no) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    middle_name = EXCLUDED.middle_name,
                    last_name = EXCLUDED.last_name,
                    mobile = EXCLUDED.mobile,
                    old_software_id = COALESCE(EXCLUDED.old_software_id, patients.old_software_id),
                    updated_at = NOW()
                """
            ),
            payload,
        )
        lookups["patient_by_no"][patient_no] = payload["id"]
        if payload["old_software_id"]:
            lookups["patient_by_no"][payload["old_software_id"]] = payload["id"]
        imported += 1
        await tick(imported=imported, skipped=skipped)
    return {"imported": imported, "skipped": skipped}


async def _migrate_services(session: AsyncSession, rows: list[dict], lookups: dict, replace: bool) -> dict:
    if replace:
        await session.execute(
            text(
                "DELETE FROM patient_service_masters "
                "WHERE code LIKE 'PS%%' AND (category_id IS NULL OR category_id = :cat)"
            ),
            {"cat": lookups.get("gen_category_id")},
        )

    imported = 0
    skipped = 0
    tick = _RowTicker(len(rows))
    for row in rows:
        cd = _parse_int(row.get("CD"))
        code = f"PS{cd}"
        if code in lookups["service_by_code"] and not replace:
            skipped += 1
            await tick(imported=imported, skipped=skipped)
            continue
        status = str(row.get("STATUS") or "Y").strip().upper()
        rate = _parse_decimal(row.get("RATE"))
        payload = {
            "id": str(uuid4()),
            "code": code,
            "name": _clip(row.get("CNAME"), 200) or f"Service {cd}",
            "service_charge": rate,
            "rate": rate,
            "is_sharing": str(row.get("SHARING") or "N").upper() == "Y",
            "doctor_id": lookups["doctor_by_did"].get(_parse_int(row.get("DID"))) or None,
            "show_in_doctor_collection": False,
            "discount_apply": str(row.get("OTHDIS") or "N").upper() == "Y",
            "is_renewal": str(row.get("RNWL") or "N").upper() == "Y",
            "renewal_days": _parse_int(row.get("RNWLDAYS")) or None,
            "is_service_active": status in {"", "Y", "YES", "1"},
            "category_id": lookups.get("gen_category_id"),
            "is_active": True,
        }
        await session.execute(
            text(
                """
                INSERT INTO patient_service_masters (
                    id, code, name, service_charge, rate, is_sharing, doctor_id,
                    show_in_doctor_collection, discount_apply, is_renewal, renewal_days,
                    is_service_active, category_id, is_active, created_at, updated_at
                ) VALUES (
                    :id, :code, :name, :service_charge, :rate, :is_sharing, :doctor_id,
                    :show_in_doctor_collection, :discount_apply, :is_renewal, :renewal_days,
                    :is_service_active, :category_id, :is_active, NOW(), NOW()
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    rate = EXCLUDED.rate,
                    service_charge = EXCLUDED.service_charge,
                    updated_at = NOW()
                """
            ),
            payload,
        )
        lookups["service_by_code"][code] = {"id": payload["id"], "name": payload["name"]}
        imported += 1
        await tick(imported=imported, skipped=skipped)
    return {"imported": imported, "skipped": skipped}


async def _migrate_bills(session: AsyncSession, rows: list[dict], lookups: dict, replace: bool) -> dict:
    opd_rows = [r for r in rows if _parse_int(r.get("SW")) == 1]
    ipd_rows = [r for r in rows if _parse_int(r.get("SW")) == 2]
    other_rows = [r for r in rows if _parse_int(r.get("SW")) not in (1, 2)]
    # treat SW=3 (legacy discharge/billing) as IPD-like lines for reporting only

    if replace:
        await session.execute(
            text(
                "TRUNCATE TABLE opd_bill_payments, opd_bill_lines, opd_bills, opd_tokens "
                "RESTART IDENTITY CASCADE"
            )
        )

    # Group OPD by bill no + date + patient
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in opd_rows:
        key = (
            _parse_int(row.get("BILLNO")),
            str(_parse_date(row.get("TRNDT")) or ""),
            str(row.get("PID") or "").strip(),
        )
        groups[key].append(row)

    imported_bills = 0
    imported_lines = 0
    skipped = 0
    missing_patients = 0
    tick = _RowTicker(len(groups), unit="bills")

    for (billno, trndt, pid), lines in groups.items():
        patient_id = lookups["patient_by_no"].get(pid)
        if not patient_id:
            missing_patients += 1
            skipped += 1
            await tick(imported=imported_bills, skipped=skipped, imported_lines=imported_lines)
            continue
        first = lines[0]
        did = _parse_int(first.get("DID"))
        doctor_id = lookups["doctor_by_did"].get(did)
        bill_date = _parse_date(first.get("TRNDT")) or date.today()
        bill_no = f"LEG-OPD-{bill_date.strftime('%Y%m%d')}-{billno}"
        # ensure unique
        existing = await session.execute(
            text("SELECT id FROM opd_bills WHERE bill_no = :bn"), {"bn": bill_no}
        )
        if existing.scalar() and not replace:
            skipped += 1
            await tick(imported=imported_bills, skipped=skipped, imported_lines=imported_lines)
            continue

        net_total = sum(_parse_decimal(r.get("NETAMNT")) for r in lines)
        bill_id = str(uuid4())
        await session.execute(
            text(
                """
                INSERT INTO opd_bills (
                    id, bill_no, bill_date, patient_id, patient_no, doctor_id,
                    is_cash, admin_charges, scheme_discount, sanctioned_scheme_amount,
                    adjust_advance, gross_amount, net_amount, remarks, visit_category,
                    appointment_date, status, is_active, created_at, updated_at
                ) VALUES (
                    :id, :bill_no, :bill_date, :patient_id, :patient_no, :doctor_id,
                    true, :admin_charges, 0, :scnamnt, :advamnt, :gross, :net, :remarks, 'opd',
                    :appointment_date, 'saved', true, NOW(), NOW()
                )
                ON CONFLICT (bill_no) DO NOTHING
                """
            ),
            {
                "id": bill_id,
                "bill_no": bill_no,
                "bill_date": bill_date,
                "patient_id": patient_id,
                "patient_no": pid[:20],
                "doctor_id": doctor_id,
                "admin_charges": _parse_decimal(first.get("ADMINCRG")),
                "scnamnt": _parse_decimal(first.get("SCNAMNT")),
                "advamnt": _parse_decimal(first.get("ADVAMNT")),
                "gross": net_total,
                "net": net_total,
                "remarks": _clip(first.get("REMARKS"), 5000),
                "appointment_date": _parse_date(first.get("APDATE")),
            },
        )
        # confirm insert happened
        check = await session.execute(
            text("SELECT id FROM opd_bills WHERE bill_no = :bn"), {"bn": bill_no}
        )
        real_id = check.scalar()
        if not real_id:
            skipped += 1
            await tick(imported=imported_bills, skipped=skipped, imported_lines=imported_lines)
            continue
        bill_id = str(real_id)
        imported_bills += 1

        for sort_i, line in enumerate(lines):
            srcd = _parse_int(line.get("SRCD"))
            svc_code = f"PS{srcd}" if srcd else f"LEG{_parse_int(line.get('MKEY'))}"
            svc = lookups["service_by_code"].get(svc_code) or {}
            rate = _parse_decimal(line.get("RATE"))
            qty = max(_parse_int(line.get("QTY"), default=1), 1)
            amount = _parse_decimal(line.get("NETAMNT"), default=rate * qty)
            await session.execute(
                text(
                    """
                    INSERT INTO opd_bill_lines (
                        id, bill_id, service_id, service_code, service_name,
                        rate, quantity, amount, original_rate, hospital_amount,
                        doctor_amount, line_source, sort_order, is_active,
                        created_at, updated_at
                    ) VALUES (
                        :id, :bill_id, :service_id, :service_code, :service_name,
                        :rate, :quantity, :amount, :rate, :amount,
                        0, 'legacy', :sort_order, true, NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "bill_id": bill_id,
                    "service_id": svc.get("id"),
                    "service_code": svc_code[:30],
                    "service_name": (svc.get("name") or f"Service {srcd}")[:200],
                    "rate": rate,
                    "quantity": qty,
                    "amount": amount,
                    "sort_order": sort_i,
                },
            )
            imported_lines += 1
        await tick(imported=imported_bills, skipped=skipped, imported_lines=imported_lines)

    return {
        "imported": imported_bills,
        "imported_lines": imported_lines,
        "skipped": skipped,
        "missing_patients": missing_patients,
        "opd_source_rows": len(opd_rows),
        "ipd_source_rows": len(ipd_rows),
        "other_sw_rows": len(other_rows),
        "message": (
            f"OPD bills imported: {imported_bills}. "
            f"IPD (SW=2) rows detected: {len(ipd_rows)} "
            f"(IPD needs admissions — skipped for now). "
            f"Other SW rows: {len(other_rows)}."
        ),
    }


async def _migrate_cashbook(session: AsyncSession, rows: list[dict], lookups: dict, replace: bool) -> dict:
    ledger_id = lookups.get("cash_ledger_id")
    if not ledger_id:
        return {"imported": 0, "message": "No ledger found — create a cash ledger first."}

    if replace:
        await session.execute(
            text(
                "TRUNCATE TABLE cashbook_voucher_lines, cashbook_vouchers RESTART IDENTITY CASCADE"
            )
        )

    imported = 0
    skipped = 0
    tick = _RowTicker(len(rows), unit="vouchers")
    for row in rows:
        mkey = _parse_int(row.get("MKEY"))
        rvno = _parse_int(row.get("RVNO"), default=mkey)
        trndt = _parse_date(row.get("TRNDT")) or date.today()
        voucher_no = f"LEG-CSH-{trndt.strftime('%Y%m%d')}-{rvno}-{mkey}"
        existing = await session.execute(
            text("SELECT id FROM cashbook_vouchers WHERE voucher_no = :vn"),
            {"vn": voucher_no},
        )
        if existing.scalar() and not replace:
            skipped += 1
            await tick(imported=imported, skipped=skipped)
            continue

        pid = str(row.get("PID") or "").strip()
        patient_id = lookups["patient_by_no"].get(pid) if pid else None
        credit = _parse_decimal(row.get("CREDIT"))
        debit = _parse_decimal(row.get("DEBIT"))
        narration = " ".join(
            p for p in (_clip(row.get("PART1"), 250), _clip(row.get("PART2"), 250)) if p
        )
        voucher_id = str(uuid4())
        await session.execute(
            text(
                """
                INSERT INTO cashbook_vouchers (
                    id, voucher_no, voucher_date, source_type, source_id,
                    patient_id, patient_no, narration, is_active, created_at, updated_at
                ) VALUES (
                    :id, :voucher_no, :voucher_date, 'legacy_cashbook', :source_id,
                    :patient_id, :patient_no, :narration, true, NOW(), NOW()
                )
                """
            ),
            {
                "id": voucher_id,
                "voucher_no": voucher_no,
                "voucher_date": trndt,
                "source_id": voucher_id,
                "patient_id": patient_id,
                "patient_no": pid[:20] if pid else None,
                "narration": narration or None,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO cashbook_voucher_lines (
                    id, voucher_id, ledger_id, debit_amount, credit_amount,
                    sort_order, is_active, created_at, updated_at
                ) VALUES (
                    :id, :voucher_id, :ledger_id, :debit, :credit,
                    0, true, NOW(), NOW()
                )
                """
            ),
            {
                "id": str(uuid4()),
                "voucher_id": voucher_id,
                "ledger_id": ledger_id,
                "debit": debit,
                "credit": credit,
            },
        )
        imported += 1
        await tick(imported=imported, skipped=skipped)
    return {"imported": imported, "skipped": skipped}


def _sniff_blob_kind(blob: bytes) -> str:
    if blob[:3] == b"\xff\xd8\xff":
        return "jpg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if blob[:4] == b"%PDF":
        return "pdf"
    if blob[:2] == b"BM":
        return "bmp"
    if blob[:4] in (b"II*\x00", b"MM\x00*"):
        return "tif"
    if blob[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "webp"
    return "unknown"


def _require_pillow() -> None:
    """JPG/PNG/… legacy docs must be converted to PDF via Pillow."""
    try:
        import PIL  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Pillow (PIL) is not installed in the backend Python environment. "
            "Install it with: pip install pillow  — then restart the backend and re-run "
            "Patient Documents migration. Legacy image blobs cannot be converted to PDF without it."
        ) from exc


def _image_blob_to_pdf(blob: bytes) -> tuple[bytes, int]:
    """Convert an image blob (JPG/PNG/BMP/TIFF…) into a single PDF document."""
    from io import BytesIO

    from PIL import Image, ImageSequence

    with Image.open(BytesIO(blob)) as img:
        pages = [frame.convert("RGB") for frame in ImageSequence.Iterator(img)]
    if not pages:
        raise ValueError("Image has no readable pages.")
    buffer = BytesIO()
    pages[0].save(
        buffer,
        format="PDF",
        resolution=200.0,
        save_all=len(pages) > 1,
        append_images=pages[1:],
    )
    return buffer.getvalue(), len(pages)


def _pdf_page_count(blob: bytes) -> int:
    try:
        from io import BytesIO

        from pypdf import PdfReader

        return max(1, len(PdfReader(BytesIO(blob)).pages))
    except Exception:  # noqa: BLE001
        return 1


def _document_relative_path(target: Path) -> str:
    """Path stored in patient_documents.file_path (same convention as uploads)."""
    from app.services.patient_document_files import _relative_path

    return _relative_path(target)


def _purge_legacy_document_files(storage: Path) -> int:
    removed = 0
    for pattern in ("legacy_*", "*/doc_legacy_*"):
        for stale in storage.glob(pattern):
            if stale.is_file():
                try:
                    stale.unlink()
                    removed += 1
                except OSError:
                    pass
    return removed


async def _emit_document_progress(
    *,
    processed: int,
    total: int,
    imported: int,
    converted: int,
    skipped: int,
    missing: int,
    failed: int,
    detail: str,
) -> None:
    ctx = dict(_table_ctx.get() or {})
    await _emit_progress(
        {
            "type": "rows",
            "activity": "Converting patient history",
            "processed": processed,
            "total": total,
            "unit": "documents",
            "imported": imported,
            "converted_to_pdf": converted,
            "skipped": skipped,
            "missing_patients": missing,
            "failed": failed,
            "detail": detail,
            **ctx,
        }
    )


async def _migrate_documents(
    session: AsyncSession,
    conn,
    lookups: dict,
    replace: bool,
    *,
    legacy_table: str,
    source_filter: str | None = None,
) -> dict:
    settings = get_settings()
    storage: Path = Path(settings.patient_documents_storage_dir)
    storage.mkdir(parents=True, exist_ok=True)

    # Image blobs (jpg/png/…) need Pillow; fail once up front instead of per-row.
    _require_pillow()

    purged_files = 0
    if replace:
        await session.execute(
            text("TRUNCATE TABLE patient_document_views, patient_documents RESTART IDENTITY CASCADE")
        )
        purged_files = _purge_legacy_document_files(storage)

    total = _count_rows(conn, legacy_table, source_filter)
    ctx = dict(_table_ctx.get() or {})
    await _emit_progress(
        {
            "type": "table",
            "phase": "writing",
            "source_rows": total,
            "message": f"Converting patient history — {total:,} document(s)",
            **ctx,
        }
    )

    imported = 0
    converted = 0
    skipped = 0
    missing = 0
    failed = 0
    kinds: dict[str, int] = defaultdict(int)
    errors: list[str] = []

    counts = {
        "processed": 0,
        "total": total,
        "imported": imported,
        "converted": converted,
        "skipped": skipped,
        "missing": missing,
        "failed": failed,
    }

    async def progress(detail: str) -> None:
        counts["imported"] = imported
        counts["converted"] = converted
        counts["skipped"] = skipped
        counts["missing"] = missing
        counts["failed"] = failed
        await _emit_document_progress(detail=detail, **counts)

    # One document at a time. Loading every DOC blob first runs out of memory.
    for index, row in enumerate(_iter_rows(conn, legacy_table, source_filter), start=1):
        counts["processed"] = index
        pid = str(row.get("PID") or "").strip()
        patient_label = pid or "unknown patient"
        patient_id = lookups["patient_by_no"].get(pid)
        if not patient_id:
            missing += 1
            await progress(f"patient {patient_label} · skipped, patient not in master")
            continue
        blob = row.get("DOC")
        row["DOC"] = None
        if blob is None:
            skipped += 1
            await progress(f"patient {patient_label} · skipped, empty document")
            continue
        if isinstance(blob, memoryview):
            blob = blob.tobytes()
        elif isinstance(blob, str):
            blob = blob.encode("latin-1", errors="replace")
        elif not isinstance(blob, (bytes, bytearray)):
            skipped += 1
            await progress(f"patient {patient_label} · skipped, unreadable document")
            continue
        blob = bytes(blob)

        # MKEY is only the legacy row id from the same rcd record (for filenames /
        # error labels). It is not looked up in another table.
        mkey = _parse_int(row.get("MKEY"))
        doc_date = _parse_date(row.get("DATE1") or row.get("TRNDT")) or date.today()
        kind = _sniff_blob_kind(blob)
        kinds[kind] += 1
        await progress(f"patient {patient_label} · {kind} → PDF")

        if kind == "pdf":
            pdf_bytes = blob
            page_count = _pdf_page_count(blob)
        else:
            try:
                pdf_bytes, page_count = _image_blob_to_pdf(blob)
                converted += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                if len(errors) < 5:
                    errors.append(f"PID {pid} / MKEY {mkey} ({kind}): {exc}")
                await progress(f"patient {patient_label} · {kind} conversion failed")
                continue

        folder = storage / str(patient_id)
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"doc_legacy_{pid}_{mkey}_{uuid4().hex[:8]}.pdf"
        file_size = len(pdf_bytes)
        dest.write_bytes(pdf_bytes)
        pdf_bytes = b""

        await session.execute(
            text(
                """
                INSERT INTO patient_documents (
                    id, patient_id, file_path, original_name, document_type,
                    page_count, file_size_bytes, document_date, remarks,
                    is_active, created_at, updated_at
                ) VALUES (
                    :id, :patient_id, :file_path, :original_name, 'patient_document',
                    :page_count, :file_size, :document_date, :remarks,
                    true, NOW(), NOW()
                )
                """
            ),
            {
                "id": str(uuid4()),
                "patient_id": patient_id,
                "file_path": _document_relative_path(dest),
                "original_name": f"legacy_{pid}_{mkey}.pdf",
                "page_count": page_count,
                "file_size": file_size,
                "document_date": doc_date,
                "remarks": _clip(row.get("OLDID"), 500),
            },
        )
        imported += 1
        await progress(f"patient {patient_label} · saved PDF ({page_count} page(s))")

    message = (
        f"imported={imported}, converted to PDF={converted}, "
        f"source types: {', '.join(f'{k}:{v}' for k, v in sorted(kinds.items())) or 'none'}"
    )
    if failed:
        message += f"; conversion failures={failed} ({'; '.join(errors)})"
    if purged_files:
        message += f"; removed {purged_files} old legacy file(s)"
    return {
        "imported": imported,
        "converted_to_pdf": converted,
        "skipped": skipped,
        "missing_patients": missing,
        "failed": failed,
        "source_rows": total,
        "source_kinds": dict(kinds),
        "message": message,
    }


async def _migrate_pathology(
    session: AsyncSession,
    conn,
    replace: bool,
    *,
    legacy_table: str = "pservice",
    source_filter: str | None = None,
) -> dict:
    """Lightweight pathology import from live MySQL pservice (+ optional pprmtr).

    Full panel/range parsing lives in scripts/import_legacy_pathology.py;
    here we upsert LAB services from pservice so the UI option still works.
    """
    try:
        rows = _fetch_rows(conn, legacy_table, source_filter)
    except Exception as exc:  # noqa: BLE001
        return {"imported": 0, "source_rows": 0, "message": f"{legacy_table} not available: {exc}"}

    # ensure LAB category
    cat = await session.execute(
        text(
            "SELECT id FROM service_categories "
            "WHERE UPPER(code) = 'LAB' OR UPPER(name) LIKE 'LAB%%' LIMIT 1"
        )
    )
    lab_cat = cat.scalar()
    if not lab_cat:
        lab_cat = str(uuid4())
        await session.execute(
            text(
                """
                INSERT INTO service_categories (id, code, name, sort_order, is_active, created_at, updated_at)
                VALUES (:id, 'LAB', 'Laboratory', 90, true, NOW(), NOW())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"id": lab_cat},
        )
        cat2 = await session.execute(
            text("SELECT id FROM service_categories WHERE UPPER(code) = 'LAB' LIMIT 1")
        )
        lab_cat = cat2.scalar() or lab_cat

    ctx = dict(_table_ctx.get() or {})
    await _emit_progress(
        {
            "type": "table",
            "phase": "writing",
            "source_rows": len(rows),
            **ctx,
        }
    )

    imported = 0
    tick = _RowTicker(len(rows))
    for row in rows:
        cd = _parse_int(row.get("CD"))
        code = f"P{cd}"
        rate = _parse_decimal(row.get("RATE"))
        status = str(row.get("STATUS") or "Y").strip().upper()
        await session.execute(
            text(
                """
                INSERT INTO patient_service_masters (
                    id, code, name, service_charge, rate, is_sharing,
                    show_in_doctor_collection, discount_apply, is_renewal,
                    is_service_active, category_id, is_active, created_at, updated_at
                ) VALUES (
                    :id, :code, :name, :rate, :rate, false,
                    false, false, false,
                    :active, :category_id, true, NOW(), NOW()
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    rate = EXCLUDED.rate,
                    service_charge = EXCLUDED.service_charge,
                    updated_at = NOW()
                """
            ),
            {
                "id": str(uuid4()),
                "code": code,
                "name": _clip(row.get("CNAME"), 200) or f"Lab {cd}",
                "rate": rate,
                "active": status in {"", "Y", "YES", "1"},
                "category_id": str(lab_cat),
            },
        )
        imported += 1
        await tick(imported=imported)
    return {
        "imported": imported,
        "source_rows": len(rows),
        "message": (
            f"Upserted {imported} lab service(s) from pservice. "
            "For full units/ranges/panels use scripts/import_legacy_pathology.py."
        ),
        "replace_requested": replace,
    }


async def run_migration(
    *,
    mysql_conn_str: str,
    postgres_url: str | None,
    selected_keys: list[str],
    mapping_overrides: list[dict[str, Any]] | None,
    replace_existing: bool,
    dry_run: bool,
    app_session: AsyncSession | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run selected migrations. Uses app_session when postgres_url matches app DB."""
    cb_token = _progress_cb.set(progress)
    try:
        return await _run_migration(
            mysql_conn_str=mysql_conn_str,
            postgres_url=postgres_url,
            selected_keys=selected_keys,
            mapping_overrides=mapping_overrides,
            replace_existing=replace_existing,
            dry_run=dry_run,
            app_session=app_session,
        )
    finally:
        _progress_cb.reset(cb_token)


async def _run_migration(
    *,
    mysql_conn_str: str,
    postgres_url: str | None,
    selected_keys: list[str],
    mapping_overrides: list[dict[str, Any]] | None,
    replace_existing: bool,
    dry_run: bool,
    app_session: AsyncSession | None = None,
) -> dict[str, Any]:
    if not selected_keys:
        raise ValueError("Select at least one table mapping to migrate.")

    # Build mapping catalog with overrides (editable table names / WHERE filters)
    catalog = {m["key"]: dict(m) for m in DEFAULT_MAPPINGS}
    for ov in mapping_overrides or []:
        key = ov.get("key")
        if key not in catalog:
            continue
        if ov.get("legacy_table"):
            catalog[key]["legacy_table"] = str(ov["legacy_table"]).strip()
        if ov.get("source_filter") is not None:
            catalog[key]["source_filter"] = str(ov["source_filter"]).strip()

    ordered = [k for k in MIGRATE_ORDER if k in selected_keys]
    await _emit_progress(
        {
            "type": "start",
            "dry_run": dry_run,
            "table_total": len(ordered),
            "tables": [
                {
                    "key": key,
                    "label": catalog[key]["label"],
                    "legacy_table": catalog[key]["legacy_table"],
                }
                for key in ordered
            ],
            "message": "Dry run started." if dry_run else "Migration started.",
        }
    )

    settings = get_settings()
    use_external = False
    external_engine = None
    session: AsyncSession

    if postgres_url and display_postgres_url(postgres_url) != display_postgres_url(settings.database_url):
        use_external = True
        info = test_postgres_connection(postgres_url)
        external_engine = create_async_engine(info["normalized_url"], echo=False)
        factory = async_sessionmaker(external_engine, class_=AsyncSession, expire_on_commit=False)
        session = factory()
    else:
        if app_session is None:
            raise ValueError("Application database session is required.")
        session = app_session

    await _emit_progress(
        {"type": "status", "phase": "connecting", "message": "Connecting to MySQL…"}
    )
    mysql = _connect_mysql(mysql_conn_str)
    results: dict[str, Any] = {}
    try:
        await _emit_progress(
            {
                "type": "status",
                "phase": "lookups",
                "message": "Loading existing PostgreSQL data…",
            }
        )
        lookups = await load_lookups(session)
        for index, key in enumerate(ordered, start=1):
            meta = catalog[key]
            table = meta["legacy_table"]
            where = meta.get("source_filter")
            table_info = {
                "key": key,
                "label": meta["label"],
                "legacy_table": table,
                "table_index": index,
                "table_total": len(ordered),
            }
            ctx_token = _table_ctx.set(table_info)
            try:
                reading_message = (
                    "Counting patient history documents in MySQL…"
                    if key == "documents"
                    else None
                )
                await _emit_progress(
                    {
                        "type": "table",
                        "phase": "reading",
                        "message": reading_message,
                        **table_info,
                    }
                )
                try:
                    if key == "pathology":
                        result = await _migrate_pathology(
                            session,
                            mysql,
                            replace_existing,
                            legacy_table=table,
                            source_filter=where,
                        )
                    elif key == "documents":
                        if dry_run:
                            source_rows = _count_rows(mysql, table, where)
                            result = {
                                "imported": 0,
                                "converted_to_pdf": 0,
                                "source_rows": source_rows,
                                "dry_run": True,
                                "message": (
                                    f"{source_rows:,} patient history document(s) "
                                    "would be converted to PDF."
                                ),
                            }
                            await _emit_progress(
                                {
                                    "type": "rows",
                                    "activity": "Converting patient history",
                                    "processed": source_rows,
                                    "total": source_rows,
                                    "unit": "documents",
                                    "imported": 0,
                                    "converted_to_pdf": 0,
                                    "source_rows": source_rows,
                                    "detail": "dry run — no files written",
                                    **table_info,
                                }
                            )
                        else:
                            result = await _migrate_documents(
                                session,
                                mysql,
                                lookups,
                                replace_existing,
                                legacy_table=table,
                                source_filter=where,
                            )
                    else:
                        rows = _fetch_rows(mysql, table, where)
                        await _emit_progress(
                            {
                                "type": "table",
                                "phase": "writing",
                                "source_rows": len(rows),
                                **table_info,
                            }
                        )
                        if dry_run:
                            result = {
                                "imported": 0,
                                "source_rows": len(rows),
                                "dry_run": True,
                            }
                            await _emit_progress(
                                {
                                    "type": "rows",
                                    "processed": len(rows),
                                    "total": len(rows),
                                    "unit": "rows",
                                    "imported": 0,
                                    "source_rows": len(rows),
                                    **table_info,
                                }
                            )
                        elif key == "hospital":
                            result = await _migrate_hospital(session, rows, replace_existing)
                        elif key == "doctors":
                            result = await _migrate_doctors(session, rows, lookups, replace_existing)
                        elif key == "patients":
                            result = await _migrate_patients(session, rows, lookups, replace_existing)
                        elif key == "services":
                            result = await _migrate_services(session, rows, lookups, replace_existing)
                        elif key == "opd_ipd_bills":
                            result = await _migrate_bills(session, rows, lookups, replace_existing)
                        elif key == "cashbook":
                            result = await _migrate_cashbook(session, rows, lookups, replace_existing)
                        else:
                            result = {"imported": 0, "message": f"Unknown mapping key: {key}"}
                        if "source_rows" not in result:
                            result["source_rows"] = len(rows)
                    results[key] = {
                        "ok": True,
                        "label": meta["label"],
                        "legacy_table": table,
                        **result,
                    }
                    await _emit_progress(
                        {
                            "type": "table_done",
                            "ok": True,
                            **table_info,
                            **result,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    _logger.exception("Legacy migration failed for %s (table %s)", key, table)
                    failed = {
                        "ok": False,
                        "label": meta["label"],
                        "legacy_table": table,
                        "error": _error_text(exc),
                        "error_type": type(exc).__name__,
                        "traceback": traceback.format_exc(limit=6),
                    }
                    results[key] = failed
                    await _emit_progress({"type": "table_done", **table_info, **failed})
            finally:
                _table_ctx.reset(ctx_token)

        await _emit_progress(
            {
                "type": "status",
                "phase": "saving",
                "message": (
                    "Dry run finished reading. Nothing will be saved."
                    if dry_run
                    else "Saving migrated rows to PostgreSQL…"
                ),
            }
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        mysql.close()
        if use_external:
            await session.close()
            if external_engine is not None:
                await external_engine.dispose()

    ok_count = sum(1 for r in results.values() if r.get("ok"))
    all_ok = ok_count == len(results) and len(results) > 0
    if dry_run and all_ok:
        message = "Dry run completed. No data was written."
    elif all_ok:
        message = "Migration completed."
    elif dry_run:
        message = f"Dry run finished with errors: {ok_count}/{len(results)} table(s) succeeded."
    else:
        message = f"Migration finished with errors: {ok_count}/{len(results)} table(s) succeeded."
    return {
        "ok": all_ok,
        "dry_run": dry_run,
        "results": results,
        "message": message,
    }
