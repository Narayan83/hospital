from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.components.date_edit import style_date_field
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.responsive_layout import (
    configure_form_layout,
    configure_splitter,
    create_scroll_panel,
)
from app.ui.styles import BORDER, HEADER_BTN_STYLE, TABLE_COMPACT_STYLE

CONDITION_OPTIONS = ["", "Stable", "Improved", "Against Medical Advice", "Referred", "Expired"]
SUMMARY_PAGE_SIZE = 15
CLINICAL_ROW_HEIGHT = 26
CLINICAL_ROW_FOCUS_HEIGHT = 88
CLINICAL_TABLE_STYLE = TABLE_COMPACT_STYLE + f"""
QTableWidget {{
    border: 1px solid {BORDER};
    border-radius: 2px;
    gridline-color: #b8c4d4;
}}
QHeaderView::section {{
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid #b8c4d4;
}}
QTextEdit {{
    border: none;
    background: transparent;
    font-size: 11px;
    padding: 1px 4px;
}}
QTextEdit:focus {{
    background: #ffffff;
}}
"""


def _left_field_style() -> str:
    from app.ui.styles import compact_field_style, form_field_style

    return form_field_style() + compact_field_style()


def _left_field_height() -> int:
    from app.ui.styles import left_pane_field_height

    return left_pane_field_height()


LEFT_FIELD_STYLE = _left_field_style()
LEFT_FIELD_HEIGHT = _left_field_height()

_pending_admission: dict | None = None


def set_pending_admission(admission: dict | None) -> None:
    global _pending_admission
    _pending_admission = admission


def consume_pending_admission() -> dict | None:
    global _pending_admission
    admission = _pending_admission
    _pending_admission = None
    return admission


class DischargeSummaryWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._admission: dict | None = None
        self._saved_summary_id: str | None = None
        self._build_ui()

    def _configure_left_form(self, form: QFormLayout) -> None:
        configure_form_layout(form, wrap_all=True)

    def _style_left_field(self, field) -> None:
        if isinstance(field, QDateEdit):
            style_date_field(
                field,
                compact=True,
                fixed_height=LEFT_FIELD_HEIGHT,
                min_width=120,
                extra_style=LEFT_FIELD_STYLE,
            )
            return
        field.setStyleSheet(LEFT_FIELD_STYLE)
        field.setFixedHeight(LEFT_FIELD_HEIGHT)
        field.setMinimumWidth(120)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = splitter
        outer.addWidget(splitter, stretch=1)
        configure_splitter(splitter, left_ratio=0.30)

        left_scroll, left_host, left_layout = create_scroll_panel()

        patient_required_box = QGroupBox("Patient")
        patient_required_form = QFormLayout(patient_required_box)
        self._configure_left_form(patient_required_form)
        pid_row = QHBoxLayout()
        self.patient_id_input = QLineEdit()
        self.patient_id_input.setPlaceholderText("Patient Id (required)")
        self.patient_id_input.editingFinished.connect(self._on_patient_id_editing_finished)
        self._style_left_field(self.patient_id_input)
        search_btn = QPushButton("Search")
        search_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        search_btn.clicked.connect(self._lookup_patient)
        pick_btn = QPushButton("Pick Patient")
        pick_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        pick_btn.clicked.connect(self._pick_patient)
        pid_row.addWidget(self.patient_id_input, stretch=1)
        pid_row.addWidget(search_btn)
        pid_row.addWidget(pick_btn)
        patient_required_form.addRow("Patient Id *", pid_row)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self._style_left_field(self.patient_name)
        patient_required_form.addRow("Patient Name", self.patient_name)
        left_layout.addWidget(patient_required_box)

        patient_box = QGroupBox("Admission Details (Optional)")
        patient_form = QFormLayout(patient_box)
        self._configure_left_form(patient_form)
        self.patient_box = patient_box
        patient_box.setCheckable(True)
        patient_box.setChecked(False)
        patient_box.toggled.connect(self._on_admission_box_toggled)
        adm_btn_row = QHBoxLayout()
        find_adm_btn = QPushButton("Find Admission")
        find_adm_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        find_adm_btn.clicked.connect(self._find_admission)
        adm_btn_row.addWidget(find_adm_btn)
        adm_btn_row.addStretch()
        patient_form.addRow("", adm_btn_row)
        self.admission_no = QLineEdit()
        self.admission_no.setReadOnly(True)
        self.ward_name = QLineEdit()
        self.ward_name.setReadOnly(True)
        self._style_left_field(self.admission_no)
        self._style_left_field(self.ward_name)
        patient_form.addRow("Admission No", self.admission_no)
        patient_form.addRow("Ward", self.ward_name)
        left_layout.addWidget(patient_box)

        summary_box = QGroupBox("Summary Details")
        summary_form = QFormLayout(summary_box)
        self._configure_left_form(summary_form)
        self.summary_no = QLineEdit()
        self.summary_no.setReadOnly(True)
        self.summary_no.setPlaceholderText("Assigned on Save")
        self.summary_date = QDateEdit()
        self.summary_date.setCalendarPopup(True)
        self.summary_date.setDisplayFormat("dd/MM/yyyy")
        self.summary_date.setDate(QDate.currentDate())
        self.admission_date = QDateEdit()
        self.admission_date.setCalendarPopup(True)
        self.admission_date.setDisplayFormat("dd/MM/yyyy")
        self.admission_date.setDate(QDate.currentDate())
        self.discharge_date = QDateEdit()
        self.discharge_date.setCalendarPopup(True)
        self.discharge_date.setDisplayFormat("dd/MM/yyyy")
        self.discharge_date.setDate(QDate.currentDate())
        self.doctor = QComboBox()
        self.condition = QComboBox()
        self.condition.addItems(CONDITION_OPTIONS)
        for field in (
            self.summary_no,
            self.doctor,
            self.condition,
        ):
            self._style_left_field(field)
        for field in (self.summary_date, self.admission_date, self.discharge_date):
            style_date_field(
                field,
                compact=True,
                fixed_height=LEFT_FIELD_HEIGHT,
                min_width=96,
                extra_style=LEFT_FIELD_STYLE,
            )
        summary_form.addRow("Summary No", self.summary_no)

        dates_row = QHBoxLayout()
        dates_row.setContentsMargins(0, 0, 0, 0)
        dates_row.setSpacing(6)

        def _date_cell(label_text: str, field: QDateEdit) -> QWidget:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 11px; color: #475569;")
            cell_layout.addWidget(label)
            cell_layout.addWidget(field)
            return cell

        dates_row.addWidget(_date_cell("Summary Date", self.summary_date), stretch=1)
        dates_row.addWidget(_date_cell("Admission Date *", self.admission_date), stretch=1)
        dates_row.addWidget(_date_cell("Discharge Date *", self.discharge_date), stretch=1)
        dates_host = QWidget()
        dates_host.setLayout(dates_row)
        summary_form.addRow(dates_host)

        summary_form.addRow("Doctor *", self.doctor)
        summary_form.addRow("Condition on Discharge", self.condition)
        left_layout.addWidget(summary_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.save_btn = QPushButton("Save Summary")
        self.save_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.save_btn.clicked.connect(self._save_summary)
        self.print_btn = QPushButton("Print Summary")
        self.print_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.print_btn.clicked.connect(self._print_summary)
        self.reprint_btn = QPushButton("Reprint")
        self.reprint_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.reprint_btn.clicked.connect(self._preview_summary)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        clear_btn.clicked.connect(self._clear_form)
        self.history_btn = QPushButton("Get Old Summary")
        self.history_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.history_btn.clicked.connect(self._show_old_summaries_dialog)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addWidget(self.reprint_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self.history_btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)

        guide_box = QGroupBox("How to use")
        guide_box.setStyleSheet(
            "QGroupBox { font-size: 11px; font-weight: 600; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px; }"
        )
        guide_layout = QVBoxLayout(guide_box)
        guide_layout.setContentsMargins(8, 6, 8, 6)
        guide_layout.setSpacing(2)
        for line in (
            "1. Enter Patient Id → Search (or Pick Patient).",
            "2. Optional: tick Admission Details → Find Admission.",
            "3. Select Doctor, then type in Clinical Details on the right.",
            "4. Click a row to type. The selected row expands for extra lines.",
            "5. Save Summary → prints preview. Get Old Summary loads past records.",
        ):
            tip = QLabel(line)
            tip.setWordWrap(True)
            tip.setStyleSheet("font-size: 10px; color: #64748b; border: none;")
            guide_layout.addWidget(tip)
        left_layout.addWidget(guide_box)
        left_scroll.setWidget(left_host)
        splitter.addWidget(left_scroll)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 2, 2, 2)
        right_layout.setSpacing(6)

        clinical_header = QHBoxLayout()
        clinical_header.setSpacing(8)
        clinical_lbl = QLabel("Clinical Details")
        clinical_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        clinical_header.addWidget(clinical_lbl)
        clinical_header.addStretch()
        right_layout.addLayout(clinical_header)

        self.chief_complaint = self._make_clinical_editor("Chief complaint on admission")
        self.history_of_illness = self._make_clinical_editor("History of present illness")
        self.diagnosis_on_admission = self._make_clinical_editor("Provisional / admission diagnosis")
        self.final_diagnosis = self._make_clinical_editor("Final diagnosis at discharge")
        self.investigation = self._make_clinical_editor("Investigations done during stay")
        self.treatment_given = self._make_clinical_editor("Treatment / management given")
        self.procedures = self._make_clinical_editor("Procedures or surgery performed")
        self.medications = self._make_clinical_editor("Medications advised on discharge")
        self.advice_follow_up = self._make_clinical_editor("Follow-up advice and precautions")
        self.remarks = self._make_clinical_editor("Additional remarks")
        clinical_rows = (
            ("Chief Complaint", self.chief_complaint),
            ("History of Illness", self.history_of_illness),
            ("Diagnosis on Admission", self.diagnosis_on_admission),
            ("Final Diagnosis", self.final_diagnosis),
            ("Investigations", self.investigation),
            ("Treatment Given", self.treatment_given),
            ("Procedures", self.procedures),
            ("Medications on Discharge", self.medications),
            ("Advice & Follow-up", self.advice_follow_up),
            ("Remarks", self.remarks),
        )
        self._clinical_fields = [field for _label, field in clinical_rows]

        self.clinical_table = QTableWidget(len(clinical_rows), 2)
        self.clinical_table.setHorizontalHeaderLabels(["Particulars", "Details"])
        self.clinical_table.setProperty("hmsColumnKinds", ["text", "text"])
        self.clinical_table.setProperty("hmsStretchColumn", 1)
        self.clinical_table.setStyleSheet(CLINICAL_TABLE_STYLE)
        self.clinical_table.setAlternatingRowColors(True)
        self.clinical_table.setShowGrid(True)
        self.clinical_table.setWordWrap(False)
        self.clinical_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.clinical_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.clinical_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.clinical_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clinical_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v_header = self.clinical_table.verticalHeader()
        v_header.setDefaultSectionSize(CLINICAL_ROW_HEIGHT)
        v_header.setMinimumSectionSize(CLINICAL_ROW_HEIGHT)
        v_header.setFixedWidth(26)
        header = self.clinical_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clinical_table.setColumnWidth(0, 180)
        for row_idx, (label_text, field) in enumerate(clinical_rows):
            item = QTableWidgetItem(label_text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(label_text)
            self.clinical_table.setItem(row_idx, 0, item)
            self.clinical_table.setCellWidget(row_idx, 1, field)
            self.clinical_table.setRowHeight(row_idx, CLINICAL_ROW_HEIGHT)
            field.installEventFilter(self)
        self.clinical_table.cellClicked.connect(self._on_clinical_cell_clicked)
        right_layout.addWidget(self.clinical_table, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

    @staticmethod
    def _make_clinical_editor(placeholder: str) -> QTextEdit:
        field = QTextEdit()
        field.setPlaceholderText(placeholder)
        field.setAcceptRichText(False)
        field.setFrameShape(QFrame.Shape.NoFrame)
        field.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        field.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        field.setTabChangesFocus(True)
        field.document().setDocumentMargin(2)
        return field

    def _on_clinical_cell_clicked(self, row: int, _column: int) -> None:
        fields = getattr(self, "_clinical_fields", [])
        if 0 <= row < len(fields):
            fields[row].setFocus()

    def _set_clinical_row_height(self, field: QTextEdit, focused: bool) -> None:
        fields = getattr(self, "_clinical_fields", [])
        try:
            row = fields.index(field)
        except ValueError:
            return
        height = CLINICAL_ROW_FOCUS_HEIGHT if focused else CLINICAL_ROW_HEIGHT
        self.clinical_table.setRowHeight(row, height)

    def eventFilter(self, obj, event):
        if obj in getattr(self, "_clinical_fields", []):
            if event.type() == QEvent.Type.FocusIn:
                self._set_clinical_row_height(obj, True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_clinical_row_height(obj, False)
        return super().eventFilter(obj, event)

    def build_header_actions(self) -> QWidget:
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("Search Patient", self._lookup_patient),
                ("Find Admission", self._find_admission),
                ("Load by Summary No", self._load_by_summary_no),
                ("IPD Discharge", lambda: self._navigate("in_patient_discharge")),
            ]
        )

    def load_admission_context(self, admission: dict) -> None:
        if admission.get("patient_no"):
            self._apply_patient(
                {
                    "id": admission.get("patient_id"),
                    "patient_no": admission.get("patient_no"),
                    "patient_name": admission.get("patient_name"),
                }
            )
        self._load_admission(admission)
        admission_id = admission.get("id")
        if not admission_id:
            return
        try:
            summary = self.api.get_discharge_summary_by_admission(admission_id)
        except ApiError:
            if admission.get("diagnosis"):
                self.diagnosis_on_admission.setPlainText(str(admission["diagnosis"]))
            return
        self._load_summary(summary)

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def refresh(self) -> None:
        pending = consume_pending_admission()
        if pending:
            self.load_admission_context(pending)
        cache = get_session().cache
        self.doctor.clear()
        self.doctor.addItem("— Select Doctor —", None)
        doctors = cache.doctors if cache.loaded else []
        if not doctors:
            try:
                doctors = self.api.list_doctors(page_size=500).get("items", [])
            except ApiError:
                doctors = []
        for doc in doctors:
            self.doctor.addItem(doc.get("full_name") or doc.get("name", ""), doc.get("id"))

    @staticmethod
    def _set_date_field(field: QDateEdit, value: str | date | None) -> None:
        if not value:
            return
        if isinstance(value, date):
            field.setDate(QDate(value.year, value.month, value.day))
            return
        parts = str(value).split("-")
        if len(parts) == 3:
            field.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))

    @staticmethod
    def _date_field_iso(field: QDateEdit) -> str:
        qd = field.date()
        return date(qd.year(), qd.month(), qd.day()).isoformat()

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, parent=self)
        if not patient:
            return
        self._apply_patient(patient)
        self._lookup_patient()

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id_input.setText(patient.get("patient_no") or "")
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        name = " ".join(p for p in parts if p)
        self.patient_name.setText(name or patient.get("patient_name") or "")

    def _resolve_patient(self) -> dict | None:
        patient_no = self.patient_id_input.text().strip()
        if not patient_no:
            QMessageBox.warning(self, "Patient", "Enter a patient id first.")
            return None
        if self._patient and (self._patient.get("patient_no") or "").strip().upper() == patient_no.upper():
            return self._patient
        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                result = self.api.list_patients(search=patient_no, page_size=20)
                items = [
                    item
                    for item in (result.get("items") or [])
                    if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
                ]
            if not items:
                self._patient = None
                self.patient_name.clear()
                QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
                return None
            self._apply_patient(items[0])
            return items[0]
        except ApiError as exc:
            QMessageBox.warning(self, "Patient", str(exc))
            return None

    def _on_patient_id_editing_finished(self) -> None:
        if not self.patient_id_input.text().strip():
            return
        self._lookup_patient()

    def _lookup_patient(self) -> None:
        self._resolve_patient()

    def _show_old_summaries_dialog(self) -> None:
        patient = self._patient or self._resolve_patient()
        if not patient:
            return
        try:
            all_rows = self.api.list_discharge_summaries(patient_no=patient.get("patient_no"))
        except ApiError as exc:
            QMessageBox.warning(self, "Summaries", str(exc))
            return
        if not all_rows:
            QMessageBox.information(
                self,
                "Summaries",
                f"No discharge summaries found for {patient.get('patient_no')}.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Discharge Summaries — {patient.get('patient_no')}")
        dialog.resize(920, 500)
        layout = QVBoxLayout(dialog)

        info = QLabel(
            f"{len(all_rows)} record(s) — newest first. "
            f"Showing {SUMMARY_PAGE_SIZE} per page."
        )
        info.setStyleSheet("color: #64748b;")
        layout.addWidget(info)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Summary No", "Date", "Admission", "Discharge", "Diagnosis", "Doctor"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table, stretch=1)

        page_index = [0]

        nav_row = QHBoxLayout()
        prev_btn = QPushButton("◀ Previous")
        page_label = QLabel()
        next_btn = QPushButton("Next ▶")
        nav_row.addStretch()
        nav_row.addWidget(prev_btn)
        nav_row.addWidget(page_label)
        nav_row.addWidget(next_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        def _render_page() -> None:
            start = page_index[0] * SUMMARY_PAGE_SIZE
            chunk = all_rows[start : start + SUMMARY_PAGE_SIZE]
            table.setRowCount(len(chunk))
            for row_idx, item in enumerate(chunk):
                table.setItem(row_idx, 0, QTableWidgetItem(item.get("summary_no", "")))
                table.setItem(row_idx, 1, QTableWidgetItem(str(item.get("summary_date", ""))))
                table.setItem(row_idx, 2, QTableWidgetItem(item.get("admission_no") or ""))
                table.setItem(
                    row_idx, 3, QTableWidgetItem(str(item.get("discharge_date") or ""))
                )
                table.setItem(row_idx, 4, QTableWidgetItem(item.get("final_diagnosis") or ""))
                table.setItem(row_idx, 5, QTableWidgetItem(item.get("doctor_name") or ""))
                cell = table.item(row_idx, 0)
                if cell:
                    cell.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            total_pages = max(1, (len(all_rows) + SUMMARY_PAGE_SIZE - 1) // SUMMARY_PAGE_SIZE)
            page_label.setText(f"Page {page_index[0] + 1} of {total_pages}")
            prev_btn.setEnabled(page_index[0] > 0)
            next_btn.setEnabled(start + SUMMARY_PAGE_SIZE < len(all_rows))

        def _prev_page() -> None:
            if page_index[0] > 0:
                page_index[0] -= 1
                _render_page()

        def _next_page() -> None:
            if (page_index[0] + 1) * SUMMARY_PAGE_SIZE < len(all_rows):
                page_index[0] += 1
                _render_page()

        prev_btn.clicked.connect(_prev_page)
        next_btn.clicked.connect(_next_page)
        _render_page()

        selected_id: str | None = None

        def _accept_selection() -> None:
            nonlocal selected_id
            sel_rows = table.selectionModel().selectedRows()
            if not sel_rows:
                QMessageBox.information(dialog, "Select", "Choose a summary from the list.")
                return
            cell = table.item(sel_rows[0].row(), 0)
            if not cell:
                return
            summary_id = cell.data(Qt.ItemDataRole.UserRole)
            if not summary_id:
                return
            selected_id = summary_id
            dialog.accept()

        table.doubleClicked.connect(lambda _index: _accept_selection())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Open")
        buttons.accepted.connect(_accept_selection)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted or not selected_id:
            return
        try:
            summary = self.api.get_discharge_summary(selected_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Load Summary", str(exc))
            return
        self._load_summary(summary)

    def _on_admission_box_toggled(self, checked: bool) -> None:
        if checked and not self._admission:
            self._find_admission()
            if not self._admission:
                self.patient_box.blockSignals(True)
                self.patient_box.setChecked(False)
                self.patient_box.blockSignals(False)

    def _include_admission_details(self) -> bool:
        return self.patient_box.isChecked() and self._admission is not None

    def _validate_before_save(self) -> bool:
        if not self._patient and not self._resolve_patient():
            return False
        if not self.doctor.currentData():
            QMessageBox.warning(self, "Validation", "Select a doctor.")
            return False
        adm_qd = self.admission_date.date()
        dis_qd = self.discharge_date.date()
        adm = date(adm_qd.year(), adm_qd.month(), adm_qd.day())
        dis = date(dis_qd.year(), dis_qd.month(), dis_qd.day())
        if dis < adm:
            QMessageBox.warning(
                self,
                "Validation",
                "Discharge date cannot be before admission date.",
            )
            return False
        if self.patient_box.isChecked() and not self._admission:
            QMessageBox.warning(
                self,
                "Validation",
                "Select an admission or uncheck Admission Details.",
            )
            return False
        return True

    def _load_combo_doctor(self, doctor_id: str | None) -> None:
        if not doctor_id:
            self.doctor.setCurrentIndex(0)
            return
        for idx in range(self.doctor.count()):
            if self.doctor.itemData(idx) == doctor_id:
                self.doctor.setCurrentIndex(idx)
                return

    def _find_admission(self) -> None:
        search = self.patient_id_input.text().strip()
        admission = self._pick_admission_dialog(search=search or None)
        if admission:
            self._load_admission(admission)
            try:
                summary = self.api.get_discharge_summary_by_admission(admission["id"])
                self._load_summary(summary)
            except ApiError:
                self._saved_summary_id = None
                self.summary_no.clear()
                self.save_btn.setText("Save Summary")
                if admission.get("diagnosis"):
                    self.diagnosis_on_admission.setPlainText(str(admission["diagnosis"]))

    def _pick_admission_dialog(self, search: str | None = None) -> dict | None:
        try:
            rows = self.api.list_ipd_admissions(status="discharged", search=search)
        except ApiError as exc:
            QMessageBox.warning(self, "Discharged Patients", str(exc))
            return None
        if not rows:
            QMessageBox.information(
                self,
                "Discharged Patients",
                "No discharged admissions found. Complete IPD discharge billing first.",
            )
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Discharged Admission")
        dialog.resize(900, 460)
        layout = QVBoxLayout(dialog)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter"))
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("Patient id, name, admission no...")
        filter_edit.setText(search or "")
        filter_row.addWidget(filter_edit, stretch=1)
        layout.addLayout(filter_row)

        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["Admission No", "Patient Id", "Patient Name", "Ward", "Admit Date", "Discharge Date", "Doctor"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table, stretch=1)

        def _populate(items: list[dict]) -> None:
            table.setRowCount(len(items))
            for row_idx, item in enumerate(items):
                table.setItem(row_idx, 0, QTableWidgetItem(item.get("admission_no", "")))
                table.setItem(row_idx, 1, QTableWidgetItem(item.get("patient_no") or ""))
                table.setItem(row_idx, 2, QTableWidgetItem(item.get("patient_name") or ""))
                table.setItem(row_idx, 3, QTableWidgetItem(item.get("ward_name") or ""))
                table.setItem(row_idx, 4, QTableWidgetItem(str(item.get("admission_date", ""))))
                table.setItem(row_idx, 5, QTableWidgetItem(str(item.get("discharge_date", ""))))
                table.setItem(row_idx, 6, QTableWidgetItem(item.get("doctor_name") or ""))
                for col in range(7):
                    cell = table.item(row_idx, col)
                    if cell:
                        cell.setData(Qt.ItemDataRole.UserRole, item)

        def _apply_filter() -> None:
            query = filter_edit.text().strip().lower()
            if not query:
                _populate(rows)
                return
            filtered = [
                item
                for item in rows
                if query in (item.get("admission_no") or "").lower()
                or query in (item.get("patient_no") or "").lower()
                or query in (item.get("patient_name") or "").lower()
                or query in (item.get("ward_name") or "").lower()
            ]
            _populate(filtered)

        filter_edit.textChanged.connect(_apply_filter)
        _apply_filter()

        selected: dict | None = None

        def _accept_selection() -> None:
            nonlocal selected
            sel_rows = table.selectionModel().selectedRows()
            if not sel_rows:
                QMessageBox.information(dialog, "Select", "Choose an admission from the list.")
                return
            cell = table.item(sel_rows[0].row(), 0)
            if cell:
                selected = cell.data(Qt.ItemDataRole.UserRole)
            dialog.accept()

        table.doubleClicked.connect(lambda _index: _accept_selection())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        buttons.accepted.connect(_accept_selection)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return selected
        return None

    def _load_admission(self, admission: dict) -> None:
        self._admission = admission
        if getattr(self, "patient_box", None) is not None:
            self.patient_box.setChecked(True)
        self.admission_no.setText(admission.get("admission_no") or "")
        self.ward_name.setText(admission.get("ward_name") or "")
        if admission.get("patient_no"):
            self.patient_id_input.setText(admission.get("patient_no") or "")
        if admission.get("patient_name"):
            self.patient_name.setText(admission.get("patient_name") or "")
        if admission.get("admission_date"):
            self._set_date_field(self.admission_date, admission.get("admission_date"))
        if admission.get("discharge_date"):
            self._set_date_field(self.discharge_date, admission.get("discharge_date"))
            self._set_date_field(self.summary_date, admission.get("discharge_date"))
        if admission.get("doctor_id") and self.doctor.currentData() is None:
            self._load_combo_doctor(admission.get("doctor_id"))

    def _load_summary(self, summary: dict) -> None:
        self._saved_summary_id = summary.get("id")
        self.summary_no.setText(summary.get("summary_no") or "")
        if summary.get("patient_no"):
            self._apply_patient(
                {
                    "id": summary.get("patient_id"),
                    "patient_no": summary.get("patient_no"),
                    "patient_name": summary.get("patient_name"),
                }
            )
        include_admission = bool(summary.get("include_admission_details"))
        if getattr(self, "patient_box", None) is not None:
            self.patient_box.setChecked(include_admission)
        if include_admission and summary.get("admission_id"):
            admission = {
                "id": summary.get("admission_id"),
                "patient_no": summary.get("patient_no"),
                "patient_name": summary.get("patient_name"),
                "admission_no": summary.get("admission_no"),
                "ward_name": summary.get("ward_name"),
                "doctor_name": summary.get("doctor_name"),
                "doctor_id": summary.get("doctor_id"),
                "admission_date": summary.get("admission_date"),
                "discharge_date": summary.get("discharge_date"),
            }
            self._admission = admission
            self.admission_no.setText(admission.get("admission_no") or "")
            self.ward_name.setText(admission.get("ward_name") or "")
        else:
            self._admission = None
            self.admission_no.clear()
            self.ward_name.clear()
        if summary.get("summary_date"):
            self._set_date_field(self.summary_date, summary.get("summary_date"))
        if summary.get("admission_date"):
            self._set_date_field(self.admission_date, summary.get("admission_date"))
        if summary.get("discharge_date"):
            self._set_date_field(self.discharge_date, summary.get("discharge_date"))
        self._load_combo_doctor(summary.get("doctor_id"))
        condition = summary.get("condition_on_discharge") or ""
        idx = self.condition.findText(condition)
        self.condition.setCurrentIndex(idx if idx >= 0 else 0)
        self.chief_complaint.setPlainText(summary.get("chief_complaint") or "")
        self.history_of_illness.setPlainText(summary.get("history_of_illness") or "")
        self.diagnosis_on_admission.setPlainText(summary.get("diagnosis_on_admission") or "")
        self.final_diagnosis.setPlainText(summary.get("final_diagnosis") or "")
        self.investigation.setPlainText(summary.get("investigation") or "")
        self.treatment_given.setPlainText(summary.get("treatment_given") or "")
        self.procedures.setPlainText(summary.get("procedures") or "")
        self.medications.setPlainText(summary.get("medications_on_discharge") or "")
        self.advice_follow_up.setPlainText(summary.get("advice_follow_up") or "")
        self.remarks.setPlainText(summary.get("remarks") or "")
        self.save_btn.setText("Update Summary")

    def _load_by_summary_no(self) -> None:
        summary_no, ok = QInputDialog.getText(self, "Load Summary", "Enter discharge summary number:")
        if not ok or not summary_no.strip():
            return
        try:
            summary = self.api.get_discharge_summary_by_no(summary_no.strip())
        except ApiError as exc:
            QMessageBox.warning(self, "Load Summary", str(exc))
            return
        self._load_summary(summary)
        if summary.get("patient_id"):
            self._apply_patient(
                {
                    "id": summary.get("patient_id"),
                    "patient_no": summary.get("patient_no"),
                    "patient_name": summary.get("patient_name"),
                }
            )

    @staticmethod
    def _text_value(field: QTextEdit) -> str | None:
        text = field.toPlainText().strip()
        return text or None

    def _build_payload(self) -> dict:
        qd = self.summary_date.date()
        summary_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        condition = self.condition.currentText().strip() or None
        doctor_id = self.doctor.currentData()
        payload = {
            "summary_date": summary_date,
            "admission_date": self._date_field_iso(self.admission_date),
            "discharge_date": self._date_field_iso(self.discharge_date),
            "doctor_id": doctor_id,
            "include_admission_details": self._include_admission_details(),
            "chief_complaint": self._text_value(self.chief_complaint),
            "history_of_illness": self._text_value(self.history_of_illness),
            "diagnosis_on_admission": self._text_value(self.diagnosis_on_admission),
            "final_diagnosis": self._text_value(self.final_diagnosis),
            "investigation": self._text_value(self.investigation),
            "treatment_given": self._text_value(self.treatment_given),
            "procedures": self._text_value(self.procedures),
            "condition_on_discharge": condition,
            "medications_on_discharge": self._text_value(self.medications),
            "advice_follow_up": self._text_value(self.advice_follow_up),
            "remarks": self._text_value(self.remarks),
        }
        if self._include_admission_details() and self._admission:
            payload["admission_id"] = self._admission.get("id")
        return payload

    def _report_endpoint(self) -> str | None:
        if self._saved_summary_id:
            return f"/reports/discharge-summary/{self._saved_summary_id}"
        summary_no = self.summary_no.text().strip()
        if summary_no:
            return f"/reports/discharge-summary/by-no/{summary_no}"
        return None

    def _preview_summary(self) -> None:
        endpoint = self._report_endpoint()
        if endpoint:
            preview_report(self.api, endpoint, parent=self, title="Discharge Summary Preview", report_code="DISCHARGE_SUMMARY")

    def _print_summary(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Print", "Save or load a discharge summary first.")
            return
        print_report(self.api, endpoint, parent=self, report_code="DISCHARGE_SUMMARY")

    def _save_summary(self) -> None:
        if not self._validate_before_save():
            return
        payload = self._build_payload()
        try:
            if self._saved_summary_id:
                summary = self.api.update_discharge_summary(self._saved_summary_id, payload)
                title = "Updated"
            else:
                payload["patient_id"] = self._patient.get("id")
                summary = self.api.create_discharge_summary(payload)
                title = "Saved"
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._load_summary(summary)
        summary_no = summary.get("summary_no", "")
        if summary_no:
            QGuiApplication.clipboard().setText(summary_no)
        QMessageBox.information(self, title, f"Discharge summary {summary_no} saved successfully.")
        self._preview_summary()

    def _clear_form(self) -> None:
        self._patient = None
        self._admission = None
        self._saved_summary_id = None
        if getattr(self, "patient_box", None) is not None:
            self.patient_box.setChecked(False)
        self.patient_id_input.clear()
        self.patient_name.clear()
        self.admission_no.clear()
        self.ward_name.clear()
        self.summary_no.clear()
        self.summary_date.setDate(QDate.currentDate())
        self.admission_date.setDate(QDate.currentDate())
        self.discharge_date.setDate(QDate.currentDate())
        self.doctor.setCurrentIndex(0)
        self.condition.setCurrentIndex(0)
        for field in (
            self.chief_complaint,
            self.history_of_illness,
            self.diagnosis_on_admission,
            self.final_diagnosis,
            self.investigation,
            self.treatment_given,
            self.procedures,
            self.medications,
            self.advice_follow_up,
            self.remarks,
        ):
            field.clear()
        self.save_btn.setText("Save Summary")
