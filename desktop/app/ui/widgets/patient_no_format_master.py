from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


PATTERN_HELP = (
    "Tokens: {PREFIX} or {P}, {SECTION} or {S}, {YYYY}, {YY}, {MM}, {DD}, "
    "{YYYYMMDD}, {YYMMDD}, {SEQ} or {SEQ:3}. Daily sequence resets when date tokens are used."
)


class PatientNoFormatMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Patient ID Format")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        help_label = QLabel(PATTERN_HELP)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #475569; margin-bottom: 8px;")
        layout.addWidget(help_label)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        self.format_combo = QComboBox()
        self.format_combo.setEnabled(False)
        self.format_combo.currentIndexChanged.connect(self._on_format_selected)
        top.addWidget(QLabel("Select Format"))
        top.addWidget(self.format_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Format")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. PREFIX_DAILY")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Prefix + Full Date + Daily Seq")
        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText("e.g. {PREFIX}{YYYYMMDD}{SEQ:3}")
        self.sample_output = QLineEdit()
        self.sample_output.setPlaceholderText("e.g. P20260619001")
        self.seq_pad_width = QSpinBox()
        self.seq_pad_width.setRange(0, 10)
        self.seq_pad_width.setValue(3)
        self.is_selected = QCheckBox("Use this format for new patients")
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Pattern *", self.pattern)
        form.addRow("Sample Output *", self.sample_output)
        form.addRow("Default Seq Width", self.seq_pad_width)
        form.addRow("", self.is_selected)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Pattern", "Sample", "Selected"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._items = list(cache.patient_no_formats)
        else:
            try:
                self._items = self.api.list_patient_no_formats()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._load_table()
        self._load_format_combo()

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("pattern", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("sample_output", "")))
            self.table.setItem(
                row,
                4,
                QTableWidgetItem("Yes" if item.get("is_selected") else "No"),
            )
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_format_combo(self) -> None:
        current = self.format_combo.currentData()
        self.format_combo.clear()
        self.format_combo.addItem("— Select —", None)
        for item in self._items:
            label = f"{item.get('code')} — {item.get('name')}"
            if item.get("is_selected"):
                label += " (active)"
            self.format_combo.addItem(label, item.get("id"))
        if current:
            idx = self.format_combo.findData(current)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.format_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        self.name.setEnabled(enabled)
        self.pattern.setEnabled(enabled)
        self.sample_output.setEnabled(enabled)
        self.seq_pad_width.setEnabled(enabled)
        self.is_selected.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_format_selected(self) -> None:
        format_id = self.format_combo.currentData()
        if format_id:
            self._load_item(format_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        format_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and format_id:
            idx = self.format_combo.findData(format_id)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)

    def _load_item(self, format_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == format_id), None)
        if not item:
            try:
                item = self.api.get_patient_no_format(format_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = format_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.pattern.setText(item.get("pattern", ""))
        self.sample_output.setText(item.get("sample_output", ""))
        self.seq_pad_width.setValue(int(item.get("seq_pad_width") or 0))
        self.is_selected.setChecked(bool(item.get("is_selected")))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.pattern.clear()
        self.sample_output.clear()
        self.seq_pad_width.setValue(3)
        self.is_selected.setChecked(False)
        self.format_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            format_id = self.format_combo.currentData() or self._selected_id
            if not format_id:
                QMessageBox.warning(self, "Validation", "Select a format to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this format?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_patient_no_format(format_id)
                QMessageBox.information(self, "Success", "Format deactivated.")
                self._clear_form()
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        code = self.code.text().strip()
        name = self.name.text().strip()
        pattern = self.pattern.text().strip()
        sample_output = self.sample_output.text().strip()
        if not code or not name or not pattern or not sample_output:
            QMessageBox.warning(self, "Validation", "Code, name, pattern, and sample output are required.")
            return

        payload = {
            "name": name,
            "pattern": pattern,
            "sample_output": sample_output,
            "seq_pad_width": self.seq_pad_width.value(),
            "is_selected": self.is_selected.isChecked(),
        }
        try:
            if mode == self.MODE_CREATE:
                self.api.create_patient_no_format(
                    {
                        "code": code,
                        **payload,
                        "sort_order": 0,
                    }
                )
                QMessageBox.information(self, "Success", "Format created.")
                self._clear_form()
            else:
                format_id = self.format_combo.currentData() or self._selected_id
                if not format_id:
                    QMessageBox.warning(self, "Validation", "Select a format to modify.")
                    return
                self.api.update_patient_no_format(format_id, payload)
                QMessageBox.information(self, "Success", "Format updated.")
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
