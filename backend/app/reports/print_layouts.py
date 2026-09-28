"""Custom bill layouts stored on PrintConfig.layout_options.

Same idea as GenERP print templates: each document (OPD bill, IPD bill, …)
has ordered bands. Staff print the saved layout. Until a layout is saved
from the designer, the existing fixed HTML template is used.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

LAYOUT_VERSION = 1
KIND_BILL = "bill"

STANDARD_PAGES: dict[str, tuple[str, float, float]] = {
    "A4": ("A4", 210.0, 297.0),
    "A5": ("A5", 148.0, 210.0),
    "A6": ("A6", 105.0, 148.0),
    "LETTER": ("Letter", 215.9, 279.4),
    "LEGAL": ("Legal", 215.9, 355.6),
}

DOCUMENT_NAMES: dict[str, str] = {
    "OPD_BILL": "OPD Bill",
    "IPD_BILL": "IPD Bill",
    "PATHOLOGY_BILL": "Pathology Bill",
    "PHARMACY_SALE_BILL": "Pharmacy Sale Bill",
    "ADVANCE_RECEIPT": "Advance Receipt",
}

BANDS = ("header", "meta", "columns", "totals", "footer")

# id, caption, band
BILL_CATALOG: list[dict[str, Any]] = [
    {"id": "hospital_name", "label": "Hospital name", "band": "header"},
    {"id": "hospital_address", "label": "Address", "band": "header"},
    {"id": "hospital_phone", "label": "Phone", "band": "header"},
    {"id": "hospital_email", "label": "Email", "band": "header"},
    {"id": "hospital_gstin", "label": "GSTIN", "band": "header"},
    {"id": "hospital_website", "label": "Website", "band": "header"},
    {"id": "bill_title", "label": "Bill title", "band": "header"},
    {"id": "patient_no", "label": "Patient ID", "band": "meta"},
    {"id": "patient_name", "label": "Patient name", "band": "meta"},
    {"id": "patient_age", "label": "Age", "band": "meta"},
    {"id": "patient_gender", "label": "Sex", "band": "meta"},
    {"id": "doctor_name", "label": "Doctor", "band": "meta"},
    {"id": "referring_doctor", "label": "Referring doctor", "band": "meta"},
    {"id": "department_name", "label": "Department", "band": "meta"},
    {"id": "bill_no", "label": "Bill no", "band": "meta"},
    {"id": "bill_date", "label": "Date", "band": "meta"},
    {"id": "voucher_no", "label": "Receipt no", "band": "meta"},
    {"id": "voucher_date", "label": "Receipt date", "band": "meta"},
    {"id": "admission_no", "label": "Admission no", "band": "meta"},
    {"id": "ward_bed", "label": "Ward / bed", "band": "meta"},
    {"id": "stay_days", "label": "Stay days", "band": "meta"},
    {"id": "admission_date", "label": "Admit date", "band": "meta"},
    {"id": "discharge_date", "label": "Discharge date", "band": "meta"},
    {"id": "scheme", "label": "Scheme", "band": "meta"},
    {"id": "cash_credit", "label": "Cash / credit", "band": "meta"},
    {"id": "token_number", "label": "Token", "band": "meta"},
    {"id": "sample_no", "label": "Sample no", "band": "meta"},
    {"id": "visit_category", "label": "Visit type", "band": "meta"},
    {"id": "sr", "label": "Sl.No", "band": "columns", "align": "center", "width": 8},
    {"id": "code", "label": "Code", "band": "columns", "align": "left", "width": 12},
    {"id": "name", "label": "Service", "band": "columns", "align": "left", "width": 46},
    {"id": "category", "label": "Category", "band": "columns", "align": "left", "width": 16},
    {"id": "rate", "label": "Rate", "band": "columns", "align": "right", "width": 12},
    {"id": "qty", "label": "Qty", "band": "columns", "align": "right", "width": 10},
    {"id": "amount", "label": "Amount", "band": "columns", "align": "right", "width": 12},
    {"id": "gross_amount", "label": "Gross", "band": "totals"},
    {"id": "admin_charges", "label": "Admin charges", "band": "totals"},
    {"id": "scheme_discount", "label": "Discount", "band": "totals"},
    {"id": "adjust_advance", "label": "Advance adjusted", "band": "totals"},
    {"id": "net_amount", "label": "Net amount", "band": "totals"},
    {"id": "amount", "label": "Amount", "band": "totals"},
    {"id": "balance_after", "label": "Balance after", "band": "totals"},
    {"id": "payment_mode", "label": "Payment", "band": "footer"},
    {"id": "remarks", "label": "Remarks", "band": "footer"},
    {"id": "computer_note", "label": "Computer note", "band": "footer"},
    {"id": "signature", "label": "Signature", "band": "footer"},
    {"id": "thanks", "label": "Thank you line", "band": "footer"},
]

# Totals "amount" and columns don't share ids across bands — catalog ids must be unique
# per band. The totals amount uses id "receipt_amount" to avoid clashing with column "amount".
for _row in BILL_CATALOG:
    if _row["id"] == "amount" and _row["band"] == "totals":
        _row["id"] = "receipt_amount"

DEFAULT_COMPUTER_NOTE = "Computer generated bill — signature not required."
DEFAULT_SIGNATURE = "Receiver's Signature"
DEFAULT_THANKS = "Thank you"

_TEXT_DEFAULTS = {
    "computer_note": DEFAULT_COMPUTER_NOTE,
    "signature": DEFAULT_SIGNATURE,
    "thanks": DEFAULT_THANKS,
}

# Visible field ids per document. Anything else stays in the catalog but hidden.
_VISIBLE: dict[str, dict[str, list[str]]] = {
    "OPD_BILL": {
        "header": ["hospital_name", "hospital_address", "hospital_phone", "bill_title"],
        "meta": ["patient_no", "department_name", "bill_date", "patient_name", "doctor_name", "bill_no"],
        "columns": ["sr", "name", "rate", "qty", "amount"],
        "totals": ["admin_charges", "scheme_discount", "adjust_advance", "net_amount"],
        "footer": ["token_number", "payment_mode", "remarks", "computer_note", "signature"],
    },
    "IPD_BILL": {
        "header": ["hospital_name", "hospital_address", "hospital_phone", "bill_title"],
        "meta": [
            "patient_no", "department_name", "bill_date",
            "patient_name", "doctor_name", "bill_no",
            "admission_no", "ward_bed", "stay_days",
            "admission_date", "discharge_date",
        ],
        "columns": ["sr", "name", "rate", "qty", "amount"],
        "totals": ["admin_charges", "scheme_discount", "adjust_advance", "net_amount"],
        "footer": ["payment_mode", "remarks", "computer_note", "signature"],
    },
    "PATHOLOGY_BILL": {
        "header": ["hospital_name", "hospital_address", "hospital_phone", "bill_title"],
        "meta": [
            "patient_no", "patient_name", "patient_age", "patient_gender",
            "doctor_name", "referring_doctor", "bill_no", "bill_date", "sample_no",
        ],
        "columns": ["sr", "name", "rate", "qty", "amount"],
        "totals": ["admin_charges", "scheme_discount", "net_amount"],
        "footer": ["payment_mode", "remarks", "computer_note", "signature"],
    },
    "PHARMACY_SALE_BILL": {
        "header": ["hospital_name", "hospital_address", "hospital_phone", "bill_title"],
        "meta": ["patient_no", "patient_name", "doctor_name", "bill_no", "bill_date"],
        "columns": ["sr", "name", "category", "rate", "qty", "amount"],
        "totals": ["scheme_discount", "net_amount"],
        "footer": ["payment_mode", "remarks", "computer_note", "signature"],
    },
    "ADVANCE_RECEIPT": {
        "header": ["hospital_name", "hospital_address", "hospital_phone", "bill_title"],
        "meta": ["patient_no", "patient_name", "voucher_no", "voucher_date"],
        "columns": [],
        "totals": ["receipt_amount", "balance_after"],
        "footer": ["payment_mode", "remarks", "computer_note", "signature"],
    },
}

# token_number is meta in catalog but OPD footer list referenced it — keep it in meta.
_VISIBLE["OPD_BILL"]["meta"] = [
    "patient_no", "department_name", "bill_date",
    "patient_name", "doctor_name", "bill_no", "token_number",
]
_VISIBLE["OPD_BILL"]["footer"] = ["payment_mode", "remarks", "computer_note", "signature"]


def catalog_payload() -> dict[str, Any]:
    return {
        "version": LAYOUT_VERSION,
        "documents": [{"code": code, "name": name, "kind": KIND_BILL} for code, name in DOCUMENT_NAMES.items()],
        "formats": [{"code": code, "name": label} for code, (label, _w, _h) in STANDARD_PAGES.items()],
        "bands": [{"id": band, "label": band.title()} for band in BANDS],
        "fields": deepcopy(BILL_CATALOG),
    }


def _catalog_index() -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["band"], row["id"]): row for row in BILL_CATALOG}


def _optional_mm(raw: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if raw.get(key) is None or raw.get(key) == "":
            continue
        try:
            value = float(raw[key])
        except (TypeError, ValueError):
            continue
        return round(max(0.0, min(1000.0, value)), 1)
    return None


def _clean_field(raw: dict[str, Any], catalog_row: dict[str, Any] | None) -> dict[str, Any] | None:
    fid = str(raw.get("id") or "").strip()
    if not fid:
        return None
    band = str(raw.get("band") or (catalog_row or {}).get("band") or "")
    if catalog_row is None and not fid.startswith("static_"):
        return None
    align = str(raw.get("align") or (catalog_row or {}).get("align") or "left")
    if align not in {"left", "center", "right"}:
        align = "left"
    item: dict[str, Any] = {
        "id": fid,
        "band": band,
        "visible": bool(raw.get("visible", True)),
        "label": str(raw.get("label") or (catalog_row or {}).get("label") or fid)[:80],
        "align": align,
    }
    if band == "columns":
        try:
            width = float(raw.get("width") if raw.get("width") is not None else (catalog_row or {}).get("width") or 10)
        except (TypeError, ValueError):
            width = 10
        item["width"] = max(4.0, min(400.0, width))
    for dest, keys in (
        ("x_mm", ("x_mm", "xMm")),
        ("y_mm", ("y_mm", "yMm")),
        ("width_mm", ("width_mm", "widthMm")),
        ("height_mm", ("height_mm", "heightMm")),
    ):
        placed = _optional_mm(raw, *keys)
        if placed is not None:
            item[dest] = placed
    font = raw.get("font_size_pt") if raw.get("font_size_pt") is not None else raw.get("fontSizePt")
    if font is not None:
        try:
            item["font_size_pt"] = max(6.0, min(36.0, round(float(font), 1)))
        except (TypeError, ValueError):
            pass
    if fid.startswith("static_") or fid in _TEXT_DEFAULTS or fid == "bill_title":
        text = raw.get("text")
        if text is None and fid in _TEXT_DEFAULTS:
            text = _TEXT_DEFAULTS[fid]
        if text is not None:
            item["text"] = str(text)[:500]
    return item


def _default_band(code: str, band: str) -> list[dict[str, Any]]:
    visible = set((_VISIBLE.get(code) or _VISIBLE["OPD_BILL"]).get(band) or [])
    fields: list[dict[str, Any]] = []
    index = _catalog_index()
    ordered_ids = list((_VISIBLE.get(code) or {}).get(band) or [])
    seen: set[str] = set()
    for fid in ordered_ids:
        row = index.get((band, fid))
        if not row:
            continue
        seen.add(fid)
        fields.append(
            _clean_field(
                {
                    "id": fid,
                    "band": band,
                    "visible": True,
                    "label": row["label"],
                    "align": row.get("align") or ("center" if band == "header" else "left"),
                    "width": row.get("width"),
                    "text": _TEXT_DEFAULTS.get(fid),
                },
                row,
            )
        )
    for row in BILL_CATALOG:
        if row["band"] != band or row["id"] in seen:
            continue
        if row["id"] in visible:
            continue
        fields.append(
            _clean_field(
                {
                    "id": row["id"],
                    "band": band,
                    "visible": False,
                    "label": row["label"],
                    "align": row.get("align") or "left",
                    "width": row.get("width"),
                    "text": _TEXT_DEFAULTS.get(row["id"]),
                },
                row,
            )
        )
    return [field for field in fields if field]


def _merge_band(code: str, band: str, saved: Any) -> list[dict[str, Any]]:
    index = _catalog_index()
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(saved, list):
        for raw in saved:
            if not isinstance(raw, dict):
                continue
            fid = str(raw.get("id") or "")
            catalog_row = index.get((band, fid))
            if fid.startswith("static_"):
                raw = {**raw, "band": band}
                cleaned = _clean_field(raw, {"id": fid, "label": raw.get("label") or "Text", "band": band})
            else:
                cleaned = _clean_field({**raw, "band": band}, catalog_row)
            if not cleaned or cleaned["id"] in seen:
                continue
            seen.add(cleaned["id"])
            merged.append(cleaned)
    for field in _default_band(code, band):
        if field["id"] in seen:
            continue
        hidden = {**field, "visible": False}
        merged.append(hidden)
    return merged


def _empty_formats(code: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    band_layout = {band: _default_band(code, band) for band in BANDS}
    return {fmt: deepcopy(band_layout) for fmt in STANDARD_PAGES}


def default_document_layout(code: str) -> dict[str, Any]:
    code_u = code.upper()
    if code_u not in DOCUMENT_NAMES:
        code_u = "OPD_BILL"
    return {
        "version": LAYOUT_VERSION,
        "kind": KIND_BILL,
        "designed": False,
        "formats": _empty_formats(code_u),
        "custom_pages": {},
        "page": {fmt: {"orientation": "portrait"} for fmt in STANDARD_PAGES},
    }


def custom_pages_of(layout: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (layout or {}).get("custom_pages") or {}
    pages: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return pages
    for key, value in raw.items():
        code = str(key or "").strip().upper()
        if not code.startswith("CUSTOM_") or not isinstance(value, dict):
            continue
        try:
            width = float(value.get("width_mm") or value.get("widthMm") or 0)
            height = float(value.get("height_mm") or value.get("heightMm") or 0)
        except (TypeError, ValueError):
            continue
        if width < 40 or height < 40 or width > 1000 or height > 1000:
            continue
        pages[code] = {
            "name": str(value.get("name") or code)[:80],
            "width_mm": round(width, 1),
            "height_mm": round(height, 1),
        }
    return pages


def paper_mm(layout: dict[str, Any] | None, bill_format: str | None) -> tuple[float, float]:
    fmt = (bill_format or "A4").upper()
    pages = custom_pages_of(layout)
    if fmt in pages:
        page = pages[fmt]
        return page["width_mm"], page["height_mm"]
    if fmt in STANDARD_PAGES:
        _name, width, height = STANDARD_PAGES[fmt]
        return width, height
    return STANDARD_PAGES["A4"][1], STANDARD_PAGES["A4"][2]


def resolve_format(layout: dict[str, Any] | None, bill_format: str | None) -> str:
    fmt = (bill_format or "A4").strip().upper() or "A4"
    if fmt in STANDARD_PAGES or fmt in custom_pages_of(layout):
        return fmt
    if fmt == "CUSTOM":
        pages = custom_pages_of(layout)
        if len(pages) == 1:
            return next(iter(pages))
    return "A4"


def normalize_layout(code: str, raw: Any) -> dict[str, Any]:
    code_u = (code or "OPD_BILL").upper()
    if code_u not in DOCUMENT_NAMES:
        code_u = "OPD_BILL"
    base = default_document_layout(code_u)
    if not isinstance(raw, dict):
        return base
    designed = bool(raw.get("designed"))
    custom_pages = custom_pages_of(raw)
    formats_in = raw.get("formats") if isinstance(raw.get("formats"), dict) else {}
    formats: dict[str, dict[str, list[dict[str, Any]]]] = {}
    page_meta_in = raw.get("page") if isinstance(raw.get("page"), dict) else {}
    page_meta: dict[str, dict[str, str]] = {}
    keys = list(STANDARD_PAGES.keys()) + list(custom_pages.keys())
    for fmt in keys:
        saved = formats_in.get(fmt) if isinstance(formats_in.get(fmt), dict) else {}
        formats[fmt] = {band: _merge_band(code_u, band, saved.get(band)) for band in BANDS}
        orientation = "portrait"
        meta = page_meta_in.get(fmt)
        if isinstance(meta, dict) and str(meta.get("orientation") or "").lower() == "landscape":
            orientation = "landscape"
        page_meta[fmt] = {"orientation": orientation}
    return {
        "version": LAYOUT_VERSION,
        "kind": KIND_BILL,
        "designed": designed,
        "formats": formats,
        "custom_pages": custom_pages,
        "page": page_meta,
    }


def layout_for_format(layout: dict[str, Any], bill_format: str | None) -> dict[str, list[dict[str, Any]]]:
    fmt = resolve_format(layout, bill_format)
    formats = layout.get("formats") or {}
    band = formats.get(fmt) or formats.get("A4") or {}
    return {name: list(band.get(name) or []) for name in BANDS}


def sample_context(code: str) -> dict[str, Any]:
    lines = [
        {"sr": 1, "code": "CON", "name": "Consultation", "category": "OPD", "rate": "500.00", "qty": 1, "amount": "500.00"},
        {"sr": 2, "code": "CBC", "name": "Complete Blood Count", "category": "Lab", "rate": "350.00", "qty": 1, "amount": "350.00"},
    ]
    if code == "PHARMACY_SALE_BILL":
        lines = [
            {"sr": 1, "code": "PCM", "name": "Paracetamol 500", "category": "B001", "rate": "2.00", "qty": 10, "amount": "20.00"},
        ]
    if code == "ADVANCE_RECEIPT":
        lines = []
    return {
        "hospital_name": "City Care Hospital",
        "hospital_address": "12 Main Road, Sample City",
        "hospital_phone": "080-4000-1000",
        "hospital_email": "billing@hospital.example",
        "hospital_gstin": "29AAAAA0000A1Z5",
        "hospital_website": "www.hospital.example",
        "bill_title": DOCUMENT_NAMES.get(code, "Bill"),
        "patient_no": "P00021",
        "patient_name": "Anita Rao",
        "patient_age": "34",
        "patient_gender": "Female",
        "doctor_name": "Dr Sharma",
        "referring_doctor": "Dr Iyer",
        "department_name": "General Medicine",
        "bill_no": "OP-1042",
        "bill_date": "23/09/2026",
        "voucher_no": "ADV-18",
        "voucher_date": "23/09/2026",
        "admission_no": "IP-220",
        "ward_name": "General",
        "bed_no": "12",
        "ward_bed": "General / 12",
        "stay_days": 3,
        "admission_date": "20/09/2026",
        "discharge_date": "23/09/2026",
        "scheme": "General",
        "cash_credit": "Cash",
        "token_number": "7",
        "sample_no": "S-88",
        "visit_category": "OPD",
        "gross_amount": "850.00",
        "admin_charges": "0.00",
        "scheme_discount": "50.00",
        "adjust_advance": "200.00",
        "net_amount": "600.00",
        "receipt_amount": "5,000.00",
        "amount": "5,000.00",
        "balance_after": "5,000.00",
        "payment_mode": "Cash",
        "payments": [{"mode": "Cash", "amount": "600.00"}],
        "remarks": "Sample preview",
        "lines": lines,
    }
