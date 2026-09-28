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


class PharmacySupplierMasterWidget(QWidget):
    MODE_CREATE, MODE_MODIFY, MODE_DELETE = "Create", "Modify", "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Supplier Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

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

        form_box = QGroupBox("Supplier")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.contact_person = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QLineEdit()
        self.gst_number = QLineEdit()
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Contact Person", self.contact_person)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        form.addRow("GST Number", self.gst_number)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(QPushButton("Clear", clicked=self._clear_form))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Phone", "GST"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._items = self.api.list_pharmacy_suppliers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.table.setRowCount(len(self._items))
        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("phone") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("gst_number") or ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.item_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _on_mode_changed(self, mode: str) -> None:
        is_create, is_delete = mode == self.MODE_CREATE, mode == self.MODE_DELETE
        self.item_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        for widget in (
            self.name,
            self.contact_person,
            self.phone,
            self.email,
            self.address,
            self.gst_number,
            self.sort_order,
        ):
            widget.setEnabled(not is_delete)
        if is_create:
            self._clear_form()

    def _on_item_selected(self) -> None:
        if self.item_combo.currentData():
            self._load_item(self.item_combo.currentData())

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if items and self.mode_combo.currentText() != self.MODE_CREATE:
            idx = self.item_combo.findData(self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole))
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def _load_item(self, item_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == item_id), None)
        if not item:
            return
        self._selected_id = item_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.contact_person.setText(item.get("contact_person") or "")
        self.phone.setText(item.get("phone") or "")
        self.email.setText(item.get("email") or "")
        self.address.setText(item.get("address") or "")
        self.gst_number.setText(item.get("gst_number") or "")
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.contact_person.clear()
        self.phone.clear()
        self.email.clear()
        self.address.clear()
        self.gst_number.clear()
        self.sort_order.setValue(0)
        self.item_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _payload(self) -> dict:
        return {
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "contact_person": self.contact_person.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "email": self.email.text().strip() or None,
            "address": self.address.text().strip() or None,
            "gst_number": self.gst_number.text().strip() or None,
            "sort_order": self.sort_order.value(),
        }

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            item_id = self.item_combo.currentData() or self._selected_id
            if not item_id:
                QMessageBox.warning(self, "Validation", "Select a supplier.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate supplier?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_pharmacy_supplier(item_id)
                self._clear_form()
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return
        payload = self._payload()
        if not payload["code"] or not payload["name"]:
            QMessageBox.warning(self, "Validation", "Code and name required.")
            return
        try:
            if mode == self.MODE_CREATE:
                self.api.create_pharmacy_supplier(payload)
            else:
                item_id = self.item_combo.currentData() or self._selected_id
                if not item_id:
                    QMessageBox.warning(self, "Validation", "Select a supplier.")
                    return
                update_payload = {k: v for k, v in payload.items() if k != "code"}
                self.api.update_pharmacy_supplier(item_id, update_payload)
            self._clear_form()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
