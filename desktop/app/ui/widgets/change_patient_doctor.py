"""Change patient name (updates master) and/or consulting doctor on OPD/IPD bills."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.styles import BTN_PRIMARY, BTN_SECONDARY, TEXT_MUTED


class ChangePatientDoctorWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._loaded: dict | None = None
        self._doctors: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        heading = QLabel("Change Patient Name / Doctor")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        root.addWidget(heading)

        hint = QLabel(
            "After a bill is saved: correct insurance/patient name (updates Patient Master) "
            "and/or change consulting doctor (select from existing doctors). Works for OPD and IPD."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        root.addWidget(hint)

        search_box = QGroupBox("Find Bill")
        search_form = QFormLayout(search_box)
        type_row = QHBoxLayout()
        self.bill_type_group = QButtonGroup(self)
        self.opd_radio = QRadioButton("OPD")
        self.ipd_radio = QRadioButton("IPD")
        self.opd_radio.setChecked(True)
        self.bill_type_group.addButton(self.opd_radio)
        self.bill_type_group.addButton(self.ipd_radio)
        type_row.addWidget(self.opd_radio)
        type_row.addWidget(self.ipd_radio)
        type_row.addStretch(1)
        search_form.addRow("Bill Type", type_row)

        bill_row = QHBoxLayout()
        self.bill_no = QLineEdit()
        self.bill_no.setPlaceholderText("Bill number")
        self.bill_no.setMaximumWidth(220)
        self.bill_no.returnPressed.connect(self._load_bill)
        load_btn = QPushButton("Load")
        load_btn.setStyleSheet(BTN_SECONDARY)
        load_btn.clicked.connect(self._load_bill)
        bill_row.addWidget(self.bill_no)
        bill_row.addWidget(load_btn)
        bill_row.addStretch(1)
        search_form.addRow("Bill No", bill_row)
        root.addWidget(search_box)

        self.info = QLabel("Load a bill to continue.")
        self.info.setStyleSheet(f"color: {TEXT_MUTED};")
        root.addWidget(self.info)

        # Patient name — primary action
        name_box = QGroupBox("Patient Name (updates Patient Master)")
        name_layout = QVBoxLayout(name_box)
        self.change_name = QCheckBox("Change patient name")
        self.change_name.stateChanged.connect(self._sync_enabled)
        name_layout.addWidget(self.change_name)
        name_form = QFormLayout()
        self.title_edit = QLineEdit()
        self.first_name = QLineEdit()
        self.middle_name = QLineEdit()
        self.last_name = QLineEdit()
        for field in (self.title_edit, self.first_name, self.middle_name, self.last_name):
            field.setMaximumWidth(260)
        name_form.addRow("Title", self.title_edit)
        name_form.addRow("First Name", self.first_name)
        name_form.addRow("Middle Name", self.middle_name)
        name_form.addRow("Last Name", self.last_name)
        name_layout.addLayout(name_form)
        root.addWidget(name_box)

        # Doctor — select only
        doctor_box = QGroupBox("Consulting Doctor")
        doctor_layout = QVBoxLayout(doctor_box)
        self.change_doctor = QCheckBox("Change doctor")
        self.change_doctor.stateChanged.connect(self._sync_enabled)
        doctor_layout.addWidget(self.change_doctor)
        doctor_form = QFormLayout()
        self.doctor_combo = QComboBox()
        self.doctor_combo.setMinimumWidth(280)
        doctor_form.addRow("Select Doctor", self.doctor_combo)
        doctor_layout.addLayout(doctor_form)
        root.addWidget(doctor_box)

        # Collapsed patient master details
        self.master_toggle = QToolButton()
        self.master_toggle.setText("Patient Master details ▸")
        self.master_toggle.setCheckable(True)
        self.master_toggle.setChecked(False)
        self.master_toggle.setStyleSheet("QToolButton { border: none; color: #1e40af; font-weight: bold; }")
        self.master_toggle.toggled.connect(self._toggle_master)
        root.addWidget(self.master_toggle)

        self.master_box = QGroupBox("Patient Master (read-only)")
        master_form = QFormLayout(self.master_box)
        self.patient_no_label = QLabel("—")
        self.patient_id_label = QLabel("—")
        master_form.addRow("Patient No", self.patient_no_label)
        master_form.addRow("Patient Id", self.patient_id_label)
        note = QLabel("Full master edit is under Patient Master / Patient List if needed.")
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        note.setWordWrap(True)
        master_form.addRow(note)
        self.master_box.setVisible(False)
        root.addWidget(self.master_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(BTN_SECONDARY)
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)
        root.addStretch(1)

        self._sync_enabled()
        self._load_doctors()

    def _toggle_master(self, checked: bool) -> None:
        self.master_box.setVisible(checked)
        self.master_toggle.setText(
            "Patient Master details ▾" if checked else "Patient Master details ▸"
        )

    def _bill_type(self) -> str:
        return "IPD" if self.ipd_radio.isChecked() else "OPD"

    def _load_doctors(self) -> None:
        cache = get_session().cache
        if cache.loaded and cache.doctors:
            self._doctors = list(cache.doctors)
        else:
            try:
                page = self.api.list_doctors(page=1, page_size=500)
                self._doctors = page.get("items") or []
            except ApiError:
                self._doctors = []
        self.doctor_combo.clear()
        self.doctor_combo.addItem("— Select doctor —", None)
        for doctor in self._doctors:
            if doctor.get("is_active") is False:
                continue
            label = doctor.get("full_name") or doctor.get("doctor_code") or doctor.get("id")
            self.doctor_combo.addItem(label, doctor.get("id"))

    def _sync_enabled(self) -> None:
        name_on = self.change_name.isChecked()
        for field in (self.title_edit, self.first_name, self.middle_name, self.last_name):
            field.setEnabled(name_on)
        self.doctor_combo.setEnabled(self.change_doctor.isChecked())

    def _load_bill(self) -> None:
        bill_no = self.bill_no.text().strip()
        if not bill_no:
            QMessageBox.warning(self, "Bill", "Enter bill number.")
            return
        try:
            self._loaded = self.api.lookup_bill_identity(
                bill_type=self._bill_type(),
                bill_no=bill_no,
            )
        except ApiError as exc:
            self._loaded = None
            QMessageBox.warning(self, "Bill", str(exc))
            return

        data = self._loaded
        self.info.setText(
            f"{data.get('bill_type')} {data.get('bill_no')} | "
            f"Date {data.get('bill_date') or '—'} | "
            f"Patient {data.get('patient_no') or '—'} | "
            f"Doctor {data.get('doctor_name') or '—'} | "
            f"Net {float(data.get('net_amount') or 0):.2f}"
        )
        self.title_edit.setText(data.get("title") or "")
        self.first_name.setText(data.get("first_name") or "")
        self.middle_name.setText(data.get("middle_name") or "")
        self.last_name.setText(data.get("last_name") or "")
        self.patient_no_label.setText(data.get("patient_no") or "—")
        self.patient_id_label.setText(data.get("patient_id") or "—")

        doctor_id = data.get("doctor_id")
        idx = self.doctor_combo.findData(doctor_id)
        self.doctor_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.change_name.setChecked(False)
        self.change_doctor.setChecked(False)
        self._sync_enabled()

    def _save(self) -> None:
        if not self._loaded:
            QMessageBox.warning(self, "Save", "Load a bill first.")
            return
        if not self.change_name.isChecked() and not self.change_doctor.isChecked():
            QMessageBox.warning(self, "Save", "Tick Change patient name and/or Change doctor.")
            return
        payload = {
            "bill_type": self._bill_type(),
            "bill_no": self.bill_no.text().strip(),
            "update_patient_name": self.change_name.isChecked(),
            "update_doctor": self.change_doctor.isChecked(),
        }
        if self.change_name.isChecked():
            first = self.first_name.text().strip()
            if not first:
                QMessageBox.warning(self, "Name", "First name is required.")
                return
            payload.update(
                {
                    "title": self.title_edit.text().strip() or None,
                    "first_name": first,
                    "middle_name": self.middle_name.text().strip() or None,
                    "last_name": self.last_name.text().strip() or None,
                }
            )
        if self.change_doctor.isChecked():
            doctor_id = self.doctor_combo.currentData()
            if not doctor_id:
                QMessageBox.warning(self, "Doctor", "Select a doctor.")
                return
            payload["doctor_id"] = doctor_id

        try:
            self._loaded = self.api.update_bill_identity(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return

        QMessageBox.information(self, "Saved", "Changes saved.")
        self._load_bill()

    def _clear(self) -> None:
        self._loaded = None
        self.bill_no.clear()
        self.info.setText("Load a bill to continue.")
        self.title_edit.clear()
        self.first_name.clear()
        self.middle_name.clear()
        self.last_name.clear()
        self.patient_no_label.setText("—")
        self.patient_id_label.setText("—")
        self.doctor_combo.setCurrentIndex(0)
        self.change_name.setChecked(False)
        self.change_doctor.setChecked(False)
        self._sync_enabled()
