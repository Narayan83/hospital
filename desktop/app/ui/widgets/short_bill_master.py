from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import flatten_menus, get_session


class ServicePickDialog(QDialog):
    """Pick one row from Patient Service Master."""

    def __init__(self, services: list[dict], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Service")
        self.resize(640, 460)
        self._services = services
        self.selected: dict | None = None

        layout = QVBoxLayout(self)
        hint = QLabel("Services from Patient Service Master. Type to search, then double-click or press Select.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Service name or code")
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Code", "Service Name", "Rate"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda _index: self._accept_current())
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self._accept_current)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(select_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        self._apply_filter("")

    def _apply_filter(self, text: str) -> None:
        query = text.strip().casefold()
        rows = [
            item
            for item in self._services
            if item.get("is_active") is not False
            and (
                not query
                or query in str(item.get("name", "")).casefold()
                or query in str(item.get("code", "")).casefold()
            )
        ]
        self.table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            code = QTableWidgetItem(str(item.get("code") or ""))
            name = QTableWidgetItem(str(item.get("name") or ""))
            rate = QTableWidgetItem(f"{float(item.get('rate') or 0):.2f}")
            code.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.table.setItem(row, 0, code)
            self.table.setItem(row, 1, name)
            self.table.setItem(row, 2, rate)
        self._visible = rows

    def _accept_current(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "_visible", [])):
            QMessageBox.information(self, "Select Service", "Choose a service from the list.")
            return
        self.selected = self._visible[row]
        self.accept()


class ShortBillMasterWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._types: list[dict] = []
        self._services: list[dict] = []
        self._doctors: list[dict] = []
        self._selected_id: str | None = None
        self._service_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Short Bill Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Type the name. That name is added under Transactions when you save. "
            "Pick the service from Patient Service Master. The code is created automatically."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Short Bill Type")
        form = QFormLayout(form_box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.name = QLineEdit()
        self.name.setPlaceholderText("This name becomes the Transactions menu")
        self.service_display = QLineEdit()
        self.service_display.setReadOnly(True)
        self.service_display.setPlaceholderText("Select a service from Patient Service Master")
        service_btn = QPushButton("Select Service")
        service_btn.clicked.connect(self._pick_service)
        service_row = QHBoxLayout()
        service_row.addWidget(self.service_display, stretch=1)
        service_row.addWidget(service_btn)
        service_host = QWidget()
        service_host.setLayout(service_row)
        self.doctor = QComboBox()
        self.doctor.setMaxVisibleItems(20)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 9999999)
        self.rate.setDecimals(2)
        self.prefix = QLineEdit()
        self.prefix.setPlaceholderText("Auto from the name")
        self.prefix.setMaximumWidth(160)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        self.sort_order.setMaximumWidth(120)
        wide = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for field in (self.name, self.service_display, self.doctor):
            field.setMinimumWidth(520)
            field.setSizePolicy(wide)
            field.setProperty("hmsAllowWide", True)
        form.addRow("Name *", self.name)
        form.addRow("Service *", service_host)
        form.addRow("Default Rate", self.rate)
        form.addRow("Default Doctor", self.doctor)
        form.addRow("Bill Prefix", self.prefix)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self._close)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Code", "Name", "Transaction Menu", "Service", "Rate", "Doctor"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(80)
        self.table.setColumnWidth(1, 280)
        self.table.setColumnWidth(3, 280)
        self.table.setColumnWidth(5, 240)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._types = self.api.list_short_bill_types()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            self._types = []
        try:
            services = self.api.list_patient_services()
            self._services = services if isinstance(services, list) else services.get("items", [])
        except ApiError as exc:
            QMessageBox.warning(self, "Services", str(exc))
            self._services = list(get_session().cache.patient_services or [])
        try:
            self._doctors = self._load_all_doctors()
        except ApiError as exc:
            QMessageBox.warning(self, "Doctors", str(exc))
            self._doctors = list(get_session().cache.doctors or [])
        self._load_doctor_combo()
        self._load_table()

    def _load_all_doctors(self) -> list[dict]:
        items: list[dict] = []
        page = 1
        while page <= 50:
            doctors = self.api.list_doctors(page=page, page_size=100)
            batch = doctors.get("items", []) if isinstance(doctors, dict) else list(doctors or [])
            items.extend(batch)
            pages = int(doctors.get("pages") or 1) if isinstance(doctors, dict) else 1
            if page >= pages or not batch:
                break
            page += 1
        return items

    def _pick_service(self) -> None:
        if not self._services:
            try:
                services = self.api.list_patient_services()
                self._services = services if isinstance(services, list) else services.get("items", [])
            except ApiError as exc:
                QMessageBox.warning(self, "Services", str(exc))
                return
        active = [item for item in self._services if item.get("is_active") is not False]
        if not active:
            QMessageBox.information(
                self,
                "Select Service",
                "No services found. Add them in Patient Service Creation first.",
            )
            return
        dialog = ServicePickDialog(active, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected:
            return
        chosen = dialog.selected
        self._service_id = chosen.get("id")
        self.service_display.setText(
            f"{chosen.get('name', '')}  ({chosen.get('code', '')})".strip()
        )
        self.rate.setValue(float(chosen.get("rate") or 0))

    def _load_doctor_combo(self) -> None:
        current = self.doctor.currentData()
        self.doctor.clear()
        self.doctor.addItem("— None —", None)
        for item in self._doctors:
            if item.get("is_active") is False:
                continue
            self.doctor.addItem(item.get("full_name", ""), item.get("id"))
        if current:
            idx = self.doctor.findData(current)
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)
        view = self.doctor.view()
        view.setMinimumWidth(520)
        view.setStyleSheet(
            "QAbstractItemView { min-height: 160px; max-height: 360px; background: white; color: black; }"
        )

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._types))
        shown = [item for item in self._types if item.get("is_active") is not False]
        self._types = shown
        self.table.setRowCount(len(shown))
        for row, item in enumerate(shown):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("default_service_name") or "—"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(item.get('default_rate') or 0):.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(item.get("default_doctor_name") or "—"))

    def _on_table_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        code_cell = self.table.item(rows[0].row(), 0)
        if code_cell is None:
            return
        code = code_cell.text()
        item = next((row for row in self._types if row.get("code") == code), None)
        if not item:
            return
        self._selected_id = item.get("id")
        self.name.setText(item.get("name", ""))
        self._service_id = item.get("default_service_id")
        self.service_display.setText(item.get("default_service_name") or "")
        self.rate.setValue(float(item.get("default_rate") or 0))
        doctor_id = item.get("default_doctor_id")
        if doctor_id:
            didx = self.doctor.findData(doctor_id)
            if didx >= 0:
                self.doctor.setCurrentIndex(didx)
            else:
                self.doctor.setCurrentIndex(0)
        else:
            self.doctor.setCurrentIndex(0)
        self.prefix.setText(item.get("bill_prefix", ""))
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _selected_item(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        code_item = self.table.item(rows[0].row(), 0)
        if code_item is None:
            return None
        code = code_item.text()
        return next((row for row in self._types if row.get("code") == code), None)

    def _delete_selected(self) -> None:
        item = self._selected_item() or (
            next((row for row in self._types if row.get("id") == self._selected_id), None)
            if self._selected_id
            else None
        )
        if item is None:
            QMessageBox.information(self, "Delete", "Select a row to delete.")
            return
        name = item.get("name") or "this entry"
        if (
            QMessageBox.question(
                self,
                "Delete",
                f"Delete “{name}”? It will be removed from Transactions.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.api.delete_short_bill_type(item["id"])
        except ApiError as exc:
            QMessageBox.warning(self, "Delete", str(exc))
            return
        self._reload_menus()
        self._clear_form()
        self.refresh()
        QMessageBox.information(self, "Deleted", f"“{name}” deleted.")

    def _clear_form(self) -> None:
        self._selected_id = None
        self._service_id = None
        self.name.clear()
        self.service_display.clear()
        self.rate.setValue(0)
        self.doctor.setCurrentIndex(0)
        self.prefix.clear()
        self.sort_order.setValue(0)
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Save", "Name is required. It becomes the Transactions menu.")
            return
        if not self._service_id:
            QMessageBox.warning(self, "Save", "Select a service from Patient Service Master.")
            return
        selected = next((item for item in self._services if item.get("id") == self._service_id), None)
        service_name = (selected or {}).get("name") or self.service_display.text().strip()
        prefix = self.prefix.text().strip().upper()
        if not prefix:
            words = [part for part in name.upper().replace("-", " ").split() if part.isalnum()]
            if len(words) >= 2:
                prefix = "".join(word[0] for word in words)[:6]
            elif words:
                prefix = words[0][:6]
            else:
                prefix = "SB"
        payload = {
            "name": name,
            "default_service_id": self._service_id,
            "default_service_name": service_name,
            "default_rate": self.rate.value(),
            "default_doctor_id": self.doctor.currentData(),
            "bill_prefix": prefix,
            "sort_order": self.sort_order.value(),
            "is_active": True,
        }
        editing = bool(self._selected_id)
        try:
            if editing:
                self.api.update_short_bill_type(self._selected_id, payload)
            else:
                self.api.create_short_bill_type(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return
        self._reload_menus()
        self._clear_form()
        self.refresh()
        QMessageBox.information(self, "Saved", f"“{name}” saved.")

    def _reload_menus(self) -> None:
        try:
            menus = self.api.get_my_menus()
        except ApiError:
            return
        session = get_session()
        session.menus = menus
        session.flat_menus = flatten_menus(menus)
        sidebar = getattr(self.window(), "sidebar", None)
        if sidebar is not None:
            sidebar.load_menus()

    def _close(self) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QDialog):
                parent.reject()
                return
            parent = parent.parentWidget()
        window = self.window()
        show_module = getattr(window, "_show_module", None)
        if callable(show_module):
            show_module("dashboard")
