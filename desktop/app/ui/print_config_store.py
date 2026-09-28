from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.print_local_config import (
    get_report_printer,
    migrate_db_printer,
    sync_print_ini_codes,
)

if TYPE_CHECKING:
    from app.api_client.client import ApiClient


@dataclass(frozen=True)
class ResolvedPrintSettings:
    printer_name: str | None = None
    paper_size: str = "A4"
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    orientation: str = "portrait"
    print_mode: str = "preview"
    margin_top_mm: float = 8.0
    margin_right_mm: float = 5.0
    margin_bottom_mm: float = 10.0
    margin_left_mm: float = 5.0
    copies: int = 1


PAPER_SIZE_OPTIONS: list[tuple[str, str]] = [
    ("A4", "A4 (Standard)"),
    ("A5", "A5 (Half A4)"),
    ("A6", "A6 (Quarter A4 area)"),
    ("LETTER", "Letter"),
    ("LEGAL", "Legal"),
    ("CUSTOM", "Custom size (mm)"),
]

PRINT_MODE_OPTIONS: list[tuple[str, str]] = [
    ("preview", "Show preview before print"),
    ("direct", "Print directly (no preview)"),
]

ORIENTATION_OPTIONS: list[tuple[str, str]] = [
    ("portrait", "Portrait"),
    ("landscape", "Landscape"),
]

_cache: dict[str, ResolvedPrintSettings] = {}
_cache_loaded = False


def invalidate_print_config_cache() -> None:
    global _cache_loaded
    _cache.clear()
    _cache_loaded = False


def _from_row(row: dict) -> ResolvedPrintSettings:
    code = (row.get("code") or "").upper()
    db_printer = (row.get("printer_name") or "").strip() or None
    if db_printer:
        migrate_db_printer(code, db_printer)
    printer = get_report_printer(code) if code else None
    return ResolvedPrintSettings(
        printer_name=printer,
        paper_size=(row.get("paper_size") or "A4").upper(),
        custom_width_mm=row.get("custom_width_mm"),
        custom_height_mm=row.get("custom_height_mm"),
        orientation=(row.get("orientation") or "portrait").lower(),
        print_mode=(row.get("print_mode") or "preview").lower(),
        margin_top_mm=float(row.get("margin_top_mm") or 8),
        margin_right_mm=float(row.get("margin_right_mm") or 5),
        margin_bottom_mm=float(row.get("margin_bottom_mm") or 10),
        margin_left_mm=float(row.get("margin_left_mm") or 5),
        copies=int(row.get("copies") or 1),
    )


def load_print_configs(api: ApiClient, rows: list[dict] | None = None) -> dict[str, ResolvedPrintSettings]:
    global _cache_loaded
    if rows is None:
        rows = api.list_print_configs()
    codes = [(row.get("code") or "").upper() for row in rows if row.get("code")]
    sync_print_ini_codes(codes)
    _cache.clear()
    for row in rows:
        code = (row.get("code") or "").upper()
        if code:
            _cache[code] = _from_row(row)
    _cache_loaded = True
    return dict(_cache)


def get_print_settings(api: ApiClient | None, report_code: str | None) -> ResolvedPrintSettings | None:
    if not report_code:
        return None
    code = report_code.upper()
    if code in _cache:
        settings = _cache[code]
        printer = get_report_printer(code)
        if settings.printer_name != printer:
            return ResolvedPrintSettings(
                printer_name=printer,
                paper_size=settings.paper_size,
                custom_width_mm=settings.custom_width_mm,
                custom_height_mm=settings.custom_height_mm,
                orientation=settings.orientation,
                print_mode=settings.print_mode,
                margin_top_mm=settings.margin_top_mm,
                margin_right_mm=settings.margin_right_mm,
                margin_bottom_mm=settings.margin_bottom_mm,
                margin_left_mm=settings.margin_left_mm,
                copies=settings.copies,
            )
        return settings
    if api is None:
        return None
    if not _cache_loaded:
        try:
            load_print_configs(api)
        except Exception:
            return None
    return _cache.get(code)
