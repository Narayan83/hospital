"""Cancel Bill — void an OPD, IPD, or Pathology bill by bill no / patient id / name."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import BTN_DANGER, BTN_SECONDARY, TEXT_MUTED, mark_patient_name_field
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
from app.ui.widgets.opd_bill import SERVICE_TABLE_STYLE


class CancelBillWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._loaded_bill: dict | None = None
        self._loaded_type: str | None = None
        self._patient: dict | None = None
        self._bill_summaries: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        heading = QLabel("Cancel Bill")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        outer.addWidget(heading)

        hint = QLabel(
            "Select the bill type. Load by bill number, or search by patient id / name and pick "
            "a bill. Review the details, enter a reason, then cancel. Cancelling voids the bill, "
            "reverses its cashbook entry and releases its token (OPD) or re-opens the admission (IPD)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        outer.addWidget(hint)

        find_box = QGroupBox("Find Bill")
        find_form = QFormLayout(find_box)

        type_row = QHBoxLayout()
        self._opd_radio = QRadioButton("OPD")
        self._ipd_radio = QRadioButton("IPD")
        self._pathology_radio = QRadioButton("Pathology")
        self._opd_radio.setChecked(True)
        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._opd_radio)
        self._type_group.addButton(self._ipd_radio)
        self._type_group.addButton(self._pathology_radio)
        for radio in (self._opd_radio, self._ipd_radio, self._pathology_radio):
            radio.toggled.connect(self._on_bill_type_changed)
            type_row.addWidget(radio)
        type_row.addStretch()
        find_form.addRow("Bill Type", type_row)

        bill_no_row = QHBoxLayout()
        self.bill_no_input = QLineEdit()
        self.bill_no_input.setPlaceholderText("e.g. OPD202600001, IPDB202600001 or PATH202600001")
        self.bill_no_input.returnPressed.connect(self._load_by_bill_no)
        load_btn = QPushButton("Load Bill")
        load_btn.setStyleSheet(BTN_SECONDARY)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self._load_by_bill_no)
        bill_no_row.addWidget(self.bill_no_input, stretch=1)
        bill_no_row.addWidget(load_btn)
        find_form.addRow("Bill No", bill_no_row)

        patient_id_row = QHBoxLayout()
        self.patient_id_input = QLineEdit()
        self.patient_id_input.setPlaceholderText("Patient Id")
        self.patient_id_input.returnPressed.connect(self._search_by_patient)
        patient_id_row.addWidget(self.patient_id_input, stretch=1)
        find_form.addRow("Patient Id", patient_id_row)

        name_row = QHBoxLayout()
        self.patient_name_input = QLineEdit()
        self.patient_name_input.setPlaceholderText("Patient name")
        self.patient_name_input.returnPressed.connect(self._search_by_patient)
        mark_patient_name_field(self.patient_name_input)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_SECONDARY)
        search_btn.clicked.connect(self._search_by_patient)
        name_row.addWidget(self.patient_name_input, stretch=1)
        name_row.addWidget(search_btn)
        find_form.addRow("Name", name_row)
        outer.addWidget(find_box)

        self.bills_table = QTableWidget(0, 6)
        self.bills_table.setHorizontalHeaderLabels(bill_table_headers("opd"))
        self.bills_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.bills_table.setAlternatingRowColors(True)
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bills_table.verticalHeader().setVisible(False)
        self.bills_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bills_table.setMaximumHeight(180)
        self.bills_table.doubleClicked.connect(self._open_selected_bill)
        outer.addWidget(self.bills_table)

        open_row = QHBoxLayout()
        open_btn = QPushButton("Open Selected Bill")
        open_btn.setStyleSheet(BTN_SECONDARY)
        open_btn.clicked.connect(self._open_selected_bill)
        open_row.addWidget(open_btn)
        open_row.addStretch()
        outer.addLayout(open_row)

        self.details_box = QGroupBox("Bill Details")
        details_layout = QVBoxLayout(self.details_box)

        summary_card = QFrame()
        summary_card.setStyleSheet(
            "QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }"
        )
        summary_form = QFormLayout(summary_card)
        summary_form.setContentsMargins(12, 10, 12, 10)
        self.lbl_bill_no = QLabel("—")
        self.lbl_patient = QLabel("—")
        self.lbl_date = QLabel("—")
        self.lbl_extra = QLabel("—")
        self.lbl_net = QLabel("—")
        self.lbl_net.setStyleSheet("font-size: 16px; font-weight: 800; color: #b91c1c;")
        for lbl in (self.lbl_bill_no, self.lbl_patient, self.lbl_date, self.lbl_extra):
            lbl.setStyleSheet("font-weight: 600; color: #334155;")
        summary_form.addRow("Bill No", self.lbl_bill_no)
        summary_form.addRow("Patient", self.lbl_patient)
        summary_form.addRow("Bill Date", self.lbl_date)
        summary_form.addRow("Doctor / Dept", self.lbl_extra)
        summary_form.addRow("Net Amount", self.lbl_net)
        details_layout.addWidget(summary_card)

        self.lines_table = QTableWidget(0, 4)
        self.lines_table.setHorizontalHeaderLabels(["Code", "Service / Test", "Qty", "Amount"])
        self.lines_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lines_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.lines_table.verticalHeader().setVisible(False)
        header = self.lines_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        details_layout.addWidget(self.lines_table, stretch=1)

        reason_row = QHBoxLayout()
        reason_lbl = QLabel("Cancellation Reason")
        reason_lbl.setStyleSheet("font-weight: 600; color: #334155;")
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Why is this bill being cancelled? (required)")
        reason_row.addWidget(reason_lbl)
        reason_row.addWidget(self.reason_input, stretch=1)
        details_layout.addLayout(reason_row)

        action_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel This Bill")
        self.cancel_btn.setStyleSheet(BTN_DANGER)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_bill)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(BTN_SECONDARY)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(clear_btn)
        action_row.addStretch()
        details_layout.addLayout(action_row)

        outer.addWidget(self.details_box, stretch=1)
        self.details_box.setVisible(False)

        self.status = QLabel("")
        self.status.setStyleSheet(
            "QLabel { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;"
            f" color: {TEXT_MUTED}; padding: 4px 10px; }}"
        )
        self.status.setMinimumHeight(26)
        outer.addWidget(self.status)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def _selected_type(self) -> str:
        if self._ipd_radio.isChecked():
            return "ipd"
        if self._pathology_radio.isChecked():
            return "pathology"
        return "opd"

    def _type_label(self, bill_type: str | None = None) -> str:
        selected = bill_type or self._selected_type()
        return {"opd": "OPD", "ipd": "IPD", "pathology": "Pathology"}.get(selected, "OPD")

    def _on_bill_type_changed(self, checked: bool = False) -> None:
        if not checked:
            return
        self._configure_bills_table()
        if self._patient:
            self._load_patient_bills(self._patient)

    def _configure_bills_table(self) -> None:
        headers = bill_table_headers(self._selected_type())
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
            return
        self._apply_patient(patient)
        self._load_patient_bills(patient)
    def _load_patient_bills(self, patient: dict) -> None:
        bill_type = self._selected_type()
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
            self._set_status(f"Found {count} {label} bill(s) for {patient_no} — open one to cancel.")
        else:
            self._set_status(f"No active {label} bills for {patient_no}.")

    def _populate_bills_table(self) -> None:
        bill_type = self._selected_type()
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
        bill_type = self._selected_type()
        type_label = self._type_label(bill_type)
        try:
            bill = fetch_bill_by_no(self.api, bill_type, bill_no)
        except ApiError as exc:
            self.details_box.setVisible(False)
            QMessageBox.warning(
                self,
                "Load Bill",
                f"No {type_label} bill found with number: {bill_no}\n\n{exc}",
            )
            return
        self._show_bill(bill, bill_type)

    def _open_selected_bill(self) -> None:
        row = self.bills_table.currentRow()
        if row < 0 or row >= len(self._bill_summaries):
            QMessageBox.information(self, "Cancel Bill", "Select a bill from the list first.")
            return
        summary = self._bill_summaries[row]
        bill_id = summary.get("id")
        if not bill_id:
            QMessageBox.warning(self, "Cancel Bill", "Selected bill has no id.")
            return
        bill_type = self._selected_type()
        type_label = self._type_label(bill_type)
        try:
            bill = fetch_bill_by_id(self.api, bill_type, str(bill_id))
        except ApiError as exc:
            QMessageBox.warning(self, "Load Bill", f"Could not open {type_label} bill.\n\n{exc}")
            return
        self._show_bill(bill, bill_type)

    def _show_bill(self, bill: dict, bill_type: str) -> None:
        self._loaded_bill = bill
        self._loaded_type = bill_type
        self._populate_details(bill)
        self.details_box.setVisible(True)
        self.reason_input.clear()
        self.reason_input.setFocus()
        self._set_status(
            f"Loaded {self._type_label(bill_type)} bill {bill.get('bill_no')} — "
            "review and enter a reason to cancel."
        )

    def _populate_details(self, bill: dict) -> None:
        self.lbl_bill_no.setText(bill.get("bill_no") or "—")
        name = bill.get("patient_name") or ""
        patient_no = bill.get("patient_no") or ""
        self.lbl_patient.setText(" — ".join(p for p in [patient_no, name] if p) or "—")
        self.lbl_date.setText(str(bill.get("bill_date") or "—"))
        doctor = bill.get("doctor_name") or bill.get("referring_doctor") or ""
        dept = bill.get("department_name") or bill.get("ward_name") or ""
        self.lbl_extra.setText(" / ".join(p for p in [doctor, dept] if p) or "—")
        net = bill.get("net_amount") or 0
        try:
            self.lbl_net.setText(f"{float(net):.2f}")
        except (TypeError, ValueError):
            self.lbl_net.setText(str(net))

        lines = [
            line
            for line in (bill.get("lines") or [])
            if not line.get("is_panel_parent")
        ]
        self.lines_table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            code = QTableWidgetItem(str(line.get("service_code") or ""))
            name_item = QTableWidgetItem(str(line.get("service_name") or ""))
            qty = QTableWidgetItem(str(line.get("quantity") or 1))
            qty.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amount_val = line.get("amount") or 0
            try:
                amount_text = f"{float(amount_val):.2f}"
            except (TypeError, ValueError):
                amount_text = str(amount_val)
            amount = QTableWidgetItem(amount_text)
            amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setItem(row, 0, code)
            self.lines_table.setItem(row, 1, name_item)
            self.lines_table.setItem(row, 2, qty)
            self.lines_table.setItem(row, 3, amount)

    def _cancel_bill(self) -> None:
        if not self._loaded_bill or not self._loaded_type:
            QMessageBox.information(self, "Cancel Bill", "Load a bill first.")
            return
        reason = self.reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Reason Required", "Enter a reason for cancelling this bill.")
            self.reason_input.setFocus()
            return

        bill_no = self._loaded_bill.get("bill_no") or ""
        confirm = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Cancel bill {bill_no}?\n\nThis voids the bill and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        bill_id = self._loaded_bill.get("id")
        try:
            if self._loaded_type == "opd":
                self.api.cancel_opd_bill(bill_id, reason)
            elif self._loaded_type == "ipd":
                self.api.cancel_ipd_discharge(bill_id, reason)
            else:
                self.api.cancel_pathology_bill(bill_id, reason)
        except ApiError as exc:
            QMessageBox.warning(self, "Cancel Bill", str(exc))
            return

        QMessageBox.information(self, "Cancelled", f"Bill {bill_no} has been cancelled.")
        self._set_status(f"Bill {bill_no} cancelled.")
        self._clear()

    def _clear(self) -> None:
        self._loaded_bill = None
        self._loaded_type = None
        self._patient = None
        self._bill_summaries = []
        self.bill_no_input.clear()
        self.patient_id_input.clear()
        self.patient_name_input.clear()
        self.reason_input.clear()
        self.bills_table.setRowCount(0)
        self.lines_table.setRowCount(0)
        self.details_box.setVisible(False)

    def refresh(self) -> None:
        pass
