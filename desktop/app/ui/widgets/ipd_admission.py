from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.components.patient_registration_dialog import register_patient_dialog
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.styles import HEADER_BTN_STYLE

class IpdAdmissionWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._build_ui()

    @staticmethod
    def _wide(widget: QWidget) -> QWidget:
        """Let fields stretch past the global 360px form cap."""
        widget.setProperty("hmsAllowWide", True)
        widget.setMaximumWidth(16777215)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumWidth(280)
        return widget

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form_box = QGroupBox("Admission Details")
        form_box.setProperty("hmsExpandFormFields", True)
        form = QFormLayout(form_box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setProperty("hmsResponsive", True)

        pid_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient No")
        self.patient_id.setMaximumWidth(220)
        find_btn = QPushButton("Find Patient")
        find_btn.clicked.connect(self._find_patient)
        pid_row.addWidget(self.patient_id)
        pid_row.addWidget(find_btn)
        pid_row.addStretch(1)
        form.addRow("Patient Id", pid_row)

        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self._wide(self.patient_name)
        self.patient_name.setMinimumWidth(420)
        self.mobile = QLineEdit()
        self.mobile.setReadOnly(True)
        self._wide(self.mobile)
        form.addRow("Patient Name", self.patient_name)
        form.addRow("Mobile", self.mobile)

        self.admission_no = QLineEdit()
        self.admission_no.setReadOnly(True)
        self.admission_no.setPlaceholderText("Assigned on Save")
        self._wide(self.admission_no)
        self.admission_date = QDateEdit()
        self.admission_date.setCalendarPopup(True)
        self.admission_date.setDisplayFormat("dd/MM/yyyy")
        self.admission_date.setDate(QDate.currentDate())
        self._wide(self.admission_date)
        self.ward = QComboBox()
        self.doctor = QComboBox()
        self.department = QComboBox()
        self.bed_no = QLineEdit()
        self.advance_amount = QLineEdit("0")
        self.diagnosis = QLineEdit()
        self.remarks = QLineEdit()
        for field in (
            self.ward,
            self.doctor,
            self.department,
            self.bed_no,
            self.advance_amount,
            self.diagnosis,
            self.remarks,
        ):
            self._wide(field)
        form.addRow("Admission No", self.admission_no)
        form.addRow("Date", self.admission_date)
        form.addRow("Ward", self.ward)
        form.addRow("Doctor", self.doctor)
        form.addRow("Department", self.department)
        form.addRow("Bed No", self.bed_no)
        form.addRow("Advance", self.advance_amount)
        form.addRow("Diagnosis", self.diagnosis)
        form.addRow("Remarks", self.remarks)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Admission")
        save_btn.clicked.connect(self._save_admission)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("Recent Admissions"))
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Admission No",
                "Date",
                "Patient Id",
                "Patient",
                "Ward",
                "Bed",
                "Advance",
                "Status",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

    def build_header_actions(self) -> QWidget:
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("New Patient", self._open_patient_registration),
                ("OPD Bill", lambda: self._navigate("opd_bill")),
                ("IPD Bill", lambda: self._navigate("ipd_bill")),
            ]
        )

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _open_patient_registration(self) -> None:
        patient = register_patient_dialog(self.api, self)
        if not patient:
            return
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no", ""))
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self.mobile.setText(patient.get("mobile") or patient.get("phone") or "")

    def refresh(self) -> None:
        cache = get_session().cache
        self._load_combo(self.ward, cache.wards, "— Select Ward —")
        self._load_combo(self.department, cache.departments, "— Select —")
        self.doctor.clear()
        self.doctor.addItem("— Select Doctor —", None)
        for doc in cache.doctors if cache.loaded else []:
            label = f"{doc.get('doctor_code')} — {doc.get('full_name', '')}"
            self.doctor.addItem(label, doc.get("id"))
        self._load_recent()

    @staticmethod
    def _load_combo(combo: QComboBox, items: list[dict], placeholder: str) -> None:
        combo.clear()
        combo.addItem(placeholder, None)
        for item in items:
            combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _find_patient(self) -> None:
        patient = pick_patient(self.api, self, initial_patient_no=self.patient_id.text().strip())
        if not patient:
            return
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no", ""))
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self.mobile.setText(patient.get("mobile") or patient.get("phone") or "")

    def _save_admission(self) -> None:
        if not self._patient:
            QMessageBox.warning(self, "Validation", "Find and load a patient first.")
            return
        qd = self.admission_date.date()
        admission_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        payload = {
            "patient_id": self._patient.get("id"),
            "ward_id": self.ward.currentData(),
            "doctor_id": self.doctor.currentData(),
            "department_id": self.department.currentData(),
            "bed_no": self.bed_no.text().strip() or None,
            "advance_amount": self.advance_amount.text().strip() or "0",
            "diagnosis": self.diagnosis.text().strip() or None,
            "remarks": self.remarks.text().strip() or None,
            "admission_date": admission_date,
        }
        try:
            admission = self.api.create_ipd_admission(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        admission_no = admission.get("admission_no", "")
        self.admission_no.setText(admission_no)
        if admission_no:
            QGuiApplication.clipboard().setText(admission_no)
        self._set_status(f"Admission saved: {admission_no} — copied to clipboard.")
        QMessageBox.information(self, "Saved", f"IPD Admission {admission_no} saved successfully.")
        self._load_recent()

    def _load_recent(self) -> None:
        try:
            rows = self.api.list_ipd_admissions()
        except ApiError:
            return
        self.table.setRowCount(len(rows))
        for row_idx, item in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(item.get("admission_no", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(item.get("admission_date", ""))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item.get("patient_no") or ""))
            self.table.setItem(row_idx, 3, QTableWidgetItem(item.get("patient_name") or ""))
            self.table.setItem(row_idx, 4, QTableWidgetItem(item.get("ward_name") or ""))
            self.table.setItem(row_idx, 5, QTableWidgetItem(item.get("bed_no") or ""))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(item.get("advance_amount", ""))))
            self.table.setItem(row_idx, 7, QTableWidgetItem(item.get("status", "")))

    def _clear_form(self) -> None:
        self._patient = None
        self.patient_id.clear()
        self.patient_name.clear()
        self.mobile.clear()
        self.admission_no.clear()
        self.bed_no.clear()
        self.advance_amount.setText("0")
        self.diagnosis.clear()
        self.remarks.clear()
        self.admission_date.setDate(QDate.currentDate())
        self._set_status("Ready for new admission.")

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
