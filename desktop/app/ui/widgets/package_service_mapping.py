from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_billing_packages_cache
from app.session import get_session


class PackageServiceMappingWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._package_id: str | None = None
        self._package_detail: dict | None = None
        self._services: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Assign Services To Package")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)
        hint = QLabel("Select a package and add services that should appear when the package is chosen in billing.")
        hint.setStyleSheet("color: #475569; margin-bottom: 8px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        top.addWidget(QLabel("Package *"))
        self.package_combo = QComboBox()
        self.package_combo.setMinimumWidth(320)
        self.package_combo.currentIndexChanged.connect(self._on_package_changed)
        top.addWidget(self.package_combo, stretch=1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        self.package_info = QLabel("")
        self.package_info.setStyleSheet("color: #1d4ed8; font-weight: 600;")
        layout.addWidget(self.package_info)

        add_box = QGroupBox("Add Service")
        add_form = QFormLayout(add_box)
        self.service_combo = QComboBox()
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 999)
        self.quantity.setValue(1)
        self.rate_override = QComboBox()
        self.rate_override.setEditable(True)
        self.rate_override.addItem("Use service rate", None)
        add_form.addRow("Service *", self.service_combo)
        add_form.addRow("Quantity", self.quantity)
        add_form.addRow("Rate Override", self.rate_override)
        layout.addWidget(add_box)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add to Package")
        add_btn.clicked.connect(self._add_service)
        save_btn = QPushButton("Save All Items")
        save_btn.clicked.connect(self._save_all)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Service", "Qty", "Rate", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self._pending_items: list[dict] = []

    def refresh(self) -> None:
        cache = get_session().cache
        packages = list(cache.billing_packages) if cache.loaded else []
        services = list(cache.patient_services) if cache.loaded else []
        if not packages or not services:
            try:
                if not packages:
                    packages = self.api.list_billing_packages()
                if not services:
                    services = self.api.list_patient_services()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return

        self._services = services
        current = self.package_combo.currentData()
        self.package_combo.clear()
        self.package_combo.addItem("— Select Package —", None)
        for pkg in packages:
            label = f"{pkg.get('code')} — {pkg.get('name')} ({pkg.get('item_count', 0)} services)"
            self.package_combo.addItem(label, pkg.get("id"))

        self.service_combo.clear()
        self.service_combo.addItem("— Select Service —", None)
        for svc in services:
            self.service_combo.addItem(
                f"{svc.get('code')} — {svc.get('name')} (₹{svc.get('rate')})",
                svc.get("id"),
            )

        if current:
            idx = self.package_combo.findData(current)
            if idx >= 0:
                self.package_combo.setCurrentIndex(idx)
        elif self.package_combo.count() > 1:
            self.package_combo.setCurrentIndex(1)

    def _on_package_changed(self) -> None:
        self._package_id = self.package_combo.currentData()
        if not self._package_id:
            self._package_detail = None
            self._pending_items = []
            self.package_info.setText("")
            self.table.setRowCount(0)
            return
        try:
            self._package_detail = self.api.get_billing_package(self._package_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        total = self._package_detail.get("package_total")
        total_text = f" | Package total: ₹{total}" if total is not None else ""
        self.package_info.setText(
            f"{self._package_detail.get('code')} — {self._package_detail.get('name')}{total_text}"
        )
        self._pending_items = [
            {
                "service_id": item.get("service_id"),
                "quantity": int(item.get("quantity") or 1),
                "rate_override": item.get("rate_override"),
                "sort_order": int(item.get("sort_order") or 0),
                "service_code": item.get("service_code"),
                "service_name": item.get("service_name"),
                "service_rate": item.get("service_rate"),
                "item_id": item.get("id"),
            }
            for item in self._package_detail.get("items", [])
        ]
        self._load_table()

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._pending_items))
        for row, item in enumerate(self._pending_items):
            rate = item.get("rate_override")
            if rate is None:
                rate = item.get("service_rate")
            self.table.setItem(row, 0, QTableWidgetItem(item.get("service_code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("service_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.get("quantity", 1))))
            self.table.setItem(row, 3, QTableWidgetItem("" if rate is None else str(rate)))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("sort_order", row))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, row)

    def _add_service(self) -> None:
        service_id = self.service_combo.currentData()
        if not self._package_id:
            QMessageBox.warning(self, "Validation", "Select a package first.")
            return
        if not service_id:
            QMessageBox.warning(self, "Validation", "Select a service to add.")
            return
        if any(item.get("service_id") == service_id for item in self._pending_items):
            QMessageBox.warning(self, "Validation", "Service already in package.")
            return

        svc = next((s for s in self._services if s.get("id") == service_id), None)
        rate_override = self.rate_override.currentData()
        if rate_override is None and self.rate_override.currentText().strip():
            rate_override = self.rate_override.currentText().strip()

        self._pending_items.append({
            "service_id": service_id,
            "quantity": self.quantity.value(),
            "rate_override": rate_override,
            "sort_order": len(self._pending_items),
            "service_code": svc.get("code") if svc else "",
            "service_name": svc.get("name") if svc else "",
            "service_rate": svc.get("rate") if svc else None,
            "item_id": None,
        })
        self._load_table()
        self.quantity.setValue(1)
        self.rate_override.setCurrentIndex(0)

    def _remove_selected(self) -> None:
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "Remove", "Select row(s) to remove.")
            return
        for row in rows:
            if 0 <= row < len(self._pending_items):
                self._pending_items.pop(row)
        for index, item in enumerate(self._pending_items):
            item["sort_order"] = index
        self._load_table()

    def _save_all(self) -> None:
        if not self._package_id:
            QMessageBox.warning(self, "Validation", "Select a package first.")
            return
        payload = {
            "items": [
                {
                    "service_id": item["service_id"],
                    "quantity": item["quantity"],
                    "rate_override": item.get("rate_override"),
                    "sort_order": item.get("sort_order", index),
                }
                for index, item in enumerate(self._pending_items)
            ]
        }
        try:
            self.api.replace_billing_package_items(self._package_id, payload)
            refresh_billing_packages_cache(self.api)
            QMessageBox.information(self, "Saved", "Package services saved.")
            self._on_package_changed()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
