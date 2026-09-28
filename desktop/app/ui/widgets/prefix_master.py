from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

FORMAT_HELP = (
    "Patient ID pattern tokens: {PREFIX} (uses Prefix Creation → PATIENT), "
    "{SECTION}, {YYYYMMDD}, {YYMMDD}, {SEQ} or {SEQ:3}. "
    "Choose a Prefix + Date format if new IDs should start with the patient prefix letter. "
    "Only one format can be active (is_selected=true in database)."
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_prefixes_cache
from app.session import get_session


class PrefixMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._formats: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Prefix Creation")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        self.prefix_combo = QComboBox()
        self.prefix_combo.setEnabled(False)
        self.prefix_combo.currentIndexChanged.connect(self._on_prefix_selected)
        top.addWidget(QLabel("Select Prefix"))
        top.addWidget(self.prefix_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Prefix")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. PATIENT")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Patient Prefix")
        self.prefix_value = QLineEdit()
        self.prefix_value.setPlaceholderText("e.g. P")
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Prefix Value *", self.prefix_value)
        form.addRow("Sort Order", self.sort_order)
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

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Prefix", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

        format_box = QGroupBox("Patient ID Format")
        format_layout = QVBoxLayout(format_box)
        help_label = QLabel(FORMAT_HELP)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #475569;")
        format_layout.addWidget(help_label)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Active format"))
        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(320)
        format_row.addWidget(self.format_combo, stretch=1)
        self.apply_format_btn = QPushButton("Apply")
        self.apply_format_btn.clicked.connect(self._apply_format)
        format_row.addWidget(self.apply_format_btn)
        format_layout.addLayout(format_row)

        self.format_table = QTableWidget(0, 4)
        self.format_table.setHorizontalHeaderLabels(["Code", "Pattern", "Sample", "Active"])
        self.format_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.format_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.format_table.setMaximumHeight(140)
        format_layout.addWidget(self.format_table)
        layout.addWidget(format_box)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._items = list(cache.prefixes)
        else:
            try:
                self._items = self.api.list_prefixes()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._load_table()
        self._load_prefix_combo()
        self._load_formats()

    def _load_formats(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._formats = list(cache.patient_no_formats)
        else:
            try:
                self._formats = self.api.list_patient_no_formats()
            except ApiError as exc:
                self._formats = []
                self.format_combo.clear()
                self.format_table.setRowCount(0)
                self.format_combo.addItem(f"Not configured — {exc}", None)
                return

        current = None
        self.format_combo.clear()
        for item in self._formats:
            label = f"{item.get('code')} — {item.get('sample_output')} ({item.get('pattern')})"
            self.format_combo.addItem(label, item.get("id"))
            if item.get("is_selected"):
                current = item.get("id")
        if current:
            idx = self.format_combo.findData(current)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)

        self.format_table.setRowCount(len(self._formats))
        for row, item in enumerate(self._formats):
            self.format_table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.format_table.setItem(row, 1, QTableWidgetItem(item.get("pattern", "")))
            self.format_table.setItem(row, 2, QTableWidgetItem(item.get("sample_output", "")))
            self.format_table.setItem(
                row,
                3,
                QTableWidgetItem("Yes" if item.get("is_selected") else "No"),
            )

    def _apply_format(self) -> None:
        format_id = self.format_combo.currentData()
        if not format_id:
            QMessageBox.warning(
                self,
                "Patient ID Format",
                "No formats in database. Run scripts/patient_id_format.sql or: alembic upgrade head",
            )
            return
        try:
            self.api.update_patient_no_format(format_id, {"is_selected": True})
            QMessageBox.information(self, "Success", "Patient ID format updated.")
            self._load_formats()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("prefix_value", "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_prefix_combo(self) -> None:
        current = self.prefix_combo.currentData()
        self.prefix_combo.clear()
        self.prefix_combo.addItem("— Select —", None)
        for item in self._items:
            self.prefix_combo.addItem(
                f"{item.get('code')} — {item.get('name')} ({item.get('prefix_value')})",
                item.get("id"),
            )
        if current:
            idx = self.prefix_combo.findData(current)
            if idx >= 0:
                self.prefix_combo.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.prefix_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        self.name.setEnabled(enabled)
        self.prefix_value.setEnabled(enabled)
        self.sort_order.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_prefix_selected(self) -> None:
        prefix_id = self.prefix_combo.currentData()
        if prefix_id:
            self._load_item(prefix_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        prefix_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if not prefix_id:
            return
        if self.mode_combo.currentText() == self.MODE_CREATE:
            self.mode_combo.setCurrentText(self.MODE_MODIFY)
        idx = self.prefix_combo.findData(prefix_id)
        if idx >= 0:
            self.prefix_combo.setCurrentIndex(idx)

    def _load_item(self, prefix_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == prefix_id), None)
        if not item:
            try:
                item = self.api.get_prefix(prefix_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = prefix_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.prefix_value.setText(item.get("prefix_value", ""))
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.prefix_value.clear()
        self.sort_order.setValue(0)
        self.prefix_combo.setCurrentIndex(0)
        self.table.clearSelection()

    @staticmethod
    def _apply_prefix_to_cache(prefix: dict) -> None:
        cache = get_session().cache
        items = list(cache.prefixes)
        prefix_id = prefix.get("id")
        replaced = False
        for index, item in enumerate(items):
            if item.get("id") == prefix_id:
                items[index] = prefix
                replaced = True
                break
        if not replaced:
            items.append(prefix)
        cache.prefixes = items

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            prefix_id = self.prefix_combo.currentData() or self._selected_id
            if not prefix_id:
                QMessageBox.warning(self, "Validation", "Select a prefix to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this prefix?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_prefix(prefix_id)
                QMessageBox.information(self, "Success", "Prefix deactivated.")
                self._clear_form()
                refresh_prefixes_cache(self.api)
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        code = self.code.text().strip()
        name = self.name.text().strip()
        prefix_value = self.prefix_value.text().strip()
        if not code or not name or not prefix_value:
            QMessageBox.warning(self, "Validation", "Code, name, and prefix value are required.")
            return

        payload = {
            "code": code,
            "name": name,
            "prefix_value": prefix_value,
            "sort_order": self.sort_order.value(),
        }
        try:
            if mode == self.MODE_CREATE:
                created = self.api.create_prefix(payload)
                self._apply_prefix_to_cache(created)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Prefix created: {created.get('code')} = {created.get('prefix_value')}.",
                )
                self._clear_form()
            else:
                prefix_id = self.prefix_combo.currentData() or self._selected_id
                if not prefix_id:
                    QMessageBox.warning(self, "Validation", "Select a prefix to modify.")
                    return
                updated = self.api.update_prefix(
                    prefix_id,
                    {
                        "name": name,
                        "prefix_value": prefix_value,
                        "sort_order": self.sort_order.value(),
                    },
                )
                QMessageBox.information(
                    self,
                    "Success",
                    f"Prefix updated: {updated.get('code')} = {updated.get('prefix_value')}.",
                )
                self._apply_prefix_to_cache(updated)
            refresh_prefixes_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
