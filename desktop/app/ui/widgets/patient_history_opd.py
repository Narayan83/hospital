from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.components.collapsible_section import CollapsibleSection
from app.ui.components.patient_documents_dialog import PatientDocumentsDialog
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE

VISIT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("opd", "OPD Patient History"),
    ("appointment", "Appointment OPD Patient History"),
    ("reference", "Reference Patient History"),
    ("online_booking", "Online Booking Patient History"),
)

TABLE_COLUMNS = [
    "Slno",
    "Pid",
    "Pname",
    "Patient Document",
    "Token",
    "Session",
    "Bill No",
    "Rdolgy",
    "Pthlgy",
    "View Prescription",
    "Enter Prescription",
]


class PatientHistoryOpdWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._sections: dict[str, CollapsibleSection] = {}
        self._tables: dict[str, QTableWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Token Date"))
        self.token_date = QDateEdit()
        self.token_date.setCalendarPopup(True)
        self.token_date.setDisplayFormat("dd/MM/yyyy")
        self.token_date.setDate(QDate.currentDate())
        self.token_date.dateChanged.connect(lambda _d: self.refresh())
        filter_row.addWidget(self.token_date)

        filter_row.addWidget(QLabel("Session"))
        self.token_session = QComboBox()
        self.token_session.addItem("All", None)
        self.token_session.addItem("Morning", "morning")
        self.token_session.addItem("Evening", "evening")
        self.token_session.currentIndexChanged.connect(lambda _i: self.refresh())
        filter_row.addWidget(self.token_session)

        self.doctor_label = QLabel("Doctor")
        self.doctor_combo = QComboBox()
        self.doctor_combo.currentIndexChanged.connect(self._on_doctor_changed)
        filter_row.addWidget(self.doctor_label)
        filter_row.addWidget(self.doctor_combo, stretch=1)

        self.doctor_name_label = QLabel()
        self.doctor_name_label.setStyleSheet("font-weight: 600; color: #1e3a5f;")
        self.doctor_name_label.setVisible(False)
        filter_row.addWidget(self.doctor_name_label, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(HEADER_BTN_STYLE)
        refresh_btn.clicked.connect(self.refresh)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        for index, (code, title) in enumerate(VISIT_CATEGORIES):
            section = CollapsibleSection(title, expanded=index == 0)
            table = QTableWidget(0, len(TABLE_COLUMNS))
            table.setHorizontalHeaderLabels(TABLE_COLUMNS)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            section.content_layout.addWidget(table)
            body_layout.addWidget(section)
            self._sections[code] = section
            self._tables[code] = table

        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)

        self.status = QLabel()
        self.status.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status)

        self._configure_doctor_filter()

    def _configure_doctor_filter(self) -> None:
        session = get_session()
        if session.maps_to_doctor and session.doctor_id:
            self.doctor_label.setVisible(False)
            self.doctor_combo.setVisible(False)
            self.doctor_name_label.setVisible(True)
            doctor_name = self._doctor_display_name(session.doctor_id)
            self.doctor_name_label.setText(f"Doctor: {doctor_name}")
        else:
            self.doctor_label.setVisible(True)
            self.doctor_combo.setVisible(True)
            self.doctor_name_label.setVisible(False)
            self._load_doctor_combo()

    def _doctor_display_name(self, doctor_id: str) -> str:
        for doctor in get_session().cache.doctors:
            if doctor.get("id") == doctor_id:
                code = doctor.get("doctor_code", "")
                name = doctor.get("full_name") or doctor.get("first_name", "")
                return f"{code} — {name}".strip(" —")
        return doctor_id

    def _load_doctor_combo(self) -> None:
        current = self.doctor_combo.currentData()
        self.doctor_combo.blockSignals(True)
        self.doctor_combo.clear()
        self.doctor_combo.addItem("— Select Doctor —", None)
        for doctor in get_session().cache.doctors:
            if not doctor.get("is_active", True):
                continue
            label = f"{doctor.get('doctor_code', '')} — {doctor.get('full_name', '')}".strip(" —")
            self.doctor_combo.addItem(label, doctor.get("id"))
        if current:
            idx = self.doctor_combo.findData(current)
            if idx >= 0:
                self.doctor_combo.setCurrentIndex(idx)
        self.doctor_combo.blockSignals(False)

    def _selected_doctor_id(self) -> str | None:
        session = get_session()
        if session.maps_to_doctor:
            return session.doctor_id
        return self.doctor_combo.currentData()

    def _on_doctor_changed(self) -> None:
        if not get_session().maps_to_doctor:
            self.refresh()

    def _token_date_iso(self) -> str:
        qd = self.token_date.date()
        return date(qd.year(), qd.month(), qd.day()).isoformat()

    def refresh(self) -> None:
        doctor_id = self._selected_doctor_id()
        if not doctor_id:
            self._clear_tables()
            self.status.setText("Select a doctor to load token-wise patients.")
            return

        token_session = self.token_session.currentData()
        try:
            tokens = self.api.list_opd_tokens(
                doctor_id=doctor_id,
                token_date=self._token_date_iso(),
                token_session=token_session,
            )
        except ApiError as exc:
            self._clear_tables()
            self.status.setText(str(exc))
            return
        except Exception as exc:
            self._clear_tables()
            self.status.setText(f"Connection error: {exc}")
            return

        grouped: dict[str, list[dict]] = {code: [] for code, _ in VISIT_CATEGORIES}
        for token in tokens:
            category = token.get("visit_category") or "opd"
            if category in grouped:
                grouped[category].append(token)

        total = 0
        for code, _title in VISIT_CATEGORIES:
            rows = grouped.get(code, [])
            self._populate_table(self._tables[code], rows)
            section = self._sections[code]
            count = len(rows)
            total += count
            section.set_title(f"{dict(VISIT_CATEGORIES).get(code, code)} ({count})")

        doctor_name = self._doctor_display_name(doctor_id)
        session_label = self.token_session.currentText()
        self.status.setText(
            f"{total} patient(s) for {doctor_name} on {self.token_date.date().toString('dd/MM/yyyy')} "
            f"({session_label} session)."
        )

    def _clear_tables(self) -> None:
        for code, _title in VISIT_CATEGORIES:
            self._populate_table(self._tables[code], [])
            section = self._sections[code]
            section.set_title(f"{dict(VISIT_CATEGORIES).get(code, code)} (0)")

    def _populate_table(self, table: QTableWidget, rows: list[dict]) -> None:
        table.setRowCount(len(rows))
        for row_index, token in enumerate(rows):
            token_no = token.get("token_number")
            session = (token.get("token_session") or "").title()
            values = [
                str(row_index + 1),
                token.get("patient_no") or "—",
                token.get("patient_name") or "—",
                "",
                str(token_no) if token_no is not None else "—",
                session or "—",
                token.get("bill_no") or "—",
                "—",
                "—",
            ]
            for col, value in enumerate(values):
                if col == 3:
                    docs_btn = QPushButton("View")
                    docs_btn.setStyleSheet(HEADER_BTN_STYLE)
                    docs_btn.clicked.connect(
                        lambda _checked=False, t=token: self._open_patient_documents(t)
                    )
                    table.setCellWidget(row_index, col, docs_btn)
                    continue
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_index, col, item)

            view_btn = QPushButton("View")
            view_btn.setStyleSheet(HEADER_BTN_STYLE)
            view_btn.clicked.connect(lambda _checked=False, t=token: self._view_prescription(t))
            table.setCellWidget(row_index, 9, view_btn)

            enter_btn = QPushButton("Enter")
            enter_btn.setStyleSheet(HEADER_BTN_STYLE)
            enter_btn.clicked.connect(lambda _checked=False, t=token: self._enter_prescription(t))
            table.setCellWidget(row_index, 10, enter_btn)

    def _open_patient_documents(self, token: dict) -> None:
        patient_id = token.get("patient_id")
        if not patient_id:
            QMessageBox.warning(self, "Patient Documents", "Patient ID is missing for this token.")
            return
        dialog = PatientDocumentsDialog(
            self.api,
            patient_id=patient_id,
            patient_no=token.get("patient_no") or "",
            patient_name=token.get("patient_name") or "",
            parent=self,
        )
        dialog.exec()

    def _view_prescription(self, token: dict) -> None:
        patient = token.get("patient_name") or token.get("patient_no") or "patient"
        QMessageBox.information(
            self,
            "View Prescription",
            f"Prescription view for {patient} is not implemented yet.",
        )

    def _enter_prescription(self, token: dict) -> None:
        patient = token.get("patient_name") or token.get("patient_no") or "patient"
        QMessageBox.information(
            self,
            "Enter Prescription",
            f"Prescription entry for {patient} is not implemented yet.",
        )
