"""Per-PC print settings stored in print.ini (system level).

Printer names differ on each workstation. Report codes are synced from the
database (Print Master API) so new print types appear automatically.
"""
from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path

_SECTION_PRINTERS = "printers"
_SECTION_META = "meta"


class _IniParser(configparser.ConfigParser):
    """Preserve report code casing (OPD_BILL, not opd_bill)."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _new_parser() -> _IniParser:
    return _IniParser()


def _resolve_hms_root() -> Path | None:
    explicit = os.environ.get("HMS_ROOT", "").strip()
    if explicit:
        return Path(explicit)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def print_ini_path() -> Path:
    explicit = os.environ.get("HMS_PRINT_INI", "").strip()
    if explicit:
        return Path(explicit)
    root = _resolve_hms_root()
    if root is not None:
        return root / "config" / "print.ini"
    local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HospitalManagement"
    return local / "print.ini"


def _default_ini_text() -> str:
    return "\n".join(
        [
            "; Hospital Management System — print settings for THIS PC only.",
            "; Printer names must match Windows Settings → Printers exactly.",
            "; Leave a printer blank to use the Windows default printer.",
            "; Report keys are added automatically from Print Master.",
            "",
            f"[{_SECTION_PRINTERS}]",
            "",
            f"[{_SECTION_META}]",
            "version = 1",
            "",
        ]
    )


def _write_ini(path: Path, parser: _IniParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def _read_or_create_parser(path: Path) -> _IniParser:
    if not path.is_file():
        path.write_text(_default_ini_text(), encoding="utf-8")
    parser = _new_parser()
    parser.read(path, encoding="utf-8")
    if _SECTION_PRINTERS not in parser:
        parser[_SECTION_PRINTERS] = {}
    if _SECTION_META not in parser:
        parser[_SECTION_META] = {"version": "1"}
    return parser


def sync_print_ini_codes(report_codes: list[str]) -> Path:
    """Ensure print.ini has an entry for every report code from the database."""
    path = print_ini_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    parser = _read_or_create_parser(path)
    section = parser[_SECTION_PRINTERS]
    existing_upper = {key.upper() for key in section}
    changed = False
    for raw in report_codes:
        code = (raw or "").strip().upper()
        if not code or code in existing_upper:
            continue
        section[code] = ""
        existing_upper.add(code)
        changed = True
    if changed:
        _write_ini(path, parser)
    return path


def ensure_print_ini(report_codes: list[str] | None = None) -> Path:
    path = print_ini_path()
    _read_or_create_parser(path)
    if report_codes:
        sync_print_ini_codes(report_codes)
    return path


def _load_parser() -> _IniParser:
    path = ensure_print_ini()
    return _read_or_create_parser(path)


def _section_value(section: configparser.SectionProxy, code: str) -> str:
    if code in section:
        return str(section[code])
    upper = code.upper()
    for key, value in section.items():
        if key.upper() == upper:
            return str(value)
    return ""


def get_report_printer(report_code: str) -> str | None:
    code = report_code.strip().upper()
    parser = _load_parser()
    if _SECTION_PRINTERS not in parser:
        return None
    value = _section_value(parser[_SECTION_PRINTERS], code).strip()
    return value or None


def set_report_printer(report_code: str, printer_name: str | None) -> Path:
    code = report_code.strip().upper()
    path = print_ini_path()
    parser = _read_or_create_parser(path)
    section = parser[_SECTION_PRINTERS]
    target_key = code
    for key in list(section):
        if key.upper() == code:
            target_key = key
            break
    if target_key not in section and code not in section:
        section[code] = ""
        target_key = code
    section[target_key] = (printer_name or "").strip()
    _write_ini(path, parser)
    return path


def list_report_printers(known_codes: list[str] | None = None) -> dict[str, str | None]:
    parser = _load_parser()
    section = parser[_SECTION_PRINTERS] if _SECTION_PRINTERS in parser else {}
    result: dict[str, str | None] = {}
    codes = list(known_codes or [])
    for key in section:
        upper = key.upper()
        if upper not in {c.upper() for c in codes}:
            codes.append(upper)
    for code in codes:
        upper = code.upper()
        value = _section_value(section, upper).strip()
        result[upper] = value or None
    for key, value in section.items():
        upper = key.upper()
        if upper not in result:
            result[upper] = str(value).strip() or None
    return result


def migrate_db_printer(report_code: str, db_printer: str | None) -> None:
    if not db_printer:
        return
    if get_report_printer(report_code):
        return
    set_report_printer(report_code, db_printer)
