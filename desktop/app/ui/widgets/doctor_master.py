from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_doctors_cache
from app.session import get_session
from app.ui.components.collapsible_section import CollapsibleSection
from app.ui.styles import BORDER, INPUT_BG, PRIMARY, SURFACE


class DoctorMasterWidget(QWidget):
    MODE_CREATE = "Create Doctor"
    MODE_MODIFY = "Modify Doctor"
    MODE_DELETE = "Delete Doctor"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._doctors: list[dict] = []
        self._departments: list[dict] = []
        self._selected_id: str | None = None
        self._pending_photo: str | None = None
        self._pending_certificate: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        heading = QLabel("Doctor Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)

        self.doctor_combo = QComboBox()
        self.doctor_combo.setEnabled(False)
        self.doctor_combo.currentIndexChanged.connect(self._on_doctor_selected)
        top.addWidget(QLabel("Select Doctor"))
        top.addWidget(self.doctor_combo, stretch=1)
        layout.addLayout(top)

        header_row = QHBoxLayout()
        id_box = QGroupBox("Doctor ID")
        id_grid = QGridLayout(id_box)
        id_grid.setHorizontalSpacing(10)
        id_grid.setVerticalSpacing(8)

        self.doctor_code = QLineEdit()
        self.doctor_code.setReadOnly(True)
        self.doctor_code.setPlaceholderText("Generated on Save")
        self.doctor_code.setMinimumWidth(120)
        self.doctor_code.setMaximumWidth(160)
        self.title = QComboBox()
        self.title.addItems(["Dr", "Mr", "Mrs", "Ms", "Prof"])
        self.title.setMinimumWidth(70)
        self.title.setMaximumWidth(90)
        self.first_name = QLineEdit()
        self.second_name = QLineEdit()
        self.third_name = QLineEdit()
        for name_field in (self.first_name, self.second_name, self.third_name):
            name_field.setProperty("hmsAllowWide", True)
            name_field.setMinimumWidth(180)
            name_field.setMaximumWidth(16777215)
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("dd-MM-yyyy")
        self.dob.setDate(QDate(1980, 1, 1))
        self.dob.dateChanged.connect(self._update_age)
        self.age_label = QLabel("0")
        self.sex = QComboBox()
        self.sex.addItems(["M", "F", "O"])
        self.sex.setMaximumWidth(70)

        id_grid.addWidget(QLabel("Code"), 0, 0)
        id_grid.addWidget(self.doctor_code, 0, 1)
        id_grid.addWidget(QLabel("First Name *"), 0, 2)
        id_grid.addWidget(self.first_name, 0, 3)
        id_grid.addWidget(QLabel("Second Name"), 0, 4)
        id_grid.addWidget(self.second_name, 0, 5)

        id_grid.addWidget(QLabel("Title"), 1, 0)
        id_grid.addWidget(self.title, 1, 1)
        id_grid.addWidget(QLabel("Third Name"), 1, 2)
        id_grid.addWidget(self.third_name, 1, 3)
        id_grid.addWidget(QLabel("Date of Birth"), 1, 4)
        id_grid.addWidget(self.dob, 1, 5)

        id_grid.addWidget(QLabel("Age"), 2, 2)
        id_grid.addWidget(self.age_label, 2, 3)
        id_grid.addWidget(QLabel("Sex"), 2, 4)
        id_grid.addWidget(self.sex, 2, 5)

        id_grid.setColumnStretch(1, 1)
        id_grid.setColumnStretch(3, 3)
        id_grid.setColumnStretch(5, 3)
        header_row.addWidget(id_box, stretch=3)

        photo_box = QGroupBox("Photo")
        photo_layout = QVBoxLayout(photo_box)
        self.photo_label = QLabel("No photo")
        self.photo_label.setFixedSize(120, 120)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet(
            f"border: 2px solid {BORDER}; background: {INPUT_BG}; border-radius: 6px;"
        )
        photo_btn = QPushButton("Upload Photo")
        photo_btn.clicked.connect(self._pick_photo)
        photo_layout.addWidget(self.photo_label, alignment=Qt.AlignmentFlag.AlignCenter)
        photo_layout.addWidget(photo_btn)
        header_row.addWidget(photo_box)
        layout.addLayout(header_row)

        address_section = CollapsibleSection("Address Details", expanded=True)
        addresses = QHBoxLayout()
        perm = QGroupBox("Permanent Address")
        perm_form = QFormLayout(perm)
        perm_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.perm_village = QLineEdit()
        self.perm_post = QLineEdit()
        self.perm_taluk = QLineEdit()
        self.perm_district = QLineEdit()
        self.perm_pincode = QLineEdit()
        for field in (
            self.perm_village,
            self.perm_post,
            self.perm_taluk,
            self.perm_district,
            self.perm_pincode,
        ):
            field.setProperty("hmsAllowWide", True)
            field.setMinimumWidth(200)
            field.setMaximumWidth(16777215)
        perm_form.addRow("Village", self.perm_village)
        perm_form.addRow("Post", self.perm_post)
        perm_form.addRow("Taluk", self.perm_taluk)
        perm_form.addRow("District", self.perm_district)
        perm_form.addRow("Pincode", self.perm_pincode)
        addresses.addWidget(perm)

        temp = QGroupBox("Temporary Address")
        temp_form = QFormLayout(temp)
        temp_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.temp_village = QLineEdit()
        self.temp_post = QLineEdit()
        self.temp_taluk = QLineEdit()
        self.temp_district = QLineEdit()
        self.temp_pincode = QLineEdit()
        for field in (
            self.temp_village,
            self.temp_post,
            self.temp_taluk,
            self.temp_district,
            self.temp_pincode,
        ):
            field.setProperty("hmsAllowWide", True)
            field.setMinimumWidth(200)
            field.setMaximumWidth(16777215)
        temp_form.addRow("Village", self.temp_village)
        temp_form.addRow("Post", self.temp_post)
        temp_form.addRow("Taluk", self.temp_taluk)
        temp_form.addRow("District", self.temp_district)
        temp_form.addRow("Pincode", self.temp_pincode)
        addresses.addWidget(temp)
        address_section.content_layout.addLayout(addresses)
        layout.addWidget(address_section)
        self._address_section = address_section

        professional_section = CollapsibleSection("Professional & Contact", expanded=True)
        prof_form = QGridLayout()
        self.remarks = QLineEdit()
        self.phone = QLineEdit()
        self.mobile = QLineEdit()
        self.mobile2 = QLineEdit()
        self.join_date = QDateEdit()
        self.join_date.setCalendarPopup(True)
        self.join_date.setDisplayFormat("dd-MM-yyyy")
        self.qualification = QLineEdit()
        self.department = QComboBox()
        self.is_existing = QComboBox()
        self.is_existing.addItems(["Y", "N"])
        self.release_date = QDateEdit()
        self.release_date.setCalendarPopup(True)
        self.release_date.setDisplayFormat("dd-MM-yyyy")
        self.register_no = QLineEdit()
        self.is_reference = QComboBox()
        self.is_reference.addItems(["N", "Y"])
        self.is_pathology = QComboBox()
        self.is_pathology.addItems(["N", "Y"])
        self.certificate_label = QLabel("No certificate uploaded")
        cert_btn = QPushButton("Upload Certificate")
        cert_btn.clicked.connect(self._pick_certificate)

        for field in (
            self.remarks,
            self.phone,
            self.mobile,
            self.mobile2,
            self.qualification,
            self.register_no,
            self.department,
        ):
            field.setProperty("hmsAllowWide", True)
            field.setMinimumWidth(160)
            field.setMaximumWidth(16777215)

        prof_form.addWidget(QLabel("Remarks"), 0, 0)
        prof_form.addWidget(self.remarks, 0, 1, 1, 3)
        prof_form.addWidget(QLabel("Phone"), 1, 0)
        prof_form.addWidget(self.phone, 1, 1)
        prof_form.addWidget(QLabel("Mobile"), 1, 2)
        prof_form.addWidget(self.mobile, 1, 3)
        prof_form.addWidget(QLabel("Mobile 2"), 2, 0)
        prof_form.addWidget(self.mobile2, 2, 1)
        prof_form.addWidget(QLabel("Join Date"), 2, 2)
        prof_form.addWidget(self.join_date, 2, 3)
        prof_form.addWidget(QLabel("Qualification"), 3, 0)
        prof_form.addWidget(self.qualification, 3, 1)
        prof_form.addWidget(cert_btn, 3, 2)
        prof_form.addWidget(self.certificate_label, 3, 3)
        prof_form.addWidget(QLabel("Department"), 4, 0)
        prof_form.addWidget(self.department, 4, 1)
        prof_form.addWidget(QLabel("Existing"), 4, 2)
        prof_form.addWidget(self.is_existing, 4, 3)
        prof_form.addWidget(QLabel("Release Date"), 5, 0)
        prof_form.addWidget(self.release_date, 5, 1)
        prof_form.addWidget(QLabel("Register No"), 5, 2)
        prof_form.addWidget(self.register_no, 5, 3)
        prof_form.addWidget(QLabel("Reference Doctor"), 6, 0)
        prof_form.addWidget(self.is_reference, 6, 1)
        prof_form.addWidget(QLabel("Pathology Doctor"), 6, 2)
        prof_form.addWidget(self.is_pathology, 6, 3)
        prof_form.setColumnStretch(1, 2)
        prof_form.setColumnStretch(3, 2)
        professional_section.content_layout.addLayout(prof_form)
        layout.addWidget(professional_section)
        self._professional_section = professional_section

        token_section = CollapsibleSection("Token Settings", expanded=False)
        token_form = QGridLayout()
        token_hint = QLabel(
            "OPD and Reference use separate numeric queues per morning/evening "
            "(1, 2, 3…). Appointment and Online Booking have their own queues with a max slot limit."
        )
        token_hint.setWordWrap(True)
        token_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        self.appointment_max_slots = QSpinBox()
        self.appointment_max_slots.setRange(1, 9999)
        self.appointment_max_slots.setValue(5)
        self.online_booking_max_slots = QSpinBox()
        self.online_booking_max_slots.setRange(1, 9999)
        self.online_booking_max_slots.setValue(10)
        token_form.addWidget(token_hint, 0, 0, 1, 4)
        token_form.addWidget(QLabel("Appointment Max Slots"), 1, 0)
        token_form.addWidget(self.appointment_max_slots, 1, 1)
        token_form.addWidget(QLabel("(per doctor / date / morning or evening)"), 1, 2, 1, 2)
        token_form.addWidget(QLabel("Online Booking Max Slots"), 2, 0)
        token_form.addWidget(self.online_booking_max_slots, 2, 1)
        token_form.addWidget(QLabel("(per doctor / date / morning or evening)"), 2, 2, 1, 2)
        token_section.content_layout.addLayout(token_form)
        layout.addWidget(token_section)
        self._token_section = token_section

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Code", "Name", "Department", "Mobile", "Ref Dr", "Pathology"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

        scroll.setWidget(body)
        outer.addWidget(scroll)
        self._on_mode_changed(self.mode_combo.currentText())

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loading or not cache.loaded:
            return
        try:
            refresh_doctors_cache(self.api)
        except ApiError:
            pass
        self._doctors = list(get_session().cache.doctors)
        self._departments = list(cache.departments)
        self._load_departments()
        self._load_table()
        self._load_doctor_combo()

    def _load_departments(self) -> None:
        current = self.department.currentData()
        self.department.clear()
        self.department.addItem("— Select —", None)
        for dept in self._departments:
            self.department.addItem(dept["name"], dept["id"])
        if current:
            idx = self.department.findData(current)
            if idx >= 0:
                self.department.setCurrentIndex(idx)

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._doctors))
        for row, doc in enumerate(self._doctors):
            self.table.setItem(row, 0, QTableWidgetItem(doc.get("doctor_code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(doc.get("full_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(doc.get("department_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(doc.get("mobile") or doc.get("phone") or ""))
            self.table.setItem(row, 4, QTableWidgetItem("Y" if doc.get("is_reference_doctor") else "N"))
            self.table.setItem(row, 5, QTableWidgetItem("Y" if doc.get("is_pathology_doctor") else "N"))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, doc.get("id"))

    def _load_doctor_combo(self) -> None:
        current = self.doctor_combo.currentData()
        self.doctor_combo.clear()
        self.doctor_combo.addItem("— Select —", None)
        for doc in self._doctors:
            self.doctor_combo.addItem(f"{doc.get('doctor_code')} — {doc.get('full_name')}", doc.get("id"))
        if current:
            idx = self.doctor_combo.findData(current)
            if idx >= 0:
                self.doctor_combo.setCurrentIndex(idx)

    def _update_age(self) -> None:
        qd = self.dob.date()
        today = date.today()
        age = today.year - qd.year() - ((today.month, today.day) < (qd.month(), qd.day()))
        self.age_label.setText(str(max(age, 0)))

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.doctor_combo.setEnabled(not is_create)
        self.save_btn.setText("Delete Doctor" if is_delete else "Save")
        enabled = not is_delete
        for widget in (
            self.title, self.first_name, self.second_name, self.third_name, self.dob, self.sex,
            self.perm_village, self.perm_post, self.perm_taluk, self.perm_district, self.perm_pincode,
            self.temp_village, self.temp_post, self.temp_taluk, self.temp_district, self.temp_pincode,
            self.remarks, self.phone, self.mobile, self.mobile2, self.join_date, self.qualification,
            self.department, self.is_existing, self.release_date, self.register_no,
            self.appointment_max_slots, self.online_booking_max_slots,
            self.is_reference, self.is_pathology,
        ):
            widget.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_doctor_selected(self) -> None:
        doctor_id = self.doctor_combo.currentData()
        if doctor_id:
            self._load_doctor(doctor_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        doctor_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if not doctor_id:
            return
        # Clicking a row always opens that doctor for edit (not create).
        if self.mode_combo.currentText() == self.MODE_CREATE:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText(self.MODE_MODIFY)
            self.mode_combo.blockSignals(False)
            self._on_mode_changed(self.MODE_MODIFY)
        idx = self.doctor_combo.findData(doctor_id)
        if idx >= 0:
            self.doctor_combo.setCurrentIndex(idx)

    def _load_doctor(self, doctor_id: str) -> None:
        try:
            doc = self.api.get_doctor(doctor_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._selected_id = doctor_id
        self.doctor_code.setText(doc.get("doctor_code", ""))
        title_idx = self.title.findText(doc.get("title") or "Dr")
        if title_idx >= 0:
            self.title.setCurrentIndex(title_idx)
        self.first_name.setText(doc.get("first_name", ""))
        self.second_name.setText(doc.get("second_name") or "")
        self.third_name.setText(doc.get("third_name") or "")
        if doc.get("date_of_birth"):
            parts = doc["date_of_birth"].split("-")
            self.dob.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        sex_idx = self.sex.findText(doc.get("sex") or "M")
        if sex_idx >= 0:
            self.sex.setCurrentIndex(sex_idx)
        self._update_age()
        self.perm_village.setText(doc.get("perm_village") or "")
        self.perm_post.setText(doc.get("perm_post") or "")
        self.perm_taluk.setText(doc.get("perm_taluk") or "")
        self.perm_district.setText(doc.get("perm_district") or "")
        self.perm_pincode.setText(doc.get("perm_pincode") or "")
        self.temp_village.setText(doc.get("temp_village") or "")
        self.temp_post.setText(doc.get("temp_post") or "")
        self.temp_taluk.setText(doc.get("temp_taluk") or "")
        self.temp_district.setText(doc.get("temp_district") or "")
        self.temp_pincode.setText(doc.get("temp_pincode") or "")
        self.remarks.setText(doc.get("remarks") or "")
        self.phone.setText(doc.get("phone") or "")
        self.mobile.setText(doc.get("mobile") or "")
        self.mobile2.setText(doc.get("mobile2") or "")
        if doc.get("join_date"):
            p = doc["join_date"].split("-")
            self.join_date.setDate(QDate(int(p[0]), int(p[1]), int(p[2])))
        self.qualification.setText(doc.get("qualification") or "")
        dept_idx = self.department.findData(doc.get("department_id"))
        if dept_idx >= 0:
            self.department.setCurrentIndex(dept_idx)
        self.is_existing.setCurrentText("Y" if doc.get("is_existing", True) else "N")
        if doc.get("release_date"):
            p = doc["release_date"].split("-")
            self.release_date.setDate(QDate(int(p[0]), int(p[1]), int(p[2])))
        self.register_no.setText(doc.get("register_no") or "")
        self.appointment_max_slots.setValue(int(doc.get("appointment_token_end") or 5))
        self.online_booking_max_slots.setValue(int(doc.get("online_booking_token_end") or 10))
        self.is_reference.setCurrentText("Y" if doc.get("is_reference_doctor") else "N")
        self.is_pathology.setCurrentText("Y" if doc.get("is_pathology_doctor") else "N")
        self.certificate_label.setText(
            Path(doc["certificate_path"]).name if doc.get("certificate_path") else "No certificate uploaded"
        )
        self._pending_photo = None
        self._pending_certificate = None
        self._load_photo_preview(doctor_id)
        self._sync_section_expansion(doc)

    def _load_photo_preview(self, doctor_id: str) -> None:
        if self._pending_photo:
            pix = QPixmap(self._pending_photo)
            if not pix.isNull():
                self.photo_label.setPixmap(pix.scaled(118, 118, Qt.AspectRatioMode.KeepAspectRatio))
                return
        try:
            url = self.api.doctor_photo_url(doctor_id)
            import httpx
            response = httpx.get(url, headers=self.api._headers(), timeout=10)
            if response.status_code == 200 and response.content:
                pix = QPixmap()
                pix.loadFromData(response.content)
                if not pix.isNull():
                    self.photo_label.setPixmap(pix.scaled(118, 118, Qt.AspectRatioMode.KeepAspectRatio))
                    return
        except Exception:
            pass
        self.photo_label.setText("No photo")

    def _pick_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._pending_photo = path
            pix = QPixmap(path)
            if not pix.isNull():
                self.photo_label.setPixmap(pix.scaled(118, 118, Qt.AspectRatioMode.KeepAspectRatio))

    def _pick_certificate(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Certificate", "", "Documents (*.pdf *.png *.jpg *.jpeg)"
        )
        if path:
            self._pending_certificate = path
            self.certificate_label.setText(Path(path).name)

    def _clear_form(self) -> None:
        self._selected_id = None
        self._pending_photo = None
        self._pending_certificate = None
        self.doctor_code.clear()
        self.title.setCurrentIndex(0)
        for field in (
            self.first_name, self.second_name, self.third_name, self.remarks, self.phone,
            self.mobile, self.mobile2, self.qualification, self.register_no,
            self.perm_village, self.perm_post, self.perm_taluk, self.perm_district, self.perm_pincode,
            self.temp_village, self.temp_post, self.temp_taluk, self.temp_district, self.temp_pincode,
        ):
            field.clear()
        self.department.setCurrentIndex(0)
        self.is_existing.setCurrentIndex(0)
        self.is_reference.setCurrentIndex(0)
        self.is_pathology.setCurrentIndex(0)
        self.appointment_max_slots.setValue(5)
        self.online_booking_max_slots.setValue(10)
        self.photo_label.setText("No photo")
        self.certificate_label.setText("No certificate uploaded")
        self.doctor_combo.setCurrentIndex(0)
        self.table.clearSelection()
        self._update_age()
        # Keep address / professional open so fields stay editable after clear.
        self._address_section.set_expanded(True)
        self._professional_section.set_expanded(True)
        self._token_section.set_expanded(False)

    def _sync_section_expansion(self, doc: dict) -> None:
        # Always keep the main edit sections open when loading a doctor.
        has_token_settings = (
            int(doc.get("appointment_token_end") or 5) != 5
            or int(doc.get("online_booking_token_end") or 10) != 10
        )
        self._address_section.set_expanded(True)
        self._professional_section.set_expanded(True)
        self._token_section.set_expanded(has_token_settings)

    def _payload(self) -> dict | None:
        if not self.first_name.text().strip():
            QMessageBox.warning(self, "Validation", "First name is required.")
            return None
        return {
            "title": self.title.currentText(),
            "first_name": self.first_name.text().strip(),
            "second_name": self.second_name.text().strip() or None,
            "third_name": self.third_name.text().strip() or None,
            "date_of_birth": self.dob.date().toString("yyyy-MM-dd"),
            "sex": self.sex.currentText(),
            "perm_village": self.perm_village.text().strip() or None,
            "perm_post": self.perm_post.text().strip() or None,
            "perm_taluk": self.perm_taluk.text().strip() or None,
            "perm_district": self.perm_district.text().strip() or None,
            "perm_pincode": self.perm_pincode.text().strip() or None,
            "temp_village": self.temp_village.text().strip() or None,
            "temp_post": self.temp_post.text().strip() or None,
            "temp_taluk": self.temp_taluk.text().strip() or None,
            "temp_district": self.temp_district.text().strip() or None,
            "temp_pincode": self.temp_pincode.text().strip() or None,
            "is_reference_doctor": self.is_reference.currentText() == "Y",
            "is_pathology_doctor": self.is_pathology.currentText() == "Y",
            "remarks": self.remarks.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "mobile": self.mobile.text().strip() or None,
            "mobile2": self.mobile2.text().strip() or None,
            "join_date": self.join_date.date().toString("yyyy-MM-dd"),
            "qualification": self.qualification.text().strip() or None,
            "department_id": self.department.currentData(),
            "is_existing": self.is_existing.currentText() == "Y",
            "release_date": (
                self.release_date.date().toString("yyyy-MM-dd")
                if self.is_existing.currentText() == "N"
                else None
            ),
            "register_no": self.register_no.text().strip() or None,
            "morning_token_start": 1,
            "evening_token_start": 1,
            "appointment_token_start": 1,
            "appointment_token_end": self.appointment_max_slots.value(),
            "online_booking_token_start": 1,
            "online_booking_token_end": self.online_booking_max_slots.value(),
        }

    def _upload_pending(self, doctor_id: str) -> None:
        if self._pending_photo:
            self.api.upload_doctor_photo(doctor_id, self._pending_photo)
        if self._pending_certificate:
            self.api.upload_doctor_certificate(doctor_id, self._pending_certificate)

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            doctor_id = self.doctor_combo.currentData() or self._selected_id
            if not doctor_id:
                QMessageBox.warning(self, "Validation", "Select a doctor to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this doctor?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_doctor(doctor_id)
                QMessageBox.information(self, "Success", "Doctor deactivated.")
                self._clear_form()
                refresh_doctors_cache(self.api)
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        payload = self._payload()
        if not payload:
            return
        try:
            if mode == self.MODE_CREATE:
                doc = self.api.create_doctor(payload)
                doctor_id = doc["id"]
                self.doctor_code.setText(doc.get("doctor_code", ""))
                self._upload_pending(doctor_id)
                QMessageBox.information(self, "Success", f"Doctor saved. ID: {doc.get('doctor_code')}")
                self.mode_combo.setCurrentText(self.MODE_CREATE)
                self._clear_form()
            else:
                doctor_id = self.doctor_combo.currentData() or self._selected_id
                if not doctor_id:
                    QMessageBox.warning(self, "Validation", "Select a doctor to modify.")
                    return
                doc = self.api.update_doctor(doctor_id, payload)
                self._upload_pending(doctor_id)
                QMessageBox.information(self, "Success", "Doctor updated.")
            refresh_doctors_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
