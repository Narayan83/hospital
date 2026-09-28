import re
from datetime import date, timedelta
from pathlib import Path
import tempfile

import httpx
from PySide6.QtCore import QDate, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.controllers.patient_controller import PatientController
from app.session import get_session
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.components.date_edit import configure_date_edit, finalize_date_edit, style_date_field
from app.ui.form_navigation import enable_enter_key_navigation
from app.ui.print_utils import preview_report

TITLES = ["Mr", "Mrs", "Miss", "Ms", "Dr", "Master", "Baby"]
SEX_OPTIONS = ["M", "F", "O"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
EXISTING_OPTIONS = [("Y", True), ("N", False)]
PATIENT_TYPES = ["General", "Insurance", "Corporate", "Staff", "VIP"]

_AGE_UNIT_DAYS = {"Days": 1, "Weeks": 7, "Months": 30, "Years": 365}
_AGE_UNIT_ALIASES = {
    "d": "Days", "day": "Days", "days": "Days",
    "w": "Weeks", "wk": "Weeks", "wks": "Weeks", "week": "Weeks", "weeks": "Weeks",
    "m": "Months", "mo": "Months", "mos": "Months", "month": "Months", "months": "Months",
    "y": "Years", "yr": "Years", "yrs": "Years", "year": "Years", "years": "Years",
}


def _parse_age_text(text: str) -> tuple[int, str] | None:
    """Parse free-text age like '8 Months', '45d', '3' (bare number -> Years)."""
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return None
    match = re.match(r"^(\d+)\s*([a-z]*)$", cleaned)
    if not match:
        return None
    value = int(match.group(1))
    unit_raw = match.group(2)
    unit = _AGE_UNIT_ALIASES.get(unit_raw) if unit_raw else "Years"
    if not unit:
        return None
    return value, unit


def _friendly_age_from_dob(dob: date) -> str:
    """Human-readable age (Years/Months/Days) from a date of birth."""
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if years >= 1:
        return f"{years} Years"
    months = (today.year - dob.year) * 12 + today.month - dob.month
    if today.day < dob.day:
        months -= 1
    if months >= 1:
        return f"{months} Months"
    return f"{max((today - dob).days, 0)} Days"

def _build_compact_style() -> str:
    """Registration chrome — same field height as density (no clip vs form_field_style)."""
    from app.ui.responsive_layout import get_density
    from app.ui.styles import date_edit_stylesheet

    d = get_density()
    h = d.field_min_height
    return (
        f"""
QLineEdit, QComboBox {{
    background-color: #ffffff;
    background: #ffffff;
    border: 1px solid #94a3b8;
    min-height: {h}px;
    max-height: {h}px;
    padding: {d.compact_v_pad}px 8px;
    font-size: {d.font_size}px;
    color: #0f172a;
}}
QLineEdit:read-only {{
    background-color: #ffffff;
    background: #ffffff;
    color: #0f172a;
}}
QComboBox {{
    padding: {d.compact_v_pad}px 2px {d.compact_v_pad}px 8px;
}}
QComboBox::drop-down {{
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    background-color: #ffffff;
    background: #ffffff;
    border-left: 1px solid #94a3b8;
}}
QGroupBox {{
    font-size: {d.font_size}px;
    font-weight: bold;
    margin-top: {max(4, d.group_margin_top - 2)}px;
    padding: {max(4, d.group_pad_top - 2)}px {max(4, d.group_pad_sides - 2)}px {max(4, d.group_pad_bottom - 2)}px {max(4, d.group_pad_sides - 2)}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 6px;
    padding: 0 3px;
}}
QLabel {{
    font-size: {d.label_font_size}px;
}}
QPushButton {{
    min-height: {h}px;
    padding: {d.compact_v_pad}px 10px;
    font-size: {d.font_size}px;
}}
"""
        + date_edit_stylesheet(compact=True)
    )


class PatientRegistrationWidget(QWidget):
    patient_saved = Signal(dict)

    def __init__(self, controller: PatientController):
        super().__init__()
        self.controller = controller
        self._current_patient_id: str | None = None
        self._pending_aadhar_scan: str | None = None
        self._form_editable = True
        self._syncing_age = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        from app.ui.responsive_layout import get_density, paint_page_surface, wrap_widget_in_scroll

        d = get_density()
        paint_page_surface(self)
        # Full-width form: address/contact rows and name fields stretch with the window.
        self.setProperty("hmsExpandFormFields", True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(d.content_margin, 2, d.content_margin, 2)
        outer.setSpacing(max(2, d.section_spacing - 1))
        self.setStyleSheet(_build_compact_style())

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        title = QLabel("New Patient Creation")
        title.setStyleSheet(
            f"font-size: {d.title_font_size}px; font-weight: bold; color: #1d4ed8; "
            "text-decoration: underline; margin: 0; padding: 0;"
        )
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(QLabel("Hospital Section"))
        self.hospital_section = QComboBox()
        self.hospital_section.setMinimumWidth(160)
        self.hospital_section.currentIndexChanged.connect(self._update_id_format_info)
        header_row.addWidget(self.hospital_section)
        outer.addLayout(header_row)

        form_host = QWidget()
        form_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(form_host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(max(2, d.section_spacing - 1))
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(wrap_widget_in_scroll(form_host), stretch=1)

        id_row = QHBoxLayout()
        id_row.setSpacing(6)
        id_row.setContentsMargins(0, 0, 0, 0)
        id_row.addWidget(QLabel("Patient Id"))
        self.patient_no = QLineEdit()
        self.patient_no.setReadOnly(True)
        self.patient_no.setMinimumWidth(108)
        self.patient_no.setMaximumWidth(140)
        self.patient_no.setPlaceholderText("Auto on save")
        id_row.addWidget(self.patient_no)

        self.title = QComboBox()
        self.title.addItems(TITLES)
        self.title.setFixedWidth(58)
        id_row.addWidget(self.title)

        id_row.addWidget(QLabel("First Name"))
        self.first_name = QLineEdit()
        self.first_name.setMaximumWidth(220)
        id_row.addWidget(self.first_name, stretch=1)

        id_row.addWidget(QLabel("Second Name"))
        self.middle_name = QLineEdit()
        self.middle_name.setMaximumWidth(200)
        id_row.addWidget(self.middle_name, stretch=1)

        id_row.addWidget(QLabel("Third Name"))
        self.last_name = QLineEdit()
        self.last_name.setMaximumWidth(200)
        id_row.addWidget(self.last_name, stretch=1)
        id_row.addStretch(1)
        root.addLayout(id_row)

        self.id_format_label = QLabel("")
        self.id_format_label.setStyleSheet(
            f"color: #475569; font-size: {max(9, d.font_size - 2)}px; margin: 0; padding: 0;"
        )
        self.id_format_label.setWordWrap(False)
        self.id_format_label.setMaximumHeight(d.font_size + 4)
        root.addWidget(self.id_format_label)

        demo_row = QHBoxLayout()
        demo_row.setSpacing(6)
        demo_row.setContentsMargins(0, 0, 0, 0)

        demo_row.addWidget(QLabel("Date of Birth"))
        self.dob = QDateEdit()
        self.dob.setProperty("hmsCompactDate", True)
        configure_date_edit(self.dob)
        self.dob.setDate(QDate.currentDate())
        self.dob.setSpecialValueText("")
        self.dob.setFixedWidth(142)
        self.dob.setFixedHeight(get_density().date_compact_height)
        finalize_date_edit(self.dob)
        self.dob.dateChanged.connect(self._update_age)
        demo_row.addWidget(self.dob)

        demo_row.addWidget(QLabel("Age"))
        self.age = QLineEdit("0 Days")
        self.age.setFixedWidth(96)
        self.age.setPlaceholderText("e.g. 8 Months")
        self.age.setToolTip(
            "Auto-filled from Date of Birth. You can also type an approximate age "
            "directly (e.g. '8 Months', '20 Days', '45 Years') when exact DOB is unknown "
            "\u2014 Date of Birth will be estimated automatically."
        )
        self.age.editingFinished.connect(self._update_dob_from_age)
        demo_row.addWidget(self.age)

        demo_row.addWidget(QLabel("Sex"))
        self.sex = QComboBox()
        self.sex.addItems(SEX_OPTIONS)
        self.sex.setFixedWidth(66)
        self.sex.setMinimumContentsLength(1)
        demo_row.addWidget(self.sex)

        demo_row.addWidget(QLabel("Blood Grp"))
        self.blood_group = QComboBox()
        self.blood_group.addItem("— Select —", "")
        for group in BLOOD_GROUPS:
            self.blood_group.addItem(group, group)
        self.blood_group.setFixedWidth(98)
        demo_row.addWidget(self.blood_group)
        demo_row.addStretch(1)
        root.addLayout(demo_row)

        columns = QHBoxLayout()
        columns.setSpacing(8)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setAlignment(Qt.AlignmentFlag.AlignTop)

        left = QVBoxLayout()
        left.setSpacing(max(2, d.section_spacing - 1))
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        left.addWidget(self._address_group(
            "Contact Address",
            "village_code",
            "contact_address1",
            "contact_address2",
            "contact_address3",
            "contact_address4",
            "contact_address5",
            labels=("Village Code", "Village/Address1", "Post/Address2", "Taluk/Address3", "District/Address4", "Pin Code/Address5"),
        ))
        left.addWidget(self._address_group(
            "Additional Address",
            None,
            "perm_address1",
            "perm_address2",
            "perm_address3",
            "perm_address4",
            "perm_address5",
            labels=("Village/Address1", "Post/Address2", "Taluk/Address3", "District/Address4", "Pin Code/Address5"),
        ))
        columns.addLayout(left, stretch=1)

        right_box = QGroupBox()
        right_box.setProperty("hmsSkipResponsive", True)
        right_form = QFormLayout(right_box)
        right_form.setVerticalSpacing(max(2, d.form_v_spacing - 1))
        right_form.setHorizontalSpacing(6)
        right_form.setContentsMargins(6, 6, 6, 6)
        right_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.old_software_id = QLineEdit()
        self.remarks = QLineEdit()
        self.phone = QLineEdit()
        self.mobile = QLineEdit()
        self.mobile2 = QLineEdit()
        self.scheme = QLineEdit()
        self.aadhar_no = QLineEdit()
        self.aadhar_scan_status = QLabel("No scan")
        self.aadhar_scan_status.setStyleSheet(f"color: #64748b; font-size: {max(10, d.font_size - 2)}px;")
        upload_aadhar_btn = QPushButton("Upload Scan")
        upload_aadhar_btn.clicked.connect(self._pick_aadhar_scan)
        view_aadhar_btn = QPushButton("View")
        view_aadhar_btn.clicked.connect(self._view_aadhar_scan)
        aadhar_col = QVBoxLayout()
        aadhar_col.setContentsMargins(0, 0, 0, 0)
        aadhar_col.setSpacing(2)
        aadhar_col.addWidget(self.aadhar_no)
        aadhar_actions = QHBoxLayout()
        aadhar_actions.setContentsMargins(0, 0, 0, 0)
        aadhar_actions.setSpacing(4)
        aadhar_actions.addWidget(self.aadhar_scan_status)
        aadhar_actions.addStretch()
        aadhar_actions.addWidget(upload_aadhar_btn)
        aadhar_actions.addWidget(view_aadhar_btn)
        aadhar_col.addLayout(aadhar_actions)
        aadhar_host = QWidget()
        aadhar_host.setLayout(aadhar_col)
        aadhar_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.existing = QComboBox()
        self.existing.addItems(["Y", "N"])
        self.existing.setFixedWidth(64)
        self.existing.currentIndexChanged.connect(self._on_existing_changed)
        self.patient_type = QComboBox()
        self.patient_type.addItems(PATIENT_TYPES)

        right_form.addRow("OLD software Id", self.old_software_id)
        right_form.addRow("Remarks", self.remarks)
        right_form.addRow("Phone", self.phone)
        right_form.addRow("Mobile", self.mobile)
        right_form.addRow("Mobile2", self.mobile2)
        right_form.addRow("Scheme", self.scheme)
        right_form.addRow("Aadhar No", aadhar_host)
        right_form.addRow("Existing?", self.existing)
        right_form.addRow("Patient Type", self.patient_type)
        columns.addWidget(right_box, stretch=1)

        root.addLayout(columns)

        # Action buttons + search live outside the scroll area (pinned) so they
        # stay visible even when the address/contact fields overflow and scroll.
        footer = QVBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(max(2, d.section_spacing - 1))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()
        self.save_btn = QPushButton("Save")
        self.edit_btn = QPushButton("Edit")
        self.print_card_btn = QPushButton("Print Patient Card")
        self.exit_btn = QPushButton("Exit")
        self.save_btn.clicked.connect(self._save_patient)
        self.edit_btn.clicked.connect(self._enable_edit)
        self.print_card_btn.clicked.connect(self._print_patient_card)
        self.exit_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.print_card_btn)
        btn_row.addWidget(self.exit_btn)
        footer.addLayout(btn_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_row.addWidget(QLabel("Search Patient"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Patient no, name, mobile...")
        search_btn = QPushButton("Find Patient")
        search_btn.clicked.connect(self._search_patient)
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(search_btn)
        footer.addLayout(search_row)
        outer.addLayout(footer)

        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setPlaceholderText("Status messages appear here...")
        outer.addWidget(self.status_label)

        self._set_form_enabled(True)
        self.edit_btn.setEnabled(False)

        self._enter_key_filter = enable_enter_key_navigation(
            self,
            skip={self.patient_no, self.status_label, self.search_input},
        )
        self.search_input.returnPressed.connect(self._search_patient)
        # Blank form starts as a new patient (Existing? = N).
        self.existing.setCurrentIndex(1)
        self._sync_remarks_field()

    def _on_existing_changed(self) -> None:
        if self._form_editable and self.existing.currentText() == "N":
            self.remarks.clear()
        self._sync_remarks_field()

    def _sync_remarks_field(self) -> None:
        is_existing = self.existing.currentText() == "Y"
        self.remarks.setEnabled(self._form_editable and is_existing)

    def _address_group(
        self,
        title: str,
        code_field: str | None,
        *field_names: str,
        labels: tuple[str, ...],
    ) -> QGroupBox:
        box = QGroupBox(title)
        box.setProperty("hmsSkipResponsive", True)
        form = QFormLayout(box)
        from app.ui.responsive_layout import get_density

        d = get_density()
        form.setVerticalSpacing(max(2, d.form_v_spacing - 1))
        form.setHorizontalSpacing(6)
        form.setContentsMargins(6, 6, 6, 6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        fields = ([code_field] if code_field else []) + list(field_names)
        for field_name, label in zip(fields, labels, strict=True):
            edit = QLineEdit()
            if field_name == "village_code":
                edit.setText("0")
                edit.setMaximumWidth(72)
            else:
                edit.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
            setattr(self, field_name, edit)
            form.addRow(label, edit)
        return box

    def _update_age(self) -> None:
        """Recompute the friendly Age label whenever Date of Birth changes."""
        if self._syncing_age:
            return
        dob = self.dob.date()
        if not dob.isValid():
            self.age.setText("")
            return
        dob_py = date(dob.year(), dob.month(), dob.day())
        self._syncing_age = True
        try:
            self.age.setText(_friendly_age_from_dob(dob_py))
        finally:
            self._syncing_age = False

    def _update_dob_from_age(self) -> None:
        """Let staff type an approximate age (e.g. '8 Months') and back-fill DOB.

        Useful for infants/children when the exact date of birth isn't known but
        an approximate age is. Reference-range and report logic elsewhere relies
        on Date of Birth, so keeping it in sync keeps those calculations correct.
        """
        if self._syncing_age or not self._form_editable:
            return
        parsed = _parse_age_text(self.age.text())
        if not parsed:
            return
        value, unit = parsed
        estimated_dob = date.today() - timedelta(days=value * _AGE_UNIT_DAYS[unit])
        self._syncing_age = True
        try:
            self.dob.setDate(QDate(estimated_dob.year, estimated_dob.month, estimated_dob.day))
            self.age.setText(f"{value} {unit}")
        finally:
            self._syncing_age = False

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_id_format_info(self) -> None:
        if self._current_patient_id:
            return
        section_id = self.hospital_section.currentData()
        preview, error = self.controller.preview_next_patient_id(section_id)
        if error:
            self.id_format_label.setText(f"ID format not configured: {error}")
            return
        if not preview:
            return
        next_no = preview.get("patient_no") or preview.get("sample_output") or ""
        self.id_format_label.setText(
            f"Next ID: {next_no}  ({preview.get('format_name')} — {preview.get('pattern')}). "
            "Assigned on Save."
        )

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        if text:
            QGuiApplication.clipboard().setText(text)

    def _set_form_enabled(self, enabled: bool) -> None:
        self._form_editable = enabled
        readonly = {self.patient_no, self.status_label}
        for widget_type in (QLineEdit, QComboBox, QDateEdit):
            for widget in self.findChildren(widget_type):
                if widget not in readonly:
                    widget.setEnabled(enabled)
        self._sync_remarks_field()

    def _build_payload(self) -> dict:
        dob_qdate = self.dob.date()
        dob_value = None
        if dob_qdate.isValid():
            dob_value = date(dob_qdate.year(), dob_qdate.month(), dob_qdate.day()).isoformat()

        return {
            "hospital_section_id": self.hospital_section.currentData(),
            "title": self.title.currentText(),
            "first_name": self.first_name.text().strip(),
            "middle_name": self.middle_name.text().strip() or None,
            "last_name": self.last_name.text().strip() or None,
            "date_of_birth": dob_value,
            "age": self.age.text().strip() or None,
            "gender": self.sex.currentText(),
            "blood_group": self.blood_group.currentData() or None,
            "village_code": self.village_code.text().strip() or None,
            "contact_address1": self.contact_address1.text().strip() or None,
            "contact_address2": self.contact_address2.text().strip() or None,
            "contact_address3": self.contact_address3.text().strip() or None,
            "contact_address4": self.contact_address4.text().strip() or None,
            "contact_address5": self.contact_address5.text().strip() or None,
            "perm_address1": self.perm_address1.text().strip() or None,
            "perm_address2": self.perm_address2.text().strip() or None,
            "perm_address3": self.perm_address3.text().strip() or None,
            "perm_address4": self.perm_address4.text().strip() or None,
            "perm_address5": self.perm_address5.text().strip() or None,
            "old_software_id": self.old_software_id.text().strip() or None,
            "remarks": self.remarks.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "mobile": self.mobile.text().strip() or None,
            "mobile2": self.mobile2.text().strip() or None,
            "scheme": self.scheme.text().strip() or None,
            "aadhar_no": self.aadhar_no.text().strip() or None,
            "is_existing_patient": self.existing.currentText() == "Y",
            "patient_type": self.patient_type.currentText(),
        }

    def _validate(self) -> bool:
        if not self.first_name.text().strip():
            QMessageBox.warning(self, "Validation", "First Name is required.")
            return False
        return True

    def _save_patient(self) -> None:
        if not self._validate():
            return

        payload = self._build_payload()

        if self._current_patient_id:
            patient, error = self.controller.update_patient(self._current_patient_id, payload)
            action = "updated"
        else:
            patient, error = self.controller.register_patient(payload)
            action = "saved"

        if error:
            self._set_status(f"Error: {error}")
            QMessageBox.warning(self, "Error", error)
            return

        self._current_patient_id = patient.get("id")
        if self._pending_aadhar_scan and self._current_patient_id:
            uploaded, upload_error = self.controller.upload_aadhar_scan(
                self._current_patient_id, self._pending_aadhar_scan
            )
            if upload_error:
                QMessageBox.warning(self, "Aadhar Scan", upload_error)
            else:
                patient = uploaded or patient
                self._pending_aadhar_scan = None
                self._update_aadhar_scan_status(patient)
        patient_no = patient.get("patient_no", "")
        self.patient_no.setText(patient_no)
        if action == "saved" and patient_no:
            self._copy_to_clipboard(patient_no)
            self._set_status(
                f"Patient saved: {patient_no} — copied to clipboard (paste in billing)."
            )
        else:
            self._set_status(f"Patient {action} successfully: {patient_no}")
        self.edit_btn.setEnabled(True)
        self._set_form_enabled(False)
        self.patient_saved.emit(patient)

    def _enable_edit(self) -> None:
        if not self._current_patient_id:
            QMessageBox.information(self, "Edit", "Load or save a patient first.")
            return
        self._set_form_enabled(True)
        self._set_status("Edit mode — make changes and click Save.")

    def load_for_edit(self, patient: dict) -> None:
        """Load an existing patient and switch straight into edit mode."""
        self._fill_form(patient)
        self._enable_edit()

    def _print_patient_card(self) -> None:
        if not self._current_patient_id:
            QMessageBox.information(
                self,
                "Print Patient Card",
                "Save or load a patient first. A patient ID is required to print the card.",
            )
            return
        preview_report(
            self.controller.api,
            f"/reports/patient-card/{self._current_patient_id}",
            parent=self,
            title="Patient Card",
            report_code="PATIENT_CARD",
        )

    def _clear_form(self) -> None:
        self._current_patient_id = None
        self.patient_no.clear()
        self.first_name.clear()
        self.middle_name.clear()
        self.last_name.clear()
        self.blood_group.setCurrentIndex(0)
        self.village_code.setText("0")
        for field in (
            "contact_address1", "contact_address2", "contact_address3",
            "contact_address4", "contact_address5",
            "perm_address1", "perm_address2", "perm_address3",
            "perm_address4", "perm_address5",
            "old_software_id", "remarks", "phone", "mobile", "mobile2",
            "scheme", "aadhar_no",
        ):
            getattr(self, field).clear()
        self.dob.setDate(QDate.currentDate())
        self._update_age()
        self.sex.setCurrentIndex(0)
        # New registrations default to Existing? = N so a fresh patient_no is expected.
        self.existing.setCurrentIndex(1)
        self._sync_remarks_field()
        self.patient_type.setCurrentIndex(0)
        self.title.setCurrentIndex(0)
        self.hospital_section.setCurrentIndex(0)
        self._set_form_enabled(True)
        self.edit_btn.setEnabled(False)
        self._pending_aadhar_scan = None
        self.aadhar_scan_status.setText("No scan")
        self._set_status("Form cleared. Ready for new patient.")
        self._update_id_format_info()

    def _fill_form(self, patient: dict) -> None:
        self._current_patient_id = patient.get("id")
        self.patient_no.setText(patient.get("patient_no", ""))
        section_id = patient.get("hospital_section_id")
        if section_id:
            idx = self.hospital_section.findData(section_id)
            if idx >= 0:
                self.hospital_section.setCurrentIndex(idx)
            elif patient.get("hospital_section_name") or patient.get("facility"):
                label = patient.get("hospital_section_name") or patient.get("facility")
                self.hospital_section.addItem(label, section_id)
                self.hospital_section.setCurrentIndex(self.hospital_section.count() - 1)
        elif patient.get("facility"):
            self.hospital_section.addItem(patient.get("facility"), None)
            self.hospital_section.setCurrentIndex(self.hospital_section.count() - 1)
        self._set_combo_text(self.title, patient.get("title") or "Mr")
        self.first_name.setText(patient.get("first_name", ""))
        self.middle_name.setText(patient.get("middle_name") or "")
        self.last_name.setText(patient.get("last_name") or "")

        dob = patient.get("date_of_birth")
        if dob:
            parts = str(dob).split("-")
            if len(parts) == 3:
                self.dob.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self._update_age()
        stored_age = str(patient.get("age") or "").strip()
        if stored_age:
            # Prefer the age as originally entered/saved over a value recomputed
            # from DOB (they can differ slightly when DOB is only approximate).
            self._syncing_age = True
            try:
                self.age.setText(stored_age)
            finally:
                self._syncing_age = False

        self._set_combo_text(self.sex, patient.get("gender", "M"))
        bg = patient.get("blood_group") or ""
        bg_idx = self.blood_group.findData(bg)
        if bg_idx >= 0:
            self.blood_group.setCurrentIndex(bg_idx)
        elif bg:
            self.blood_group.addItem(bg, bg)
            self.blood_group.setCurrentIndex(self.blood_group.count() - 1)
        else:
            self.blood_group.setCurrentIndex(0)
        self.village_code.setText(patient.get("village_code") or "0")
        self.contact_address1.setText(patient.get("contact_address1") or "")
        self.contact_address2.setText(patient.get("contact_address2") or "")
        self.contact_address3.setText(patient.get("contact_address3") or "")
        self.contact_address4.setText(patient.get("contact_address4") or "")
        self.contact_address5.setText(patient.get("contact_address5") or "")
        self.perm_address1.setText(patient.get("perm_address1") or "")
        self.perm_address2.setText(patient.get("perm_address2") or "")
        self.perm_address3.setText(patient.get("perm_address3") or "")
        self.perm_address4.setText(patient.get("perm_address4") or "")
        self.perm_address5.setText(patient.get("perm_address5") or "")
        self.old_software_id.setText(patient.get("old_software_id") or "")
        self.remarks.setText(patient.get("remarks") or "")
        self.phone.setText(patient.get("phone") or "")
        self.mobile.setText(patient.get("mobile") or "")
        self.mobile2.setText(patient.get("mobile2") or "")
        self.scheme.setText(patient.get("scheme") or "")
        self.aadhar_no.setText(patient.get("aadhar_no") or "")
        self._pending_aadhar_scan = None
        self._update_aadhar_scan_status(patient)
        self.existing.blockSignals(True)
        self.existing.setCurrentIndex(0 if patient.get("is_existing_patient") else 1)
        self.existing.blockSignals(False)
        self._set_combo_text(self.patient_type, patient.get("patient_type") or "General")
        self.edit_btn.setEnabled(True)
        self._set_form_enabled(False)
        self.id_format_label.setText("Assigned patient ID (existing record).")

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.addItem(text)
            combo.setCurrentIndex(combo.count() - 1)

    def _pick_aadhar_scan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Aadhar Scan",
            "",
            "Documents (*.pdf *.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        self._pending_aadhar_scan = path
        self.aadhar_scan_status.setText(Path(path).name)
        if self._current_patient_id:
            uploaded, error = self.controller.upload_aadhar_scan(self._current_patient_id, path)
            if error:
                QMessageBox.warning(self, "Aadhar Scan", error)
                return
            self._pending_aadhar_scan = None
            self._update_aadhar_scan_status(uploaded or {})
            self._set_status("Aadhar scan uploaded.")

    def _view_aadhar_scan(self) -> None:
        if self._pending_aadhar_scan:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._pending_aadhar_scan))
            return
        if not self._current_patient_id:
            QMessageBox.information(self, "Aadhar Scan", "Save or load a patient first.")
            return
        api = self.controller._api
        try:
            response = httpx.get(
                api.patient_aadhar_scan_url(self._current_patient_id),
                headers=api._headers(),
                timeout=15,
            )
            if response.status_code != 200:
                QMessageBox.information(self, "Aadhar Scan", "No Aadhar scan uploaded yet.")
                return
            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type:
                suffix = ".pdf"
            elif "png" in content_type:
                suffix = ".png"
            elif "webp" in content_type:
                suffix = ".webp"
            else:
                suffix = ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                temp_path = tmp.name
            QDesktopServices.openUrl(QUrl.fromLocalFile(temp_path))
        except Exception as exc:
            QMessageBox.warning(self, "Aadhar Scan", str(exc))

    def _update_aadhar_scan_status(self, patient: dict) -> None:
        scan_path = patient.get("aadhar_scan_path")
        if scan_path:
            self.aadhar_scan_status.setText(Path(scan_path).name)
        else:
            self.aadhar_scan_status.setText("No scan")

    def _search_patient(self) -> None:
        patient = pick_patient(
            self.controller.api,
            self,
            initial_patient_no=self.search_input.text().strip(),
        )
        if not patient:
            return
        self._fill_form(patient)
        self._set_status(f"Loaded patient {patient.get('patient_no')}")

    def _load_hospital_sections(self) -> None:
        current = self.hospital_section.currentData()
        self.hospital_section.clear()
        self.hospital_section.addItem("— Select Section —", None)
        for section in get_session().cache.hospital_sections:
            self.hospital_section.addItem(section.get("name", ""), section.get("id"))
        if current:
            idx = self.hospital_section.findData(current)
            if idx >= 0:
                self.hospital_section.setCurrentIndex(idx)

    def prepare_for_new(self) -> None:
        self._clear_form()
        self.refresh()

    def refresh(self) -> None:
        self._load_hospital_sections()
        if not self._current_patient_id:
            QTimer.singleShot(0, self._update_id_format_info)
        self._set_status("Ready.")
