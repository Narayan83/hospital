"""Shared patient bill search list for modification screens."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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
from app.ui.styles import mark_patient_name_field
from app.ui.widgets.bill_lookup import (
    patient_display_name,
    resolve_patient_for_search,
)
from app.ui.widgets.opd_bill import SERVICE_TABLE_STYLE


class PatientBillSearchPanel(QWidget):
    bill_selected = Signal(dict)

    def __init__(
        self,
        api: ApiClient,
        *,
        title: str,
        hint: str,
        list_bills,
        bill_columns: list[str],
        bill_row_values,
    ):
        super().__init__()
        self.api = api
        self._list_bills = list_bills
        self._bill_columns = bill_columns
        self._bill_row_values = bill_row_values
        self._patient: dict | None = None
        self._bill_summaries: list[dict] = []
        self._build_ui(title, hint)

    def _build_ui(self, title: str, hint: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint_label)

        search_box = QGroupBox("Find Patient")
        search_form = QFormLayout(search_box)
        search_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient Id")
        self.patient_id.setMaximumWidth(200)
        self.patient_id.setFixedHeight(26)
        self.patient_id.returnPressed.connect(self._search_bills)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search_bills)
        search_row.addWidget(self.patient_id)
        search_row.addWidget(search_btn)
        search_row.addStretch(1)
        search_form.addRow("Patient Id", search_row)
        self.patient_name = QLineEdit()
        self.patient_name.setPlaceholderText("Patient name")
        self.patient_name.setFixedHeight(26)
        mark_patient_name_field(self.patient_name)
        self.patient_name.returnPressed.connect(self._search_bills)
        search_form.addRow("Name", self.patient_name)
        layout.addWidget(search_box)

        self.bills_table = QTableWidget(0, len(self._bill_columns))
        self.bills_table.setHorizontalHeaderLabels(self._bill_columns)
        self.bills_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.bills_table.setAlternatingRowColors(True)
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bills_table.verticalHeader().setVisible(False)
        self.bills_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bills_table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.bills_table, stretch=1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Modify Bill")
        open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no") or "")
        self.patient_name.setText(patient_display_name(patient))

    def _resolve_patient(self) -> dict | None:
        patient_no = self.patient_id.text().strip()
        name = self.patient_name.text().strip()
        if not patient_no and not name:
            QMessageBox.warning(self, "Patient", "Enter a patient id or name first.")
            return None
        try:
            patient = resolve_patient_for_search(
                self.api,
                self,
                patient_no=patient_no,
                name=name,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Patient", str(exc))
            return None
        if not patient:
            self._patient = None
            self._bill_summaries = []
            self._populate_bills_table()
            if patient_no:
                QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
            return None
        self._apply_patient(patient)
        return patient

    def _search_bills(self) -> None:
        patient = self._resolve_patient()
        if not patient:
            return
        self._search_bills_for_patient(patient)

    def _search_bills_for_patient(self, patient: dict) -> None:
        try:
            self._bill_summaries = self._list_bills(patient.get("patient_no"))
        except ApiError as exc:
            QMessageBox.warning(self, "Search Bills", str(exc))
            return
        self._populate_bills_table()
        count = len(self._bill_summaries)
        if count:
            self._set_status(f"Found {count} bill(s) for {patient.get('patient_no')} — latest first.")
        else:
            self._set_status(f"No bills found for {patient.get('patient_no')}.")

    def _populate_bills_table(self) -> None:
        self.bills_table.setRowCount(len(self._bill_summaries))
        for row, bill in enumerate(self._bill_summaries):
            values = self._bill_row_values(bill)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, bill.get("id"))
                self.bills_table.setItem(row, col, item)

    def _selected_bill_summary(self) -> dict | None:
        row = self.bills_table.currentRow()
        if row < 0 or row >= len(self._bill_summaries):
            return None
        return self._bill_summaries[row]

    def _open_selected(self) -> None:
        summary = self._selected_bill_summary()
        if not summary:
            QMessageBox.information(self, "Modify Bill", "Select a bill from the list first.")
            return
        self.bill_selected.emit(summary)

    def reset_state(self) -> None:
        self._patient = None
        self._bill_summaries = []
        self.patient_id.clear()
        self.patient_name.clear()
        self.bills_table.setRowCount(0)
        self.status.clear()
