from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.print_local_config import (
    ensure_print_ini,
    get_report_printer,
    list_report_printers,
    print_ini_path,
    set_report_printer,
)
from app.ui.print_config_store import (
    ORIENTATION_OPTIONS,
    PAPER_SIZE_OPTIONS,
    PRINT_MODE_OPTIONS,
    invalidate_print_config_cache,
    load_print_configs,
)
from app.ui.print_utils import _populate_printer_combo
from app.ui.styles import BTN_PRIMARY, BTN_SECONDARY, FORM_FIELD_STYLE, LABEL, SUBTITLE, _apply_input_palette

_COMBO_WIDTH = 280
_SPIN_WIDTH = 110
_LABEL_WIDTH = 108
_PATHOLOGY_LAYOUT_DEFAULTS = {
    "font_size": 13,
    "row_padding": 6,
    "group_gap": 12,
    "sub_indent": 14,
}


class PrintMasterWidget(QWidget):
    HINT = (
        "Reports are loaded from the server — new print types added in the system appear here automatically. "
        "Printer is saved per PC in print.ini; other settings are shared for all users."
    )

    def __init__(self, api: ApiClient, on_navigate=None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._items: list[dict] = []
        self._local_printers: dict[str, str | None] = {}
        self._selected_id: str | None = None
        self._custom_size_label: QLabel | None = None
        self._build_ui()

    @staticmethod
    def _style_field(widget: QWidget) -> QWidget:
        _apply_input_palette(widget)
        widget.setStyleSheet(FORM_FIELD_STYLE)
        widget.setMinimumHeight(32)
        return widget

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL)
        label.setFixedWidth(_LABEL_WIDTH)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _combo(self) -> QComboBox:
        combo = self._style_field(QComboBox())
        combo.setFixedWidth(_COMBO_WIDTH)
        return combo

    def _margin_spin(self, value: float) -> QDoubleSpinBox:
        spin = self._style_field(QDoubleSpinBox())
        spin.setRange(0, 100)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setValue(value)
        spin.setFixedWidth(_SPIN_WIDTH)
        return spin

    def _layout_spin(self, value: int, minimum: int, maximum: int) -> QSpinBox:
        spin = self._style_field(QSpinBox())
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setFixedWidth(_SPIN_WIDTH)
        return spin

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        head_row = QHBoxLayout()
        heading = QLabel("Print Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        head_row.addWidget(heading)
        head_row.addStretch()
        design_btn = QPushButton("Design bill template")
        design_btn.setStyleSheet(BTN_SECONDARY)
        design_btn.clicked.connect(self._open_designer)
        head_row.addWidget(design_btn)
        outer.addLayout(head_row)

        hint = QLabel(self.HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet(SUBTITLE)
        outer.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(14)

        ini_box = QGroupBox("System printer file (this PC)")
        ini_layout = QVBoxLayout(ini_box)
        self._ini_path_label = QLabel(str(ensure_print_ini()))
        self._ini_path_label.setWordWrap(True)
        self._ini_path_label.setStyleSheet("font-size: 12px; color: #334155;")
        ini_layout.addWidget(self._ini_path_label)
        open_ini_btn = QPushButton("Open print.ini")
        open_ini_btn.setStyleSheet(BTN_SECONDARY)
        open_ini_btn.setFixedWidth(140)
        open_ini_btn.clicked.connect(self._open_ini_file)
        ini_btn_row = QHBoxLayout()
        ini_btn_row.addWidget(open_ini_btn)
        ini_btn_row.addStretch()
        ini_layout.addLayout(ini_btn_row)
        layout.addWidget(ini_box)

        settings_box = QGroupBox("Print Settings")
        settings_outer = QVBoxLayout(settings_box)
        settings_inner = QWidget()
        grid = QGridLayout(settings_inner)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(14)
        grid.setColumnMinimumWidth(0, _LABEL_WIDTH)
        grid.setColumnMinimumWidth(2, _LABEL_WIDTH)

        self.report_combo = self._combo()
        self.report_combo.currentIndexChanged.connect(self._on_report_selected)

        self.printer_combo = self._combo()
        _populate_printer_combo(self.printer_combo)
        self.printer_combo.insertItem(0, "(System default printer)", None)
        self.printer_combo.setCurrentIndex(0)

        self.paper_size = self._combo()
        for value, label in PAPER_SIZE_OPTIONS:
            self.paper_size.addItem(label, value)
        self.paper_size.currentIndexChanged.connect(self._on_paper_size_changed)

        self.custom_width = self._margin_spin(105)
        self.custom_width.setRange(10, 1000)
        self.custom_height = self._margin_spin(74)
        self.custom_height.setRange(10, 1000)

        custom_row = QWidget()
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(12)
        custom_layout.addWidget(QLabel("W"))
        custom_layout.addWidget(self.custom_width)
        custom_layout.addSpacing(8)
        custom_layout.addWidget(QLabel("H"))
        custom_layout.addWidget(self.custom_height)
        custom_layout.addStretch()
        self.custom_size_row = custom_row

        self.orientation = self._combo()
        for value, label in ORIENTATION_OPTIONS:
            self.orientation.addItem(label, value)

        self.print_mode = self._combo()
        for value, label in PRINT_MODE_OPTIONS:
            self.print_mode.addItem(label, value)

        self.margin_top = self._margin_spin(12)
        self.margin_right = self._margin_spin(12)
        self.margin_bottom = self._margin_spin(15)
        self.margin_left = self._margin_spin(12)

        self.copies = self._style_field(QSpinBox())
        self.copies.setRange(1, 20)
        self.copies.setValue(1)
        self.copies.setFixedWidth(80)

        row = 0
        grid.addWidget(self._field_label("Report"), row, 0)
        grid.addWidget(self.report_combo, row, 1, 1, 3)
        row += 1
        grid.addWidget(self._field_label("Printer"), row, 0)
        grid.addWidget(self.printer_combo, row, 1)
        grid.addWidget(self._field_label("Paper Size"), row, 2)
        grid.addWidget(self.paper_size, row, 3)
        row += 1
        grid.addWidget(self._field_label("Orientation"), row, 0)
        grid.addWidget(self.orientation, row, 1)
        grid.addWidget(self._field_label("Print Mode"), row, 2)
        grid.addWidget(self.print_mode, row, 3)
        row += 1
        self._custom_size_label = self._field_label("Custom Size")
        grid.addWidget(self._custom_size_label, row, 0)
        grid.addWidget(self.custom_size_row, row, 1, 1, 3)
        row += 1
        grid.addWidget(self._field_label("Margin Top"), row, 0)
        grid.addWidget(self.margin_top, row, 1)
        grid.addWidget(self._field_label("Margin Right"), row, 2)
        grid.addWidget(self.margin_right, row, 3)
        row += 1
        grid.addWidget(self._field_label("Margin Bottom"), row, 0)
        grid.addWidget(self.margin_bottom, row, 1)
        grid.addWidget(self._field_label("Margin Left"), row, 2)
        grid.addWidget(self.margin_left, row, 3)
        row += 1
        grid.addWidget(self._field_label("Copies"), row, 0)
        grid.addWidget(self.copies, row, 1)

        settings_outer.addWidget(settings_inner)
        layout.addWidget(settings_box)

        self.pathology_layout_box = QGroupBox("Pathology Report Layout")
        pathology_grid = QGridLayout(self.pathology_layout_box)
        pathology_grid.setContentsMargins(8, 12, 8, 8)
        pathology_grid.setHorizontalSpacing(20)
        pathology_grid.setVerticalSpacing(14)
        pathology_grid.setColumnMinimumWidth(0, _LABEL_WIDTH)
        pathology_grid.setColumnMinimumWidth(2, _LABEL_WIDTH)
        self.layout_font = self._layout_spin(_PATHOLOGY_LAYOUT_DEFAULTS["font_size"], 8, 18)
        self.layout_row_padding = self._layout_spin(_PATHOLOGY_LAYOUT_DEFAULTS["row_padding"], 0, 24)
        self.layout_group_gap = self._layout_spin(_PATHOLOGY_LAYOUT_DEFAULTS["group_gap"], 0, 40)
        self.layout_sub_indent = self._layout_spin(_PATHOLOGY_LAYOUT_DEFAULTS["sub_indent"], 0, 60)
        pathology_grid.addWidget(self._field_label("Font Size"), 0, 0)
        pathology_grid.addWidget(self.layout_font, 0, 1)
        pathology_grid.addWidget(self._field_label("Row Spacing"), 0, 2)
        pathology_grid.addWidget(self.layout_row_padding, 0, 3)
        pathology_grid.addWidget(self._field_label("Gap Before Group"), 1, 0)
        pathology_grid.addWidget(self.layout_group_gap, 1, 1)
        pathology_grid.addWidget(self._field_label("Sub-Test Indent"), 1, 2)
        pathology_grid.addWidget(self.layout_sub_indent, 1, 3)
        hint = QLabel(
            "Controls how the printed lab report groups a main service and its sub-tests. "
            "Increase Gap Before Group for a blank line before each bundle; increase Sub-Test Indent "
            "to push member tests further under the main service name."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(SUBTITLE)
        pathology_grid.addWidget(hint, 2, 0, 1, 4)
        self.pathology_layout_box.setVisible(False)
        layout.addWidget(self.pathology_layout_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(BTN_SECONDARY)
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self.refresh)
        refresh_printers_btn = QPushButton("Refresh Printers")
        refresh_printers_btn.setStyleSheet(BTN_SECONDARY)
        refresh_printers_btn.setFixedWidth(140)
        refresh_printers_btn.clicked.connect(self._refresh_printers)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(refresh_printers_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Report", "Printer", "Paper", "Orientation", "Mode", "Copies"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(220)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

        layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        self._on_paper_size_changed()

    def refresh(self) -> None:
        try:
            self._items = self.api.list_print_configs()
            codes = [item.get("code") for item in self._items if item.get("code")]
            ensure_print_ini(codes)
            self._ini_path_label.setText(str(print_ini_path()))
            load_print_configs(self.api, self._items)
            self._local_printers = list_report_printers(codes)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._load_table()
        self._load_report_combo()

    def _open_designer(self) -> None:
        if self._on_navigate:
            self._on_navigate("print_template_designer")

    def _open_ini_file(self) -> None:
        path = ensure_print_ini()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _refresh_printers(self) -> None:
        current = self.printer_combo.currentData()
        self.printer_combo.clear()
        _populate_printer_combo(self.printer_combo)
        self.printer_combo.insertItem(0, "(System default printer)", None)
        if current:
            idx = self.printer_combo.findData(current)
            self.printer_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.printer_combo.setCurrentIndex(0)

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            code = (item.get("code") or "").upper()
            printer = self._local_printers.get(code) or "Default"
            paper = item.get("paper_size") or "A4"
            if paper == "CUSTOM":
                paper = f"Custom {item.get('custom_width_mm')}x{item.get('custom_height_mm')}mm"
            self.table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(printer))
            self.table.setItem(row, 2, QTableWidgetItem(paper))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("orientation", "")))
            mode = "Direct" if item.get("print_mode") == "direct" else "Preview"
            self.table.setItem(row, 4, QTableWidgetItem(mode))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.get("copies", 1))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_report_combo(self) -> None:
        current = self.report_combo.currentData()
        self.report_combo.blockSignals(True)
        self.report_combo.clear()
        for item in self._items:
            label = item.get("name") or item.get("code") or "Report"
            self.report_combo.addItem(label, item.get("id"))
        self.report_combo.blockSignals(False)
        if not self._items:
            self._selected_id = None
            return
        if current:
            idx = self.report_combo.findData(current)
            if idx >= 0:
                self.report_combo.setCurrentIndex(idx)
                self._on_report_selected()
                return
        self.report_combo.setCurrentIndex(0)
        self._on_report_selected()

    def _on_table_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        idx = self.report_combo.findData(item_id)
        if idx >= 0:
            self.report_combo.setCurrentIndex(idx)

    def _on_report_selected(self) -> None:
        item_id = self.report_combo.currentData()
        self._selected_id = item_id
        item = next((row for row in self._items if row.get("id") == item_id), None)
        if not item:
            return
        code = (item.get("code") or "").upper()
        printer_name = get_report_printer(code)
        if printer_name:
            idx = self.printer_combo.findData(printer_name)
            if idx < 0:
                self.printer_combo.addItem(printer_name, printer_name)
                idx = self.printer_combo.findData(printer_name)
            self.printer_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.printer_combo.setCurrentIndex(0)

        paper = (item.get("paper_size") or "A4").upper()
        pidx = self.paper_size.findData(paper)
        self.paper_size.setCurrentIndex(pidx if pidx >= 0 else 0)
        self.custom_width.setValue(float(item.get("custom_width_mm") or 105))
        self.custom_height.setValue(float(item.get("custom_height_mm") or 74))

        orient = (item.get("orientation") or "portrait").lower()
        oidx = self.orientation.findData(orient)
        self.orientation.setCurrentIndex(oidx if oidx >= 0 else 0)

        mode = (item.get("print_mode") or "preview").lower()
        midx = self.print_mode.findData(mode)
        self.print_mode.setCurrentIndex(midx if midx >= 0 else 0)

        self.margin_top.setValue(float(item.get("margin_top_mm") or 12))
        self.margin_right.setValue(float(item.get("margin_right_mm") or 12))
        self.margin_bottom.setValue(float(item.get("margin_bottom_mm") or 15))
        self.margin_left.setValue(float(item.get("margin_left_mm") or 12))
        self.copies.setValue(int(item.get("copies") or 1))
        self._on_paper_size_changed()
        self._load_pathology_layout(item)

    def _load_pathology_layout(self, item: dict) -> None:
        code = (item.get("code") or "").upper()
        self.pathology_layout_box.setVisible(code == "PATHOLOGY_REPORT")
        if code != "PATHOLOGY_REPORT":
            return
        opts = item.get("layout_options") or {}
        self.layout_font.setValue(int(opts.get("font_size") or _PATHOLOGY_LAYOUT_DEFAULTS["font_size"]))
        self.layout_row_padding.setValue(
            int(opts.get("row_padding") or _PATHOLOGY_LAYOUT_DEFAULTS["row_padding"])
        )
        self.layout_group_gap.setValue(int(opts.get("group_gap") or _PATHOLOGY_LAYOUT_DEFAULTS["group_gap"]))
        self.layout_sub_indent.setValue(
            int(opts.get("sub_indent") or _PATHOLOGY_LAYOUT_DEFAULTS["sub_indent"])
        )

    def _pathology_layout_payload(self, code: str) -> dict | None:
        if code != "PATHOLOGY_REPORT":
            return None
        return {
            "font_size": self.layout_font.value(),
            "row_padding": self.layout_row_padding.value(),
            "group_gap": self.layout_group_gap.value(),
            "sub_indent": self.layout_sub_indent.value(),
        }

    def _on_paper_size_changed(self) -> None:
        is_custom = self.paper_size.currentData() == "CUSTOM"
        self.custom_size_row.setVisible(is_custom)
        if self._custom_size_label is not None:
            self._custom_size_label.setVisible(is_custom)

    def _save(self) -> None:
        if not self._selected_id:
            QMessageBox.warning(self, "Save", "Select a report first.")
            return
        paper = self.paper_size.currentData()
        item = next((row for row in self._items if row.get("id") == self._selected_id), None)
        code = (item.get("code") or "").upper() if item else ""
        payload = {
            "paper_size": paper,
            "custom_width_mm": self.custom_width.value() if paper == "CUSTOM" else None,
            "custom_height_mm": self.custom_height.value() if paper == "CUSTOM" else None,
            "orientation": self.orientation.currentData(),
            "print_mode": self.print_mode.currentData(),
            "margin_top_mm": self.margin_top.value(),
            "margin_right_mm": self.margin_right.value(),
            "margin_bottom_mm": self.margin_bottom.value(),
            "margin_left_mm": self.margin_left.value(),
            "copies": self.copies.value(),
        }
        layout_payload = self._pathology_layout_payload(code)
        if layout_payload is not None:
            payload["layout_options"] = layout_payload
        try:
            self.api.update_print_config(self._selected_id, payload)
            code = (item.get("code") or "").upper() if item else ""
            if code:
                set_report_printer(code, self.printer_combo.currentData())
            invalidate_print_config_cache()
            load_print_configs(self.api, self._items)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return
        QMessageBox.information(
            self,
            "Saved",
            f"Print settings saved.\n\nPrinter for this PC:\n{print_ini_path()}",
        )
        self.refresh()
