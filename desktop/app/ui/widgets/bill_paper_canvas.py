"""Paper-sized bill canvas. The sheet keeps its real millimetre size, and fields can be dragged."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

BANDS = ("header", "meta", "columns", "totals", "footer")

# Same sample as the server preview, so the sheet matches a printed bill.
SAMPLE = {
    "hospital_name": "City Care Hospital",
    "hospital_address": "12 Main Road, Sample City",
    "hospital_phone": "080-4000-1000",
    "hospital_email": "billing@hospital.example",
    "hospital_gstin": "29AAAAA0000A1Z5",
    "hospital_website": "www.hospital.example",
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
    "ward_bed": "General / 12",
    "stay_days": "3",
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
    "balance_after": "5,000.00",
    "payment_mode": "Cash",
    "remarks": "Sample preview",
    "lines": [
        {"sr": "1", "code": "CON", "name": "Consultation", "category": "OPD", "rate": "500.00", "qty": "1", "amount": "500.00"},
        {"sr": "2", "code": "CBC", "name": "Complete Blood Count", "category": "Lab", "rate": "350.00", "qty": "1", "amount": "350.00"},
    ],
}


def _font_pt(field_id: str, band: str, paper_w: float) -> float:
    if field_id == "hospital_name":
        pt = 16
    elif field_id == "bill_title":
        pt = 12
    elif field_id in {"computer_note", "thanks"}:
        pt = 8
    elif band == "columns":
        pt = 9
    else:
        pt = 10
    if paper_w < 110:
        pt = max(7, round(pt * paper_w / 148))
    elif paper_w < 160:
        pt = max(8, round(pt * paper_w / 180))
    return float(pt)


def _box_height(field_id: str, band: str, paper_w: float) -> float:
    if field_id == "hospital_name":
        return 6.5 if paper_w < 110 else 8.5
    if field_id == "signature":
        return 10
    if band == "columns":
        return 6
    return 5.2 if paper_w < 110 else 6.2


def place_missing(fields: list[dict], band: str, paper_w: float) -> None:
    """Give visible fields that have never been dragged a starting box on this paper."""
    visible = [field for field in fields if field.get("visible")]
    missing = [field for field in visible if field.get("x_mm") is None]
    if not missing:
        return
    pad = 1.5
    inner = max(30.0, paper_w - pad * 2)
    placed = [field for field in visible if field.get("x_mm") is not None]
    y = 1.0
    if placed:
        y = max(float(field.get("y_mm") or 0) + float(field.get("height_mm") or 6) for field in placed) + 0.8

    def apply(field: dict, x: float, top: float, width: float, height: float) -> None:
        field["x_mm"] = round(x, 1)
        field["y_mm"] = round(top, 1)
        field["width_mm"] = round(max(6.0, width), 1)
        field["height_mm"] = round(height, 1)
        if field.get("font_size_pt") is None:
            field["font_size_pt"] = _font_pt(str(field.get("id") or ""), band, paper_w)
        if band == "columns":
            field["width"] = field["width_mm"]

    if band == "columns":
        total = sum(float(field.get("width") or 10) for field in missing) or 1
        x = pad
        for field in missing:
            width = inner * float(field.get("width") or 10) / total
            apply(field, x, y, width, _box_height(str(field.get("id") or ""), band, paper_w))
            x += width
        return

    per_row = 1
    if band == "meta":
        per_row = 3 if inner >= 140 else 2 if inner >= 70 else 1
    elif band == "totals":
        per_row = 1
    stacked = {
        "hospital_name",
        "hospital_address",
        "hospital_phone",
        "hospital_email",
        "hospital_gstin",
        "hospital_website",
        "bill_title",
        "computer_note",
        "thanks",
        "signature",
    }
    row: list[dict] = []

    def flush() -> None:
        nonlocal y, row
        if not row:
            return
        cell = inner / len(row)
        height = max(_box_height(str(field.get("id") or ""), band, paper_w) for field in row)
        for index, field in enumerate(row):
            apply(field, pad + index * cell, y, cell - 0.4, height)
        y += height + 0.6
        row = []

    for field in missing:
        fid = str(field.get("id") or "")
        if band == "header" or fid in stacked or fid.startswith("static_"):
            flush()
            row = [field]
            flush()
            continue
        if band == "totals":
            flush()
            apply(field, pad + inner * 0.45, y, inner * 0.55, _box_height(fid, band, paper_w))
            y += float(field["height_mm"]) + 0.4
            continue
        row.append(field)
        if len(row) >= per_row:
            flush()
    flush()


def fit_to_paper(bands: dict[str, list[dict]], paper_w: float) -> None:
    rights: list[float] = []
    for fields in bands.values():
        for field in fields:
            if field.get("visible") and field.get("x_mm") is not None:
                rights.append(float(field.get("x_mm") or 0) + float(field.get("width_mm") or 0))
    if not rights or max(rights) <= paper_w + 0.4:
        return
    ratio = paper_w / max(rights)
    for band, fields in bands.items():
        for field in fields:
            if field.get("x_mm") is None:
                continue
            field["x_mm"] = round(float(field["x_mm"]) * ratio, 1)
            field["width_mm"] = round(max(6.0, float(field.get("width_mm") or 10) * ratio), 1)
            if band == "columns":
                field["width"] = field["width_mm"]


def preview_text(field: dict, band: str, sample: dict) -> str:
    fid = str(field.get("id") or "")
    if fid.startswith("static_") or fid in {"computer_note", "signature", "thanks", "bill_title"}:
        text = str(field.get("text") or field.get("label") or "")
        if fid == "bill_title" and not str(field.get("text") or "").strip():
            text = str(sample.get("bill_title") or field.get("label") or "Bill")
        return text
    if band == "columns":
        return str(field.get("label") or fid)
    value = sample.get(fid)
    if value is None:
        value = ""
    if band == "header":
        return str(value or field.get("label") or "")
    if band == "totals":
        label = str(field.get("label") or "")
        return f"{label}   {value}".strip()
    if not str(value).strip():
        return str(field.get("label") or fid)
    label = str(field.get("label") or "")
    return f"{label} : {value}" if label else str(value)


class BillPaperCanvas(QWidget):
    """White sheet drawn at the selected paper size. Drag a field; drag its corner to resize."""

    fieldActivated = Signal(str, str)
    geometryChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 360)
        self.setMouseTracking(True)
        self._bands: dict[str, list[dict]] = {}
        self._paper_w = 210.0
        self._paper_h = 297.0
        self._page_label = "A4"
        self._sample = dict(SAMPLE)
        self._selected: tuple[str, str] | None = None
        self._drag: dict | None = None
        self._origin = QPointF(0, 0)
        self._scale = 2.0
        self._ghost: QRectF | None = None
        self.setStyleSheet("background: #cbd5e1;")

    def set_bill(
        self,
        bands: dict[str, list[dict]],
        paper_w: float,
        paper_h: float,
        page_label: str,
        *,
        bill_title: str = "Bill",
    ) -> None:
        self._bands = bands
        self._paper_w = max(40.0, float(paper_w))
        self._paper_h = max(40.0, float(paper_h))
        self._page_label = page_label
        self._sample = dict(SAMPLE)
        self._sample["bill_title"] = bill_title
        for band in BANDS:
            place_missing(self._bands.get(band) or [], band, self._paper_w)
        fit_to_paper(self._bands, self._paper_w)
        self.update()

    def select_field(self, band: str, field_id: str) -> None:
        self._selected = (band, field_id)
        self.update()

    def _measure(self) -> tuple[QPointF, float, float]:
        """Keep a small slip smaller than A4, but large enough that the type can be read."""
        avail_w = max(self.width() - 28, 40)
        avail_h = max(self.height() - 78, 40)
        # 10pt prints at about 12 screen pixels. A half page then stays well under A4.
        readable = 12.0 * 72.0 / (10.0 * 25.4)
        scale = readable
        if self._paper_w * scale > avail_w or self._paper_h * scale > avail_h:
            scale = min(avail_w / self._paper_w, avail_h / self._paper_h)
        page_w = self._paper_w * scale
        page_h = self._paper_h * scale
        top = 28.0
        origin = QPointF((self.width() - page_w) / 2, top + max(0.0, (avail_h - page_h) / 2))
        self._origin = origin
        self._scale = scale
        ghost_w = 210.0 * scale
        ghost_h = 297.0 * scale
        if ghost_w <= self.width() - 8 and ghost_h <= avail_h and (self._paper_w < 200 or self._paper_h < 280):
            self._ghost = QRectF((self.width() - ghost_w) / 2, top + max(0.0, (avail_h - ghost_h) / 2), ghost_w, ghost_h)
        else:
            self._ghost = None
        return origin, page_w, page_h

    def _band_tops(self) -> list[tuple[str, float, float]]:
        top = 2.0
        boxes: list[tuple[str, float, float]] = []
        lines = self._sample.get("lines") or []
        for band in BANDS:
            fields = [
                field
                for field in (self._bands.get(band) or [])
                if field.get("visible") and field.get("x_mm") is not None
            ]
            if not fields:
                continue
            bottom = max(float(field.get("y_mm") or 0) + float(field.get("height_mm") or 6) for field in fields)
            extra = 0.0
            if band == "columns":
                extra = 1.5 + 4.4 * min(len(lines), 3)
            height = bottom + extra + 1.2
            boxes.append((band, top, height))
            top += height
        return boxes

    def _field_rect(self, band_top: float, field: dict) -> QRectF:
        x = self._origin.x() + float(field.get("x_mm") or 0) * self._scale
        y = self._origin.y() + (band_top + float(field.get("y_mm") or 0)) * self._scale
        w = max(4.0, float(field.get("width_mm") or 10) * self._scale)
        h = max(4.0, float(field.get("height_mm") or 6) * self._scale)
        return QRectF(x, y, w, h)

    def _hit(self, pos: QPointF) -> tuple[str, dict, str] | None:
        bands = {band: top for band, top, _height in self._band_tops()}
        for band in reversed(BANDS):
            if band not in bands:
                continue
            fields = [
                field
                for field in (self._bands.get(band) or [])
                if field.get("visible") and field.get("x_mm") is not None
            ]
            for field in reversed(fields):
                rect = self._field_rect(bands[band], field)
                handle = QRectF(rect.right() - 8, rect.bottom() - 8, 8, 8)
                if handle.contains(pos) and self._selected == (band, field.get("id")):
                    return band, field, "resize"
                if rect.contains(pos):
                    return band, field, "move"
        return None

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#cbd5e1"))
        origin, page_w, page_h = self._measure()
        if self._ghost is not None:
            painter.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(self._ghost)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(self._ghost.left(), self._ghost.top() - 16, 120, 14), "A4 for comparison")
        shadow = QRectF(origin.x() + 3, origin.y() + 3, page_w, page_h)
        painter.fillRect(shadow, QColor(15, 23, 42, 40))
        page = QRectF(origin.x(), origin.y(), page_w, page_h)
        painter.fillRect(page, QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0f172a"), 1))
        painter.drawRect(page)

        bands = self._band_tops()
        content_h = 2.0
        if bands:
            _band, top, height = bands[-1]
            content_h = top + height
        if content_h > self._paper_h:
            cut = origin.y() + self._paper_h * self._scale
            painter.setPen(QPen(QColor("#dc2626"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(page.left(), cut), QPointF(page.right(), cut))

        band_top = {band: top for band, top, _height in bands}
        for band, top, _height in bands:
            fields = [
                field
                for field in (self._bands.get(band) or [])
                if field.get("visible") and field.get("x_mm") is not None
            ]
            if band == "columns" and fields:
                self._paint_column_lines(painter, top, fields)
            for field in fields:
                self._paint_field(painter, band, top, field)

        painter.setPen(QColor("#0f172a"))
        label_font = QFont("Segoe UI", 11)
        label_font.setBold(True)
        painter.setFont(label_font)
        caption = f"{self._page_label}   ·   {self._paper_w:.1f} × {self._paper_h:.1f} mm"
        painter.drawText(QRectF(0, 2, self.width(), 22), Qt.AlignmentFlag.AlignCenter, caption)
        self._paint_size_key(painter)
        if content_h > self._paper_h + 1:
            painter.setPen(QColor("#b91c1c"))
            note_font = QFont("Segoe UI", 8)
            painter.setFont(note_font)
            painter.drawText(
                QRectF(8, self.height() - 48, self.width() - 16, 16),
                Qt.AlignmentFlag.AlignCenter,
                "Content is taller than this paper — drag fields up, hide some, or use a larger page.",
            )
        painter.end()

    def _paint_size_key(self, painter: QPainter) -> None:
        """Two bars: this paper against A4, so a half page cannot be mistaken for A4."""
        reference = max(self._paper_w, 210.0)
        max_bar = min(260.0, max(80.0, self.width() - 160))
        left = (self.width() - max_bar) / 2
        y = self.height() - 28
        page_bar = max(12.0, max_bar * (self._paper_w / reference))
        a4_bar = max(12.0, max_bar * (210.0 / reference))
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(left - 70, y - 14, 66, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self._paper_w:.0f} mm")
        painter.fillRect(QRectF(left, y - 12, page_bar, 8), QColor("#1d4ed8"))
        painter.drawText(QRectF(left - 70, y + 2, 66, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "A4 210")
        painter.fillRect(QRectF(left, y + 4, a4_bar, 8), QColor("#94a3b8"))

    def _paint_column_lines(self, painter: QPainter, band_top: float, fields: list[dict]) -> None:
        lines = list(self._sample.get("lines") or [])[:3]
        if not lines:
            return
        header_bottom = max(float(field.get("y_mm") or 0) + float(field.get("height_mm") or 6) for field in fields)
        left = min(float(field.get("x_mm") or 0) for field in fields)
        right = max(float(field.get("x_mm") or 0) + float(field.get("width_mm") or 0) for field in fields)
        row_h = 4.2 * self._scale
        font = QFont("Times New Roman")
        font.setPixelSize(max(10, int(round(8 * self._scale * 25.4 / 72))))
        painter.setFont(font)
        painter.setPen(QColor("#000000"))
        ordered = sorted(fields, key=lambda field: float(field.get("x_mm") or 0))
        for index, line in enumerate(lines):
            y = self._origin.y() + (band_top + header_bottom + 0.6) * self._scale + index * row_h
            row = QRectF(
                self._origin.x() + left * self._scale,
                y,
                max(4, (right - left) * self._scale),
                row_h,
            )
            painter.setPen(QPen(QColor("#000000"), 1))
            painter.drawRect(row)
            cursor = left
            for field in ordered:
                x = float(field.get("x_mm") or 0)
                width = float(field.get("width_mm") or 10)
                if x > cursor + 0.4:
                    cursor = x
                cell = QRectF(
                    self._origin.x() + x * self._scale,
                    y,
                    max(2, width * self._scale),
                    row_h,
                )
                fid = str(field.get("id") or "")
                text = "" if line.get(fid) is None else str(line.get(fid))
                flags = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
                align = field.get("align") or "left"
                if align == "center":
                    flags |= Qt.AlignmentFlag.AlignHCenter
                elif align == "right":
                    flags |= Qt.AlignmentFlag.AlignRight
                else:
                    flags |= Qt.AlignmentFlag.AlignLeft
                painter.setPen(QColor("#000000"))
                painter.drawText(cell.adjusted(2, 0, -2, 0), flags, text)
                cursor = x + width

    def _paint_field(self, painter: QPainter, band: str, band_top: float, field: dict) -> None:
        rect = self._field_rect(band_top, field)
        selected = self._selected == (band, field.get("id"))
        if selected:
            painter.fillRect(rect, QColor(219, 234, 254, 180))
            painter.setPen(QPen(QColor("#1d4ed8"), 1.4))
        else:
            painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawRect(rect)
        if str(field.get("id")) == "signature":
            painter.setPen(QPen(QColor("#000000"), 1))
            painter.drawLine(QPointF(rect.left() + 2, rect.top() + 2), QPointF(rect.right() - 2, rect.top() + 2))
        pt = float(field.get("font_size_pt") or 10)
        font = QFont("Times New Roman")
        font.setPixelSize(max(11, int(round(pt * self._scale * 25.4 / 72))))
        font.setBold(str(field.get("id")) not in {"computer_note", "thanks"} and not str(field.get("id")).startswith("static_"))
        font.setUnderline(str(field.get("id")) == "bill_title")
        painter.setFont(font)
        painter.setPen(QColor("#000000"))
        flags = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
        align = field.get("align") or ("center" if band == "header" else "left")
        if align == "center":
            flags |= Qt.AlignmentFlag.AlignHCenter
        elif align == "right":
            flags |= Qt.AlignmentFlag.AlignRight
        else:
            flags |= Qt.AlignmentFlag.AlignLeft
        text = preview_text(field, band, self._sample)
        painter.drawText(rect.adjusted(3, 1, -3, -1), flags, text)
        if selected:
            handle = QRectF(rect.right() - 7, rect.bottom() - 7, 7, 7)
            painter.fillRect(handle, QColor("#1d4ed8"))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._measure()
        hit = self._hit(event.position())
        if hit is None:
            self._selected = None
            self._drag = None
            self.update()
            return
        band, field, kind = hit
        self._selected = (band, str(field.get("id") or ""))
        self._drag = {
            "kind": kind,
            "band": band,
            "field": field,
            "start": event.position(),
            "x": float(field.get("x_mm") or 0),
            "y": float(field.get("y_mm") or 0),
            "w": float(field.get("width_mm") or 10),
            "h": float(field.get("height_mm") or 6),
        }
        self.fieldActivated.emit(band, str(field.get("id") or ""))
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is None or self._scale <= 0:
            hit = self._hit(event.position()) if self._selected else None
            if hit and hit[2] == "resize":
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif hit:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.unsetCursor()
            return
        delta = event.position() - self._drag["start"]
        dx = delta.x() / self._scale
        dy = delta.y() / self._scale
        field = self._drag["field"]
        if self._drag["kind"] == "resize":
            width = max(8.0, min(self._paper_w - self._drag["x"], self._drag["w"] + dx))
            height = max(4.0, self._drag["h"] + dy)
            field["width_mm"] = round(width, 1)
            field["height_mm"] = round(height, 1)
            if self._drag["band"] == "columns":
                field["width"] = field["width_mm"]
        else:
            width = float(field.get("width_mm") or self._drag["w"])
            field["x_mm"] = round(min(max(0.0, self._drag["x"] + dx), max(0.0, self._paper_w - width)), 1)
            field["y_mm"] = round(max(0.0, self._drag["y"] + dy), 1)
        self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        if self._drag is not None:
            self._drag = None
            self.geometryChanged.emit()
            self.unsetCursor()
