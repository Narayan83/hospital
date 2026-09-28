from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
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

SCHEDULE_OPTIONS = ["", "H", "H1", "X", "OTC"]


class PharmacyItemMasterWidget(QWidget):
    MODE_CREATE, MODE_MODIFY, MODE_DELETE = "Create", "Modify", "Delete"

    def __init__(self, api: ApiClient, item_type: str, title: str):
        super().__init__()
        self.api = api
        self.item_type = item_type.upper()
        self.title = title
        self._items: list[dict] = []
        self._manufacturers: list[dict] = []
        self._categories: list[dict] = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel(self.title)
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

        form_box = QGroupBox(self.title)
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.generic_name = QLineEdit()
        self.unit = QLineEdit()
        self.mrp = QDoubleSpinBox()
        self.mrp.setRange(0, 999999)
        self.mrp.setDecimals(2)
        self.purchase_rate = QDoubleSpinBox()
        self.purchase_rate.setRange(0, 999999)
        self.purchase_rate.setDecimals(2)
        self.sale_rate = QDoubleSpinBox()
        self.sale_rate.setRange(0, 999999)
        self.sale_rate.setDecimals(2)
        self.manufacturer = QComboBox()
        self.category = QComboBox()
        self.schedule = QComboBox()
        self.schedule.addItems(SCHEDULE_OPTIONS)
        self.reorder_level = QSpinBox()
        self.reorder_level.setRange(0, 99999)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Generic Name", self.generic_name)
        form.addRow("Unit", self.unit)
        form.addRow("MRP", self.mrp)
        form.addRow("Purchase Rate", self.purchase_rate)
        form.addRow("Sale Rate", self.sale_rate)
        form.addRow("Manufacturer", self.manufacturer)
        form.addRow("Drug Category", self.category)
        form.addRow("Schedule", self.schedule)
        form.addRow("Reorder Level", self.reorder_level)
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
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Unit", "Sale Rate", "Schedule"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._items = self.api.list_pharmacy_items(self.item_type)
            if self.item_type == "MD":
                self._manufacturers = self.api.list_pharmacy_code_masters("MF")
                self._categories = self.api.list_pharmacy_code_masters("DC")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._reload_lookups()
        self.table.setRowCount(len(self._items))
        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("unit") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("sale_rate") or "")))
            self.table.setItem(row, 4, QTableWidgetItem(item.get("schedule") or ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.item_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _reload_lookups(self) -> None:
        for combo, items in ((self.manufacturer, self._manufacturers), (self.category, self._categories)):
            combo.clear()
            combo.addItem("— None —", None)
            for item in items:
                combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _on_mode_changed(self, mode: str) -> None:
        is_create, is_delete = mode == self.MODE_CREATE, mode == self.MODE_DELETE
        self.item_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        for widget in (
            self.name,
            self.generic_name,
            self.unit,
            self.mrp,
            self.purchase_rate,
            self.sale_rate,
            self.manufacturer,
            self.category,
            self.schedule,
            self.reorder_level,
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
        self.generic_name.setText(item.get("generic_name") or "")
        self.unit.setText(item.get("unit") or "")
        self.mrp.setValue(float(item.get("mrp") or 0))
        self.purchase_rate.setValue(float(item.get("purchase_rate") or 0))
        self.sale_rate.setValue(float(item.get("sale_rate") or 0))
        self._set_combo(self.manufacturer, item.get("manufacturer_id"))
        self._set_combo(self.category, item.get("category_id"))
        schedule = item.get("schedule") or ""
        idx = self.schedule.findText(schedule)
        self.schedule.setCurrentIndex(idx if idx >= 0 else 0)
        self.reorder_level.setValue(int(item.get("reorder_level") or 0))
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    @staticmethod
    def _set_combo(combo: QComboBox, value: str | None) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.generic_name.clear()
        self.unit.clear()
        self.mrp.setValue(0)
        self.purchase_rate.setValue(0)
        self.sale_rate.setValue(0)
        self.manufacturer.setCurrentIndex(0)
        self.category.setCurrentIndex(0)
        self.schedule.setCurrentIndex(0)
        self.reorder_level.setValue(0)
        self.sort_order.setValue(0)
        self.item_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _payload(self) -> dict:
        return {
            "item_type": self.item_type,
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "generic_name": self.generic_name.text().strip() or None,
            "unit": self.unit.text().strip() or None,
            "mrp": self.mrp.value() or None,
            "purchase_rate": self.purchase_rate.value() or None,
            "sale_rate": self.sale_rate.value() or None,
            "manufacturer_id": self.manufacturer.currentData(),
            "category_id": self.category.currentData(),
            "schedule": self.schedule.currentText() or None,
            "reorder_level": self.reorder_level.value() or None,
            "sort_order": self.sort_order.value(),
        }

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            item_id = self.item_combo.currentData() or self._selected_id
            if not item_id:
                QMessageBox.warning(self, "Validation", "Select a record.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate record?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_pharmacy_item(item_id)
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
                self.api.create_pharmacy_item(payload)
            else:
                item_id = self.item_combo.currentData() or self._selected_id
                if not item_id:
                    QMessageBox.warning(self, "Validation", "Select a record.")
                    return
                update_payload = {k: v for k, v in payload.items() if k not in ("item_type", "code")}
                self.api.update_pharmacy_item(item_id, update_payload)
            self._clear_form()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
