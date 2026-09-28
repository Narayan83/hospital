from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import flatten_menus, get_session


class SingleServiceOpdSetupWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._options: list[dict] = []
        self._services: list[dict] = []
        self._selected_id: str | None = None
        self._prefix_touched = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Single Service OPD Setup")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Each option becomes a menu under Transactions → Billing. "
            "The counter selects the doctor, the patient, and the rate, then saves. "
            "Bill numbers use a separate series and restart each financial year (1 April). "
            "Collections are included in the doctor-wise and user-wise cash reports."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Billing Option")
        form = QFormLayout(form_box)
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Consultation, Dressing, ECG")
        self.name.editingFinished.connect(self._fill_prefix)
        self.service = QComboBox()
        self.service.currentIndexChanged.connect(self._on_service_changed)
        self.use_patient_id = QCheckBox("Require Patient ID")
        self.use_patient_id.setChecked(True)
        self.use_patient_id.setToolTip(
            "Checked: counter must pick a registered patient. "
            "Unchecked: counter types the patient name only."
        )
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 9999999)
        self.rate.setDecimals(2)
        self.rate.setToolTip("Default rate. The counter can change it while billing.")
        self.prefix = QLineEdit()
        self.prefix.setMaxLength(10)
        self.prefix.setPlaceholderText("Auto from the option name")
        self.prefix.textEdited.connect(self._mark_prefix_touched)
        self.active = QCheckBox("Active")
        self.active.setChecked(True)
        form.addRow("Option Name *", self.name)
        form.addRow("Service *", self.service)
        form.addRow("Patient", self.use_patient_id)
        form.addRow("Default Rate", self.rate)
        form.addRow("Bill Prefix", self.prefix)
        form.addRow("", self.active)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Option", "Service", "Patient", "Rate", "Prefix", "Active"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._options = self.api.list_single_service_opd_options()
            services = self.api.list_patient_services()
            self._services = services if isinstance(services, list) else services.get("items", [])
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._load_service_combo()
        self._load_table()

    def _load_service_combo(self) -> None:
        current = self.service.currentData()
        self.service.blockSignals(True)
        self.service.clear()
        self.service.addItem("— Select service —", None)
        for item in self._services:
            if item.get("is_active") is False:
                continue
            label = f"{item.get('code', '')} — {item.get('name', '')}"
            self.service.addItem(label, item.get("id"))
        if current:
            idx = self.service.findData(current)
            if idx >= 0:
                self.service.setCurrentIndex(idx)
        self.service.blockSignals(False)

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._options))
        for row, item in enumerate(self._options):
            values = [
                item.get("name", ""),
                item.get("service_name") or "—",
                "Patient ID" if item.get("use_patient_id") else "Name only",
                f"{float(item.get('default_rate') or 0):.2f}",
                item.get("bill_prefix") or "",
                "Yes" if item.get("is_active") else "No",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.get("id"))
                self.table.setItem(row, col, cell)

    def _on_service_changed(self) -> None:
        if self._selected_id:
            return
        service_id = self.service.currentData()
        service = next((item for item in self._services if item.get("id") == service_id), None)
        if service is not None:
            self.rate.setValue(float(service.get("rate") or 0))

    def _mark_prefix_touched(self) -> None:
        self._prefix_touched = True

    def _fill_prefix(self) -> None:
        if self._prefix_touched and self.prefix.text().strip():
            return
        words = [part for part in self.name.text().upper().replace("-", " ").split() if part.isalnum()]
        if not words:
            return
        if len(words) == 1:
            suggestion = words[0][:6]
        else:
            suggestion = "".join(word[0] for word in words)[:6]
        self.prefix.setText(suggestion)

    def _on_table_select(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._options):
            return
        item = self._options[row]
        self._selected_id = item.get("id")
        self.name.setText(item.get("name", ""))
        idx = self.service.findData(item.get("service_id"))
        self.service.setCurrentIndex(idx if idx >= 0 else 0)
        self.use_patient_id.setChecked(bool(item.get("use_patient_id")))
        self.rate.setValue(float(item.get("default_rate") or 0))
        self.prefix.setText(item.get("bill_prefix") or "")
        self._prefix_touched = True
        self.active.setChecked(bool(item.get("is_active", True)))

    def _clear_form(self) -> None:
        self._selected_id = None
        self._prefix_touched = False
        self.table.clearSelection()
        self.name.clear()
        self.service.setCurrentIndex(0)
        self.use_patient_id.setChecked(True)
        self.rate.setValue(0)
        self.prefix.clear()
        self.active.setChecked(True)

    def _save(self) -> None:
        name = self.name.text().strip()
        service_id = self.service.currentData()
        if not name or not service_id:
            QMessageBox.warning(self, "Save", "Option name and service are required.")
            return
        payload = {
            "name": name,
            "service_id": service_id,
            "use_patient_id": self.use_patient_id.isChecked(),
            "default_rate": self.rate.value(),
            "is_active": self.active.isChecked(),
        }
        prefix = self.prefix.text().strip()
        if prefix:
            payload["bill_prefix"] = prefix
        try:
            if self._selected_id:
                self.api.update_single_service_opd_option(self._selected_id, payload)
            else:
                self.api.create_single_service_opd_option(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return
        self._reload_menus()
        self._clear_form()
        self.refresh()
        QMessageBox.information(
            self,
            "Saved",
            "Billing option saved. It appears under Transactions → Billing.",
        )

    def _reload_menus(self) -> None:
        try:
            menus = self.api.get_my_menus()
        except ApiError:
            return
        session = get_session()
        session.menus = menus
        session.flat_menus = flatten_menus(menus)
        window = self.window()
        sidebar = getattr(window, "sidebar", None)
        if sidebar is not None:
            sidebar.load_menus()
