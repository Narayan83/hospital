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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_billing_packages_cache
from app.session import get_session


class PackageMasterWidget(QWidget):
    MODE_CREATE, MODE_MODIFY, MODE_DELETE = "Create", "Modify", "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Package Creation Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)
        hint = QLabel(
            "Define procedure packages (e.g. Normal Delivery ₹50,000). "
            "Assign services in 'Assign Services To Package'."
        )
        hint.setStyleSheet("color: #475569; margin-bottom: 8px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        self.item_combo = QComboBox()
        self.item_combo.setEnabled(False)
        self.item_combo.currentIndexChanged.connect(self._on_item_selected)
        top.addWidget(QLabel("Select"))
        top.addWidget(self.item_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Package")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.package_total = QLineEdit()
        self.package_total.setPlaceholderText("Optional fixed package amount")
        self.description = QTextEdit()
        self.description.setMaximumHeight(70)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Package Total", self.package_total)
        form.addRow("Description", self.description)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(QPushButton("Clear", clicked=self._clear_form))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Total", "Services", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._items = list(cache.billing_packages)
        else:
            try:
                self._items = self.api.list_billing_packages()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self.table.setRowCount(len(self._items))
        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            total = item.get("package_total")
            self.table.setItem(row, 2, QTableWidgetItem("" if total is None else str(total)))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("item_count", 0))))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.item_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _on_mode_changed(self, mode: str) -> None:
        is_create, is_delete = mode == self.MODE_CREATE, mode == self.MODE_DELETE
        self.item_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        for widget in (self.name, self.package_total, self.description, self.sort_order):
            widget.setEnabled(not is_delete)
        if is_create:
            self._clear_form()

    def _on_item_selected(self) -> None:
        if self.item_combo.currentData():
            self._load_item(self.item_combo.currentData())

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if items and self.mode_combo.currentText() != self.MODE_CREATE:
            item_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            idx = self.item_combo.findData(item_id)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def _load_item(self, item_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == item_id), None)
        if not item:
            try:
                item = self.api.get_billing_package(item_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = item_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        total = item.get("package_total")
        self.package_total.setText("" if total is None else str(total))
        self.description.setPlainText(item.get("description") or "")
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.package_total.clear()
        self.description.clear()
        self.sort_order.setValue(0)

    def _parse_total(self) -> str | None:
        text = self.package_total.text().strip()
        if not text:
            return None
        return text

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        try:
            if mode == self.MODE_DELETE:
                if not self._selected_id:
                    QMessageBox.warning(self, "Validation", "Select a package to delete.")
                    return
                self.api.delete_billing_package(self._selected_id)
                QMessageBox.information(self, "Deleted", "Package deleted.")
            elif mode == self.MODE_CREATE:
                if not self.code.text().strip() or not self.name.text().strip():
                    QMessageBox.warning(self, "Validation", "Code and name are required.")
                    return
                payload = {
                    "code": self.code.text().strip(),
                    "name": self.name.text().strip(),
                    "description": self.description.toPlainText().strip() or None,
                    "sort_order": self.sort_order.value(),
                }
                total = self._parse_total()
                if total is not None:
                    payload["package_total"] = total
                self.api.create_billing_package(payload)
                QMessageBox.information(self, "Saved", "Package created.")
            else:
                if not self._selected_id:
                    QMessageBox.warning(self, "Validation", "Select a package to modify.")
                    return
                payload = {
                    "name": self.name.text().strip(),
                    "description": self.description.toPlainText().strip() or None,
                    "sort_order": self.sort_order.value(),
                }
                total = self._parse_total()
                payload["package_total"] = total
                self.api.update_billing_package(self._selected_id, payload)
                QMessageBox.information(self, "Saved", "Package updated.")
            refresh_billing_packages_cache(self.api)
            self.refresh()
            if mode == self.MODE_CREATE:
                self._clear_form()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
