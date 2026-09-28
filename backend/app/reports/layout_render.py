"""Render a saved bill layout to printable HTML (table-based, same engine idea as GenERP)."""

from __future__ import annotations

import html
from typing import Any

from app.reports.print_layouts import (
    layout_for_format,
    normalize_layout,
    paper_mm,
    resolve_format,
)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _field_text(field: dict[str, Any], context: dict[str, Any], line: dict[str, Any] | None = None) -> str:
    fid = field["id"]
    if fid.startswith("static_") or fid in {"computer_note", "signature", "thanks"}:
        return str(field.get("text") or field.get("label") or "")
    if fid == "bill_title":
        return str(field.get("text") or context.get("bill_title") or field.get("label") or "")
    if line is not None:
        return "" if line.get(fid) is None else str(line.get(fid))
    if fid == "payment_mode":
        payments = context.get("payments") or []
        if isinstance(payments, list) and payments:
            modes = [str(item.get("mode") or "").strip() for item in payments if isinstance(item, dict)]
            modes = [mode for mode in modes if mode]
            if modes:
                return ", ".join(modes)
        return str(context.get("payment_mode") or "")
    if fid == "ward_bed":
        explicit = context.get("ward_bed")
        if explicit:
            return str(explicit)
        return f"{context.get('ward_name') or '—'} / {context.get('bed_no') or '—'}"
    if fid == "receipt_amount":
        return str(context.get("receipt_amount") or context.get("amount") or "")
    value = context.get(fid)
    if value is None or value == "":
        return ""
    return str(value)


def _align(field: dict[str, Any]) -> str:
    align = field.get("align") or "left"
    return align if align in {"left", "center", "right"} else "left"


