from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
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


class SingleServiceOpdBillWidget(QWidget):
    def __init__(self, api: ApiClient, *, menu_code: str):
        super().__init__()
        self.api = api
        self.menu_code = menu_code
        self._option: dict | None = None
        self._doctors: list[dict] = []
        self._bills: list[dict] = []
        self._patient_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.heading = QLabel("Single Service OPD")
        self.heading.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1e40af; text-decoration: underline;"
        )
        layout.addWidget(self.heading)

        top = QHBoxLayout()
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("Auto on save")
        self.bill_no.setMaximumWidth(160)
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        self.bill_date.dateChanged.connect(lambda _date: self._load_bills())
        top.addWidget(QLabel("Bill No"))
        top.addWidget(self.bill_no)
        top.addSpacing(12)
        top.addWidget(QLabel("Date"))
        top.addWidget(self.bill_date)
        top.addStretch()
        layout.addLayout(top)

        form = QFormLayout()
        self.doctor = QComboBox()
        self.doctor.setMinimumWidth(280)
        form.addRow("Doctor *", self.doctor)

        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Patient ID")
        self.patient_no.setMaximumWidth(160)
        self.patient_no.returnPressed.connect(self._find_patient)
        self.patient_no.textChanged.connect(self._clear_resolved_patient)
        self.patient_name_locked = QLineEdit()
        self.patient_name_locked.setReadOnly(True)
        self.patient_name_locked.setPlaceholderText("Name fills after Find")
        find_btn = QPushButton("Find")
        find_btn.clicked.connect(self._find_patient)
        id_row = QHBoxLayout()
        id_row.addWidget(self.patient_no)
        id_row.addWidget(find_btn)
        id_row.addWidget(self.patient_name_locked, stretch=1)
        self.patient_id_host = QWidget()
        self.patient_id_host.setLayout(id_row)
        self.patient_name = QLineEdit()
        self.patient_name.setPlaceholderText("Patient name")
        self.patient_id_label = QLabel("Patient ID *")
        self.patient_name_label = QLabel("Patient Name *")
        form.addRow(self.patient_id_label, self.patient_id_host)
        form.addRow(self.patient_name_label, self.patient_name)

        self.service_name = QLineEdit()
        self.service_name.setReadOnly(True)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 9999999)
        self.rate.setDecimals(2)
        form.addRow("Service", self.service_name)
        form.addRow("Rate *", self.rate)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_entry)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        list_head = QHBoxLayout()
        list_head.addWidget(QLabel("Bills on this date"))
        list_head.addStretch()
        cancel_btn = QPushButton("Cancel Selected")
        cancel_btn.clicked.connect(self._cancel_selected)
        list_head.addWidget(cancel_btn)
        layout.addLayout(list_head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Bill No", "Patient", "Doctor", "Rate"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        try:
            self._option = self.api.get_single_service_opd_option_by_menu(self.menu_code)
            doctors = self.api.list_doctors(page_size=500)
            self._doctors = doctors.get("items", []) if isinstance(doctors, dict) else doctors
        except ApiError as exc:
            QMessageBox.warning(self, "Setup", str(exc))
            return
        title = self._option.get("name") or "Single Service OPD"
        self.heading.setText(title)
        self._load_doctors()
        self._apply_option()
        self._load_bills()

    def _apply_option(self) -> None:
        if not self._option:
            return
        use_id = bool(self._option.get("use_patient_id"))
        self.patient_id_label.setVisible(use_id)
        self.patient_id_host.setVisible(use_id)
        self.patient_name_label.setVisible(not use_id)
        self.patient_name.setVisible(not use_id)
        self.service_name.setText(self._option.get("service_name") or "")
        if not self.bill_no.text().strip():
            self.rate.setValue(float(self._option.get("default_rate") or 0))

    def _load_doctors(self) -> None:
        current = self.doctor.currentData()
        self.doctor.clear()
        self.doctor.addItem("— Select doctor —", None)
        for item in self._doctors:
            if item.get("is_active") is False:
                continue
            self.doctor.addItem(item.get("full_name") or item.get("doctor_code") or "", item.get("id"))
        if current:
            idx = self.doctor.findData(current)
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)

    def _clear_resolved_patient(self, _text: str) -> None:
        self._patient_id = None
        self.patient_name_locked.clear()

    def _find_patient(self) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            QMessageBox.information(self, "Find", "Enter the patient ID.")
            return
        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = result.get("items", [])
        except ApiError as exc:
            QMessageBox.warning(self, "Find", str(exc))
            return
        match = next(
            (
                item
                for item in items
                if str(item.get("patient_no", "")).casefold() == patient_no.casefold()
            ),
            None,
        )
        if match is None and len(items) == 1:
            match = items[0]
        if match is None:
            self._patient_id = None
            self.patient_name_locked.clear()
            QMessageBox.information(self, "Find", "No patient found for that ID.")
            return
        self.patient_no.blockSignals(True)
        self.patient_no.setText(match.get("patient_no") or patient_no)
        self.patient_no.blockSignals(False)
        self._patient_id = match.get("id")
        name = " ".join(
            part
            for part in [match.get("first_name"), match.get("middle_name"), match.get("last_name")]
            if part
        )
        self.patient_name_locked.setText(name)

    def _save(self) -> None:
        if not self._option:
            QMessageBox.warning(self, "Save", "This billing option is not set up.")
            return
        doctor_id = self.doctor.currentData()
        if not doctor_id:
            QMessageBox.warning(self, "Save", "Select a doctor.")
            return
        use_id = bool(self._option.get("use_patient_id"))
        if use_id and not self._patient_id:
            self._find_patient()
            if not self._patient_id:
                return
        if not use_id and not self.patient_name.text().strip():
            QMessageBox.warning(self, "Save", "Enter the patient name.")
            return
        payload = {
            "option_id": self._option["id"],
            "bill_date": self.bill_date.date().toPython().isoformat(),
            "doctor_id": doctor_id,
            "rate": self.rate.value(),
            "patient_id": self._patient_id if use_id else None,
            "patient_no": self.patient_no.text().strip() if use_id else None,
            "patient_name": self.patient_name.text().strip() if not use_id else "",
        }
        try:
            bill = self.api.create_single_service_opd_bill(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return
        self.bill_no.setText(bill.get("bill_no", ""))
        QMessageBox.information(self, "Saved", f"Bill {bill.get('bill_no')} saved.")
        self._clear_entry(keep_doctor=True)
        self._load_bills()

    def _clear_entry(self, *, keep_doctor: bool = False) -> None:
        self.bill_no.clear()
        self._patient_id = None
        self.patient_no.clear()
        self.patient_name_locked.clear()
        self.patient_name.clear()
        if not keep_doctor:
            self.doctor.setCurrentIndex(0)
        if self._option:
            self.rate.setValue(float(self._option.get("default_rate") or 0))
        else:
            self.rate.setValue(0)

    def _load_bills(self) -> None:
        if not self._option:
            return
        try:
            self._bills = self.api.list_single_service_opd_bills(
                option_id=self._option["id"],
                bill_date=self.bill_date.date().toPython().isoformat(),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Bills", str(exc))
            return
        self.table.setRowCount(len(self._bills))
        for row, bill in enumerate(self._bills):
            patient = bill.get("patient_name") or ""
            if bill.get("patient_no"):
                patient = f"{bill.get('patient_no')}  {patient}".strip()
            values = [
                bill.get("bill_no", ""),
                patient,
                bill.get("doctor_name") or "",
                f"{float(bill.get('rate') or 0):.2f}",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, bill.get("id"))
                self.table.setItem(row, col, cell)

    def _cancel_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._bills):
            QMessageBox.information(self, "Cancel", "Select a bill to cancel.")
            return
        bill = self._bills[row]
        if (
            QMessageBox.question(
                self,
                "Cancel",
                f"Cancel bill {bill.get('bill_no')}? It will be removed from collection.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.api.cancel_single_service_opd_bill(bill["id"])
        except ApiError as exc:
            QMessageBox.warning(self, "Cancel", str(exc))
            return
        self._load_bills()
