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

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_billing_types_cache
from app.session import get_session


class BillingTypeMasterWidget(QWidget):
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

        heading = QLabel("Bill Types Creation")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)

        self.type_combo = QComboBox()
        self.type_combo.setEnabled(False)
        self.type_combo.currentIndexChanged.connect(self._on_type_selected)
        top.addWidget(QLabel("Select Type"))
        top.addWidget(self.type_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Billing Type")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. OPD")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Out Patient")
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
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

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._items = list(cache.billing_types)
        else:
            try:
                self._items = self.api.list_billing_types()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._load_table()
        self._load_type_combo()

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_type_combo(self) -> None:
        current = self.type_combo.currentData()
        self.type_combo.clear()
        self.type_combo.addItem("— Select —", None)
        for item in self._items:
            self.type_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))
        if current:
            idx = self.type_combo.findData(current)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.type_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        self.name.setEnabled(enabled)
        self.sort_order.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_type_selected(self) -> None:
        billing_type_id = self.type_combo.currentData()
        if billing_type_id:
            self._load_item(billing_type_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        billing_type_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and billing_type_id:
            idx = self.type_combo.findData(billing_type_id)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

    def _load_item(self, billing_type_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == billing_type_id), None)
        if not item:
            try:
                item = self.api.get_billing_type(billing_type_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = billing_type_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.sort_order.setValue(0)
        self.type_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            billing_type_id = self.type_combo.currentData() or self._selected_id
            if not billing_type_id:
                QMessageBox.warning(self, "Validation", "Select a billing type to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this billing type?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_billing_type(billing_type_id)
                QMessageBox.information(self, "Success", "Billing type deactivated.")
                self._clear_form()
                refresh_billing_types_cache(self.api)
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        code = self.code.text().strip()
        name = self.name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validation", "Code and name are required.")
            return

        payload = {
            "code": code,
            "name": name,
            "sort_order": self.sort_order.value(),
        }
        try:
            if mode == self.MODE_CREATE:
                self.api.create_billing_type(payload)
                QMessageBox.information(self, "Success", "Billing type created.")
                self._clear_form()
            else:
                billing_type_id = self.type_combo.currentData() or self._selected_id
                if not billing_type_id:
                    QMessageBox.warning(self, "Validation", "Select a billing type to modify.")
                    return
                self.api.update_billing_type(
                    billing_type_id,
                    {"name": name, "sort_order": self.sort_order.value()},
                )
                QMessageBox.information(self, "Success", "Billing type updated.")
            refresh_billing_types_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
