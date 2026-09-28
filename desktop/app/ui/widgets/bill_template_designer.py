"""Visual bill layout editor for OPD, IPD, pathology, pharmacy and advance receipts."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import BTN_PRIMARY, BTN_SECONDARY
from app.ui.widgets.bill_paper_canvas import BillPaperCanvas

_PAGE_MM = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "LETTER": (215.9, 279.4),
    "LEGAL": (215.9, 355.6),
}

BANDS = (
    ("header", "Header"),
    ("meta", "Patient details"),
    ("columns", "Columns"),
    ("totals", "Totals"),
    ("footer", "Footer"),
)
TEXT_FIELDS = {"bill_title", "computer_note", "signature", "thanks"}


class BillTemplateDesignerWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._layout: dict = {}
        self._code = "OPD_BILL"
        self._format = "A4"
        self._band = "header"
        self._loading = False
        self._build()
        self._load_catalog()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Bill Template Designer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        root.addWidget(title)
        hint = QLabel(
            "Design the printed page for each bill. The white sheet is the real paper size — "
            "a half page stays small, A4 fills the gray area. Drag a field to move it, and drag "
            "the blue corner to resize it. Printer choice stays in Print Master. "
            "Bills keep the old layout until you save a design here."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #475569;")
        root.addWidget(hint)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Document"))
        self.document_combo = QComboBox()
        self.document_combo.setMinimumWidth(200)
        self.document_combo.currentIndexChanged.connect(self._on_document)
        controls.addWidget(self.document_combo)
        controls.addWidget(QLabel("Page"))
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(220)
        self.page_combo.currentIndexChanged.connect(self._on_page)
        controls.addWidget(self.page_combo)
        controls.addWidget(QLabel("Orientation"))
        self.orientation = QComboBox()
        self.orientation.addItem("Portrait", "portrait")
        self.orientation.addItem("Landscape", "landscape")
        self.orientation.currentIndexChanged.connect(self._on_orientation)
        controls.addWidget(self.orientation)
        controls.addStretch()
        root.addLayout(controls)

        custom = QHBoxLayout()
        custom.addWidget(QLabel("Custom page"))
        self.custom_name = QLineEdit()
        self.custom_name.setPlaceholderText("Name, e.g. OPD slip")
        self.custom_width = QDoubleSpinBox()
        self.custom_width.setRange(40, 1000)
        self.custom_width.setValue(148)
        self.custom_width.setSuffix(" mm")
        self.custom_height = QDoubleSpinBox()
        self.custom_height.setRange(40, 1000)
        self.custom_height.setValue(210)
        self.custom_height.setSuffix(" mm")
        add_page = QPushButton("Add page")
        add_page.setStyleSheet(BTN_SECONDARY)
        add_page.clicked.connect(self._add_page)
        remove_page = QPushButton("Remove page")
        remove_page.setStyleSheet(BTN_SECONDARY)
        remove_page.clicked.connect(self._remove_page)
        custom.addWidget(self.custom_name)
        custom.addWidget(self.custom_width)
        custom.addWidget(self.custom_height)
        custom.addWidget(add_page)
        custom.addWidget(remove_page)
        custom.addStretch()
        root.addLayout(custom)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_band)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Show", "Caption", "Align", "Width", "Printed text"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 70)
        self.tabs_host = self.tabs
        for _band, label in BANDS:
            self.tabs.addTab(QWidget(), label)
        left_layout.addWidget(self.tabs)
        left_layout.addWidget(self.table, stretch=1)
        row_actions = QHBoxLayout()
        up = QPushButton("Move up")
        down = QPushButton("Move down")
        add_text = QPushButton("Add text line")
        remove = QPushButton("Remove text")
        for button in (up, down, add_text, remove):
            button.setStyleSheet(BTN_SECONDARY)
            row_actions.addWidget(button)
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        add_text.clicked.connect(self._add_text)
        remove.clicked.connect(self._remove_text)
        row_actions.addStretch()
        left_layout.addLayout(row_actions)
        splitter.addWidget(left)

        self.canvas = BillPaperCanvas()
        self.canvas.fieldActivated.connect(self._on_canvas_field)
        self.canvas.geometryChanged.connect(self._on_canvas_geometry)
        splitter.addWidget(self.canvas)
        splitter.setSizes([460, 640])
        root.addWidget(splitter, stretch=1)

        actions = QHBoxLayout()
        preview_btn = QPushButton("Refresh preview")
        preview_btn.setStyleSheet(BTN_SECONDARY)
        preview_btn.clicked.connect(self._sync_canvas)
        reset_btn = QPushButton("Reset to default")
        reset_btn.setStyleSheet(BTN_SECONDARY)
        reset_btn.clicked.connect(self._reset)
        save_btn = QPushButton("Save template")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._save)
        actions.addWidget(preview_btn)
        actions.addWidget(reset_btn)
        actions.addStretch()
        actions.addWidget(save_btn)
        root.addLayout(actions)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_table_selection)

    def _load_catalog(self) -> None:
        try:
            catalog = self.api.get_print_layout_catalog()
        except ApiError as exc:
            QMessageBox.warning(self, "Bill templates", str(exc))
            return
        self.document_combo.blockSignals(True)
        self.document_combo.clear()
        for doc in catalog.get("documents") or []:
            self.document_combo.addItem(doc.get("name") or doc.get("code"), doc.get("code"))
        self.document_combo.blockSignals(False)
        if self.document_combo.count():
            self._on_document()

    def _on_document(self) -> None:
        code = self.document_combo.currentData()
        if not code:
            return
        self._code = code
        try:
            payload = self.api.get_print_layout(code)
        except ApiError as exc:
            QMessageBox.warning(self, "Bill templates", str(exc))
            return
        self._layout = payload.get("layout") or {}
        paper = (payload.get("paper_size") or "A4").upper()
        if paper == "CUSTOM":
            pages = (self._layout.get("custom_pages") or {})
            paper = next(iter(pages), "A4")
        self._fill_pages(select=paper)
        orientation = payload.get("orientation") or "portrait"
        index = self.orientation.findData(orientation)
        self.orientation.blockSignals(True)
        if index >= 0:
            self.orientation.setCurrentIndex(index)
        self.orientation.blockSignals(False)
        self._fill_table()
        self._sync_canvas()

    def _fill_pages(self, select: str | None = None) -> None:
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        for code, label in (
            ("A4", "A4"),
            ("A5", "A5"),
            ("A6", "A6"),
            ("LETTER", "Letter"),
            ("LEGAL", "Legal"),
        ):
            self.page_combo.addItem(label, code)
        for code, page in (self._layout.get("custom_pages") or {}).items():
            name = page.get("name") or code
            self.page_combo.addItem(
                f"{name} ({page.get('width_mm')} × {page.get('height_mm')} mm)",
                code,
            )
        target = select or self._format
        index = self.page_combo.findData(target)
        self.page_combo.setCurrentIndex(index if index >= 0 else 0)
        self._format = self.page_combo.currentData() or "A4"
        self.page_combo.blockSignals(False)

    def _on_page(self) -> None:
        self._commit_table()
        self._format = self.page_combo.currentData() or "A4"
        page = (self._layout.get("page") or {}).get(self._format) or {}
        orientation = page.get("orientation") or "portrait"
        index = self.orientation.findData(orientation)
        self.orientation.blockSignals(True)
        if index >= 0:
            self.orientation.setCurrentIndex(index)
        self.orientation.blockSignals(False)
        self._fill_table()
        self._sync_canvas()

    def _on_band(self, index: int) -> None:
        if index < 0:
            return
        self._commit_table()
        self._band = BANDS[index][0]
        self._fill_table()

    def _fields(self) -> list[dict]:
        formats = self._layout.setdefault("formats", {})
        band_layout = formats.setdefault(self._format, {})
        return band_layout.setdefault(self._band, [])

    def _fill_table(self) -> None:
        self._loading = True
        self.table.blockSignals(True)
        fields = self._fields()
        self.table.setRowCount(0)
        show_width = self._band == "columns"
        self.table.setColumnHidden(3, not show_width)
        for field in fields:
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QCheckBox()
            check.setChecked(bool(field.get("visible", True)))
            check.stateChanged.connect(lambda _s, r=row: self._on_check(r))
            wrap = QWidget()
            box = QHBoxLayout(wrap)
            box.setContentsMargins(0, 0, 0, 0)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(check)
            self.table.setCellWidget(row, 0, wrap)
            caption = QTableWidgetItem(str(field.get("label") or ""))
            caption.setData(Qt.ItemDataRole.UserRole, field.get("id"))
            self.table.setItem(row, 1, caption)
            align = QComboBox()
            for value, label in (("left", "Left"), ("center", "Center"), ("right", "Right")):
                align.addItem(label, value)
            current = align.findData(field.get("align") or "left")
            align.setCurrentIndex(current if current >= 0 else 0)
            align.currentIndexChanged.connect(lambda _i, r=row: self._on_align(r))
            self.table.setCellWidget(row, 2, align)
            width = QTableWidgetItem(str(field.get("width") or ""))
            if not show_width:
                width.setFlags(width.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, width)
            text_item = QTableWidgetItem(str(field.get("text") or ""))
            fid = str(field.get("id") or "")
            if not (fid.startswith("static_") or fid in TEXT_FIELDS):
                text_item.setFlags(text_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, text_item)
        self.table.blockSignals(False)
        self._loading = False
        self._sync_canvas()

    def _on_check(self, row: int) -> None:
        if self._loading:
            return
        self._commit_row(row)
        self._sync_canvas()

    def _on_align(self, row: int) -> None:
        if self._loading:
            return
        self._commit_row(row)
        self._sync_canvas()

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        if self._loading:
            return
        self._commit_table()
        self._sync_canvas()

    def _commit_table(self) -> None:
        if self._loading or not self._layout:
            return
        fields = self._fields()
        for row in range(min(self.table.rowCount(), len(fields))):
            self._commit_row(row, fields)

    def _commit_row(self, row: int, fields: list[dict] | None = None) -> None:
        fields = fields if fields is not None else self._fields()
        if row >= len(fields):
            return
        field = fields[row]
        wrap = self.table.cellWidget(row, 0)
        if wrap:
            check = wrap.findChild(QCheckBox)
            if check:
                field["visible"] = check.isChecked()
        caption = self.table.item(row, 1)
        if caption:
            field["label"] = caption.text().strip() or field.get("label") or field.get("id")
        align = self.table.cellWidget(row, 2)
        if isinstance(align, QComboBox):
            field["align"] = align.currentData() or "left"
        width = self.table.item(row, 3)
        if width and self._band == "columns":
            try:
                field["width"] = max(4.0, float(width.text() or field.get("width") or 10))
            except ValueError:
                pass
        text = self.table.item(row, 4)
        fid = str(field.get("id") or "")
        if text and (fid.startswith("static_") or fid in TEXT_FIELDS):
            field["text"] = text.text()

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        fields = self._fields()
        target = row + delta
        if row < 0 or target < 0 or target >= len(fields):
            return
        self._commit_table()
        fields[row], fields[target] = fields[target], fields[row]
        self._fill_table()
        self.table.selectRow(target)
        self.canvas.select_field(self._band, str(self._fields()[target].get("id") or ""))

    def _add_text(self) -> None:
        self._commit_table()
        fields = self._fields()
        field_id = f"static_{self._band}_{len(fields) + 1}"
        fields.append(
            {
                "id": field_id,
                "band": self._band,
                "visible": True,
                "label": "Text",
                "align": "left",
                "text": "Type the printed line",
            }
        )
        self._fill_table()
        self.table.selectRow(self.table.rowCount() - 1)

    def _remove_text(self) -> None:
        row = self.table.currentRow()
        fields = self._fields()
        if row < 0 or row >= len(fields):
            return
        if not str(fields[row].get("id") or "").startswith("static_"):
            QMessageBox.information(self, "Bill templates", "Only extra text lines can be removed. Hide a standard field instead.")
            return
        self._commit_table()
        del fields[row]
        self._fill_table()

    def _add_page(self) -> None:
        name = self.custom_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Custom page", "Enter a name for the page.")
            return
        self._commit_table()
        pages = self._layout.setdefault("custom_pages", {})
        code = "CUSTOM_" + "".join(ch if ch.isalnum() else "_" for ch in name.upper())[:24]
        base = code
        suffix = 2
        while code in pages:
            code = f"{base}_{suffix}"
            suffix += 1
        pages[code] = {
            "name": name,
            "width_mm": float(self.custom_width.value()),
            "height_mm": float(self.custom_height.value()),
        }
        formats = self._layout.setdefault("formats", {})
        formats[code] = deepcopy(formats.get(self._format) or formats.get("A4") or {})
        page_meta = self._layout.setdefault("page", {})
        page_meta[code] = {"orientation": self.orientation.currentData() or "portrait"}
        self._fill_pages(select=code)
        self._format = code
        self._fill_table()
        self.custom_name.clear()

    def _remove_page(self) -> None:
        code = self.page_combo.currentData()
        if not code or not str(code).startswith("CUSTOM_"):
            QMessageBox.information(self, "Custom page", "Select a custom page to remove. Standard sizes stay.")
            return
        pages = self._layout.get("custom_pages") or {}
        pages.pop(code, None)
        (self._layout.get("formats") or {}).pop(code, None)
        (self._layout.get("page") or {}).pop(code, None)
        self._fill_pages(select="A4")
        self._format = self.page_combo.currentData() or "A4"
        self._fill_table()

    def _apply_orientation(self) -> None:
        page_meta = self._layout.setdefault("page", {})
        page_meta[self._format] = {"orientation": self.orientation.currentData() or "portrait"}

    def _paper_mm(self) -> tuple[float, float]:
        pages = (self._layout or {}).get("custom_pages") or {}
        page = pages.get(self._format) or {}
        if page:
            width = float(page.get("width_mm") or 210)
            height = float(page.get("height_mm") or 297)
        else:
            width, height = _PAGE_MM.get(str(self._format or "A4").upper(), _PAGE_MM["A4"])
        if (self.orientation.currentData() or "portrait") == "landscape":
            width, height = height, width
        return width, height

    def _on_orientation(self) -> None:
        if self._loading or not self._layout:
            return
        self._sync_canvas()

    def _on_table_selection(self) -> None:
        if self._loading:
            return
        row = self.table.currentRow()
        caption = self.table.item(row, 1) if row >= 0 else None
        if caption is None:
            return
        self.canvas.select_field(self._band, str(caption.data(Qt.ItemDataRole.UserRole) or ""))

    def _on_canvas_field(self, band: str, field_id: str) -> None:
        index = next((i for i, (name, _label) in enumerate(BANDS) if name == band), -1)
        if index < 0:
            return
        if self.tabs.currentIndex() != index:
            self.tabs.setCurrentIndex(index)
        for row in range(self.table.rowCount()):
            caption = self.table.item(row, 1)
            if caption and caption.data(Qt.ItemDataRole.UserRole) == field_id:
                self.table.selectRow(row)
                break

    def _on_canvas_geometry(self) -> None:
        return

    def _sync_canvas(self) -> None:
        if self._loading or not self._layout:
            return
        self._commit_table()
        self._apply_orientation()
        formats = self._layout.setdefault("formats", {})
        band_layout = formats.setdefault(self._format, {})
        bands = {band: band_layout.setdefault(band, []) for band, _label in BANDS}
        width, height = self._paper_mm()
        self.canvas.set_bill(
            bands,
            width,
            height,
            self.page_combo.currentText() or self._format,
            bill_title=self.document_combo.currentText() or "Bill",
        )

    def _refresh_preview(self) -> None:
        self._sync_canvas()

    def _save(self) -> None:
        self._commit_table()
        self._apply_orientation()
        paper = self._format
        try:
            saved = self.api.save_print_layout(
                self._code,
                {
                    "layout": self._layout,
                    "paper_size": paper,
                    "orientation": self.orientation.currentData() or "portrait",
                },
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Bill templates", str(exc))
            return
        self._layout = saved.get("layout") or self._layout
        QMessageBox.information(
            self,
            "Bill templates",
            "Template saved. New prints of this bill use this layout. Printer and margins stay in Print Master.",
        )
        self._refresh_preview()

    def _reset(self) -> None:
        if (
            QMessageBox.question(self, "Reset template", "Clear the custom design and use the built-in bill again?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            saved = self.api.reset_print_layout(self._code)
        except ApiError as exc:
            QMessageBox.warning(self, "Bill templates", str(exc))
            return
        self._layout = saved.get("layout") or {}
        self._fill_pages(select="A4")
        self._format = self.page_combo.currentData() or "A4"
        self._fill_table()
        self._refresh_preview()
