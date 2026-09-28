"""Unified Modify Bill — OPD, IPD, or Pathology by bill no / patient id / name."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import mark_patient_name_field
from app.ui.widgets.bill_lookup import (
    bill_row_values,
    bill_table_headers,
    fetch_bill_by_id,
    fetch_bill_by_no,
    filter_active_bills,
    list_bills_by_patient,
    patient_display_name,
    resolve_patient_for_search,
)
from app.ui.widgets.ipd_discharge import IpdDischargeWidget
from app.ui.widgets.opd_bill import SERVICE_TABLE_STYLE, OpdBillWidget
from app.ui.widgets.pathology_bill import PathologyBillWidget

_PAGE_SEARCH = 0
_PAGE_OPD = 1
_PAGE_IPD = 2
_PAGE_PATHOLOGY = 3


class BillModifyWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._bill_summaries: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_search_page())
        self._stack.addWidget(self._build_opd_editor_page())
        self._stack.addWidget(self._build_ipd_editor_page())
        self._stack.addWidget(self._build_pathology_editor_page())
        layout.addWidget(self._stack)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

        self._set_status("Search by bill no, patient id, or patient name.")

    def _build_search_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(8)

        heading = QLabel("Modify Bill")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        outer.addWidget(heading)

        hint = QLabel(
            "Select OPD, IPD, or Pathology. Load by bill number, or search by patient id / name, "
            "pick a bill from the list, then add or remove services/tests and change payments."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        outer.addWidget(hint)

        search_box = QGroupBox("Find Bill")
        form = QFormLayout(search_box)

        bill_type_row = QHBoxLayout()
        self._opd_radio = QRadioButton("OPD")
        self._ipd_radio = QRadioButton("IPD")
        self._pathology_radio = QRadioButton("Pathology")
        self._opd_radio.setChecked(True)
        self._bill_type_group = QButtonGroup(self)
        self._bill_type_group.addButton(self._opd_radio)
        self._bill_type_group.addButton(self._ipd_radio)
        self._bill_type_group.addButton(self._pathology_radio)
        for radio in (self._opd_radio, self._ipd_radio, self._pathology_radio):
            radio.toggled.connect(self._on_bill_type_changed)
            bill_type_row.addWidget(radio)
        bill_type_row.addStretch()
        form.addRow("Bill Type", bill_type_row)

        bill_no_row = QHBoxLayout()
        self.bill_no_input = QLineEdit()
        self.bill_no_input.setPlaceholderText("e.g. OPD202600001, IPD202600001, PATH202600001")
        self.bill_no_input.returnPressed.connect(self._load_by_bill_no)
        load_btn = QPushButton("Load Bill")
        load_btn.clicked.connect(self._load_by_bill_no)
        bill_no_row.addWidget(self.bill_no_input, stretch=1)
        bill_no_row.addWidget(load_btn)
        form.addRow("Bill No", bill_no_row)

        patient_id_row = QHBoxLayout()
        self.patient_id_input = QLineEdit()
        self.patient_id_input.setPlaceholderText("Patient Id")
        self.patient_id_input.returnPressed.connect(self._search_by_patient)
        patient_id_row.addWidget(self.patient_id_input, stretch=1)
        form.addRow("Patient Id", patient_id_row)

        name_row = QHBoxLayout()
        self.patient_name_input = QLineEdit()
        self.patient_name_input.setPlaceholderText("Patient name")
        self.patient_name_input.returnPressed.connect(self._search_by_patient)
        mark_patient_name_field(self.patient_name_input)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search_by_patient)
        name_row.addWidget(self.patient_name_input, stretch=1)
        name_row.addWidget(search_btn)
        form.addRow("Name", name_row)

        outer.addWidget(search_box)

        self.bills_table = QTableWidget(0, 6)
        self.bills_table.setHorizontalHeaderLabels(bill_table_headers("opd"))
        self.bills_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.bills_table.setAlternatingRowColors(True)
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bills_table.verticalHeader().setVisible(False)
        self.bills_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bills_table.doubleClicked.connect(self._open_selected_bill)
        outer.addWidget(self.bills_table, stretch=1)

        open_row = QHBoxLayout()
        open_btn = QPushButton("Modify Selected Bill")
        open_btn.clicked.connect(self._open_selected_bill)
        open_row.addWidget(open_btn)
        open_row.addStretch()
        outer.addLayout(open_row)
        return page

    def _build_editor_page(self, editor: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        back_row = QHBoxLayout()
        back_btn = QPushButton("← Back to Bill Search")
        back_btn.clicked.connect(self._show_search)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)
        layout.addWidget(editor, stretch=1)
        return page

    def _build_opd_editor_page(self) -> QWidget:
        self._opd_editor = OpdBillWidget(self.api, self._on_navigate, modification_mode=True)
        return self._build_editor_page(self._opd_editor)

    def _build_ipd_editor_page(self) -> QWidget:
        self._ipd_editor = IpdDischargeWidget(self.api, self._on_navigate, modification_mode=True)
        return self._build_editor_page(self._ipd_editor)

    def _build_pathology_editor_page(self) -> QWidget:
        self._pathology_editor = PathologyBillWidget(
            self.api, self._on_navigate, modification_mode=True
        )
        return self._build_editor_page(self._pathology_editor)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def _show_search(self) -> None:
        self._stack.setCurrentIndex(_PAGE_SEARCH)
        self._set_status("Search by bill no, patient id, or patient name.")

    def _selected_bill_type(self) -> str:
        if self._ipd_radio.isChecked():
            return "ipd"
        if self._pathology_radio.isChecked():
            return "pathology"
        return "opd"

    def _type_label(self, bill_type: str | None = None) -> str:
        selected = bill_type or self._selected_bill_type()
        return {"opd": "OPD", "ipd": "IPD", "pathology": "Pathology"}.get(selected, "OPD")

    def _on_bill_type_changed(self, checked: bool = False) -> None:
        if not checked:
            return
        self._configure_bills_table()
        if self._patient:
            self._load_patient_bills(self._patient)

    def _configure_bills_table(self) -> None:
        headers = bill_table_headers(self._selected_bill_type())
        self.bills_table.clear()
        self.bills_table.setColumnCount(len(headers))
        self.bills_table.setHorizontalHeaderLabels(headers)
        self.bills_table.setRowCount(0)

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id_input.setText(patient.get("patient_no") or "")
        self.patient_name_input.setText(patient_display_name(patient))

    def _search_by_patient(self) -> None:
        patient_no = self.patient_id_input.text().strip()
        name = self.patient_name_input.text().strip()
        if not patient_no and not name:
            QMessageBox.warning(
                self,
                "Search",
                "Enter a bill number, patient id, or patient name.",
            )
            return
        try:
            patient = resolve_patient_for_search(
                self.api,
                self,
                patient_no=patient_no,
                name=name,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))
            return
        if not patient:
            self._patient = None
            self._bill_summaries = []
            self._populate_bills_table()
            if patient_no:
                QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
            # Name search opens the list dialog; cancel/no match → stay quiet.
            return
        self._apply_patient(patient)
        self._load_patient_bills(patient)
    def _load_patient_bills(self, patient: dict) -> None:
        bill_type = self._selected_bill_type()
        try:
            bills = list_bills_by_patient(
                self.api,
                bill_type,
                patient_no=patient.get("patient_no"),
                patient_id=patient.get("id"),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Search Bills", str(exc))
            return
        self._bill_summaries = filter_active_bills(bills)
        self._configure_bills_table()
        self._populate_bills_table()
        count = len(self._bill_summaries)
        label = self._type_label(bill_type)
        patient_no = patient.get("patient_no") or ""
        if count:
            self._set_status(f"Found {count} {label} bill(s) for {patient_no} — double-click to modify.")
        else:
            self._set_status(f"No active {label} bills for {patient_no}.")

    def _populate_bills_table(self) -> None:
        bill_type = self._selected_bill_type()
        self.bills_table.setRowCount(len(self._bill_summaries))
        for row, bill in enumerate(self._bill_summaries):
            values = bill_row_values(bill, bill_type)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, bill.get("id"))
                self.bills_table.setItem(row, col, item)

    def _load_by_bill_no(self) -> None:
        bill_no = self.bill_no_input.text().strip()
        if not bill_no:
            QMessageBox.warning(self, "Bill Number", "Enter a bill number first.")
            return
        bill_type = self._selected_bill_type()
        type_label = self._type_label(bill_type)
        try:
            bill = fetch_bill_by_no(self.api, bill_type, bill_no)
        except ApiError as exc:
            QMessageBox.warning(
                self,
                "Load Bill",
                f"No {type_label} bill found with number: {bill_no}\n\n{exc}",
            )
            return
        self._open_bill(bill, bill_type)

    def _open_selected_bill(self) -> None:
        row = self.bills_table.currentRow()
        if row < 0 or row >= len(self._bill_summaries):
            QMessageBox.information(self, "Modify Bill", "Select a bill from the list first.")
            return
        summary = self._bill_summaries[row]
        bill_id = summary.get("id")
        if not bill_id:
            QMessageBox.warning(self, "Modify Bill", "Selected bill has no id.")
            return
        bill_type = self._selected_bill_type()
        type_label = self._type_label(bill_type)
        try:
            bill = fetch_bill_by_id(self.api, bill_type, str(bill_id))
        except ApiError as exc:
            QMessageBox.warning(self, "Load Bill", f"Could not open {type_label} bill.\n\n{exc}")
            return
        self._open_bill(bill, bill_type)

    def _open_bill(self, bill: dict, bill_type: str) -> None:
        loaded_no = (bill.get("bill_no") or "").strip()
        type_label = self._type_label(bill_type)
        if bill_type == "opd":
            self._opd_editor.load_bill_for_modification(bill)
            self._stack.setCurrentIndex(_PAGE_OPD)
        elif bill_type == "ipd":
            self._ipd_editor.load_bill_for_modification(bill)
            self._stack.setCurrentIndex(_PAGE_IPD)
        else:
            self._pathology_editor.load_bill_for_modification(bill)
            self._stack.setCurrentIndex(_PAGE_PATHOLOGY)
        self._set_status(
            f"Editing {type_label} bill {loaded_no} — "
            "add/remove items and update payments, then click Update Bill."
        )

    def refresh(self) -> None:
        self._opd_editor.refresh()
        self._ipd_editor.refresh()
        self._pathology_editor.refresh()