def _visible(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [field for field in fields if field.get("visible")]


def _p(text: str, field: dict[str, Any], *, size: str = "11pt", bold: bool = True) -> str:
    if not str(text).strip():
        return ""
    weight = "bold" if bold else "normal"
    return (
        f"<p style='margin:0;padding:1px 0;text-align:{_align(field)};"
        f"font-size:{size};font-weight:{weight};'>{_esc(text)}</p>"
    )


def _header_html(fields: list[dict[str, Any]], context: dict[str, Any]) -> str:
    bits: list[str] = []
    for field in _visible(fields):
        text = _field_text(field, context)
        if field["id"] == "hospital_name":
            bits.append(_p(text, {**field, "align": field.get("align") or "center"}, size="16pt"))
        elif field["id"] == "bill_title":
            bits.append(
                f"<p style='margin:4px 0 6px;text-align:center;font-size:12pt;font-weight:bold;"
                f"text-decoration:underline;'>{_esc(text)}</p>"
            )
        else:
            bits.append(_p(text, {**field, "align": field.get("align") or "center"}, size="10pt"))
    return "".join(bits)


def _meta_html(fields: list[dict[str, Any]], context: dict[str, Any]) -> str:
    visible = []
    for field in _visible(fields):
        value = _field_text(field, context)
        if not str(value).strip():
            continue
        visible.append((field, value))
    if not visible:
        return ""
    cells = []
    for field, value in visible:
        label = field.get("label") or field["id"]
        cells.append(
            f"<td style='font-size:11pt;font-weight:bold;padding:2px 4px;text-align:{_align(field)};'>"
            f"{_esc(label)} : {_esc(value)}</td>"
        )
    rows = []
    for index in range(0, len(cells), 3):
        chunk = cells[index : index + 3]
        while len(chunk) < 3:
            chunk.append("<td>&nbsp;</td>")
        rows.append("<tr>" + "".join(chunk) + "</tr>")
    return (
        "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:4px;'>"
        + "".join(rows)
        + "</table>"
    )


def _mm(field: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if field.get(key) is None or field.get(key) == "":
            continue
        try:
            return float(field[key])
        except (TypeError, ValueError):
            return None
    return None


def _is_placed(fields: list[dict[str, Any]]) -> bool:
    visible = _visible(fields)
    return bool(visible) and all(_mm(field, "x_mm", "xMm") is not None for field in visible)


def _col_weight(field: dict[str, Any]) -> float:
    placed = _mm(field, "width_mm", "widthMm")
    if placed is not None and placed > 0:
        return placed
    try:
        return float(field.get("width") or 10)
    except (TypeError, ValueError):
        return 10.0


def _columns_html(fields: list[dict[str, Any]], context: dict[str, Any]) -> str:
    visible = _visible(fields)
    if not visible:
        return ""
    if _is_placed(fields):
        visible = sorted(visible, key=lambda field: _mm(field, "x_mm", "xMm") or 0)
    total_width = sum(_col_weight(field) for field in visible) or 1
    header_cells = []
    for field in visible:
        pct = round(_col_weight(field) / total_width * 100, 2)
        header_cells.append(
            f"<td width='{pct}%' style='border:1px solid #000;padding:2px 3px;{_font_css(field, fallback='10pt')}"
            f"font-weight:bold;text-align:{_align(field)};'>{_esc(field.get('label') or '')}</td>"
        )
    body = []
    for line in context.get("lines") or []:
        if not isinstance(line, dict):
            continue
        tds = []
        for field in visible:
            pct = round(_col_weight(field) / total_width * 100, 2)
            tds.append(
                f"<td width='{pct}%' style='border:1px solid #000;padding:2px 3px;{_font_css(field, fallback='10pt')}"
                f"font-weight:bold;text-align:{_align(field)};'>{_esc(_field_text(field, context, line))}</td>"
            )
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (
        "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:6px;border-collapse:collapse;'>"
        f"<tr>{''.join(header_cells)}</tr>{''.join(body)}</table>"
    )


def _totals_html(fields: list[dict[str, Any]], context: dict[str, Any]) -> str:
    rows = []
    for field in _visible(fields):
        value = _field_text(field, context)
        if not str(value).strip() or value in {"0.00", "0"}:
            if field["id"] not in {"net_amount", "receipt_amount"}:
                continue
        rows.append(
            "<tr>"
            f"<td style='font-size:11pt;font-weight:bold;text-align:right;padding:1px 8px;'>"
            f"{_esc(field.get('label') or '')}</td>"
            f"<td style='font-size:11pt;font-weight:bold;text-align:right;padding:1px 0;width:90px;'>"
            f"{_esc(value)}</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:6px;'>"
        "<tr><td width='70%'>&nbsp;</td><td width='30%'>"
        "<table width='100%' cellspacing='0' cellpadding='0'>"
        + "".join(rows)
        + "</table></td></tr></table>"
    )


def _footer_html(fields: list[dict[str, Any]], context: dict[str, Any]) -> str:
    bits = []
    for field in _visible(fields):
        text = _field_text(field, context)
        if not str(text).strip():
            continue
        if field["id"] in {"computer_note", "thanks"} or field["id"].startswith("static_"):
            bits.append(_p(text, field, size="9pt", bold=False))
        elif field["id"] == "signature":
            bits.append(
                "<table width='100%' style='margin-top:18px;'><tr>"
                "<td width='55%'>&nbsp;</td>"
                f"<td width='45%' style='border-top:1px solid #000;text-align:center;font-size:11pt;font-weight:bold;padding-top:4px;'>"
                f"{_esc(text)}</td></tr></table>"
            )
        else:
            label = field.get("label") or ""
            bits.append(_p(f"{label} : {text}", field))
    return "".join(bits)


def _placed_body(field: dict[str, Any], context: dict[str, Any], band: str) -> str:
    text = _field_text(field, context)
    if band in {"header", "columns"}:
        return text if band == "header" else str(field.get("label") or "")
    if band == "totals":
        label = str(field.get("label") or "")
        return f"{label}  {text}".strip()
    if field["id"] in {"computer_note", "thanks", "signature"} or str(field["id"]).startswith("static_"):
        return text
    label = str(field.get("label") or "")
    if str(text).strip():
        return f"{label} : {text}" if label else text
    return label


def _font_css(field: dict[str, Any], *, fallback: str) -> str:
    size = field.get("font_size_pt")
    if size is None:
        size = field.get("fontSizePt")
    try:
        points = float(size) if size is not None else None
    except (TypeError, ValueError):
        points = None
    if points is None:
        return f"font-size:{fallback};"
    return f"font-size:{points:g}pt;"


def _placed_band_html(fields: list[dict[str, Any]], context: dict[str, Any], band: str, inner_mm: float) -> str:
    visible = [field for field in _visible(fields) if _mm(field, "x_mm", "xMm") is not None]
    if not visible:
        return ""
    rows: list[list[dict[str, Any]]] = []
    for field in sorted(visible, key=lambda item: ((_mm(item, "y_mm", "yMm") or 0), (_mm(item, "x_mm", "xMm") or 0))):
        y = _mm(field, "y_mm", "yMm") or 0
        if rows and abs(y - (_mm(rows[-1][0], "y_mm", "yMm") or 0)) < 2.0:
            rows[-1].append(field)
        else:
            rows.append([field])
    tables: list[str] = []
    inner = max(inner_mm, 1.0)
    for row in rows:
        ordered = sorted(row, key=lambda item: _mm(item, "x_mm", "xMm") or 0)
        cursor = 0.0
        cells: list[tuple[float, str]] = []
        for field in ordered:
            x = max(0.0, _mm(field, "x_mm", "xMm") or 0)
            width = max(4.0, _mm(field, "width_mm", "widthMm") or 20)
            if x > cursor + 0.8:
                cells.append((x - cursor, ""))
            body = _placed_body(field, context, band)
            if band != "columns" and not str(body).strip():
                cursor = max(cursor, x + width)
                continue
            weight = "normal" if field["id"] in {"computer_note", "thanks"} or str(field["id"]).startswith("static_") else "bold"
            border = ""
            if field["id"] == "signature":
                border = "border-top:1px solid #000;"
            style = (
                f"padding:1px 2px;{_font_css(field, fallback='10pt')}font-weight:{weight};"
                f"text-align:{_align(field)};vertical-align:top;{border}"
            )
            cells.append((width, f"<td style='{style}'>{_esc(body)}</td>"))
            cursor = max(cursor, x + width)
        if cursor < inner - 0.8:
            cells.append((inner - cursor, ""))
        if not any(html_bit for _w, html_bit in cells):
            continue
        total = sum(width for width, _html in cells) or 1
        rendered = []
        for width, html_bit in cells:
            pct = max(1.0, round(width / total * 100, 2))
            if html_bit:
                rendered.append(html_bit.replace("<td ", f"<td width='{pct}%' ", 1))
            else:
                rendered.append(f"<td width='{pct}%'>&nbsp;</td>")
        tables.append(
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin:0;'><tr>"
            + "".join(rendered)
            + "</tr></table>"
        )
    return "".join(tables)


def _band_html(band: str, fields: list[dict[str, Any]], context: dict[str, Any], inner_mm: float) -> str:
    if band != "columns" and _is_placed(fields):
        return _placed_band_html(fields, context, band, inner_mm)
    if band == "header":
        return _header_html(fields, context)
    if band == "meta":
        return _meta_html(fields, context)
    if band == "columns":
        return _columns_html(fields, context)
    if band == "totals":
        return _totals_html(fields, context)
    return _footer_html(fields, context)


def render_bill_html(context: dict[str, Any], layout: dict[str, Any], bill_format: str | None) -> str:
    fmt = resolve_format(layout, bill_format)
    bands = layout_for_format(layout, fmt)
    width, height = paper_mm(layout, fmt)
    orientation = ((layout.get("page") or {}).get(fmt) or {}).get("orientation") or "portrait"
    if orientation == "landscape":
        width, height = height, width
    inner = "".join(_band_html(name, bands[name], context, width) for name in ("header", "meta", "columns", "totals", "footer"))
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        f"<title>{_esc(context.get('bill_title') or 'Bill')}</title>"
        "<style>body{font-family:'Times New Roman',Times,serif;color:#000;margin:0;padding:0;}"
        "table{border-collapse:collapse;}</style></head>"
        f"<body data-page-w='{width}' data-page-h='{height}' data-page-orientation='{orientation}'>"
        f"{inner}</body></html>"
    )


def render_document_html(*, code: str, context: dict[str, Any], layout_raw: Any, bill_format: str | None) -> str:
    layout = normalize_layout(code, layout_raw)
    return render_bill_html(context, layout, bill_format)
