"""Pathology Bill Cancel — find by patient id or bill number, then void."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import BTN_DANGER, BTN_SECONDARY, TEXT_MUTED, mark_patient_name_field
from app.ui.widgets.bill_lookup import (
    filter_active_bills,
    patient_display_name,
    resolve_patient_for_search,
)
from app.ui.widgets.opd_bill import SERVICE_TABLE_STYLE


class PathologyBillCancelWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._bill_summaries: list[dict] = []
        self._current_bill: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, stretch=1)

        self._stack.addWidget(self._build_list_page())
        self._stack.addWidget(self._build_detail_page())

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        outer.addWidget(self.status)

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        heading = QLabel("Pathology Bill Cancel")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Search by Patient Id, Name, or Bill No. "
            "Open a bill, enter a reason, then cancel."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(hint)

        search_box = QGroupBox("Find Bill")
        search_form = QFormLayout(search_box)
        search_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        search_form.setProperty("hmsResponsive", True)

        search_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient Id")
        self.patient_id.returnPressed.connect(self._search_bills)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_SECONDARY)
        search_btn.clicked.connect(self._search_bills)
        search_row.addWidget(self.patient_id, stretch=1)
        search_row.addWidget(search_btn)
        search_form.addRow("Patient Id", search_row)

        self.patient_name = QLineEdit()
        self.patient_name.setPlaceholderText("Patient name")
        mark_patient_name_field(self.patient_name)
        self.patient_name.returnPressed.connect(self._search_bills)
        search_form.addRow("Name", self.patient_name)

        bill_row = QHBoxLayout()
        self.bill_no_input = QLineEdit()
        self.bill_no_input.setPlaceholderText("e.g. PATH202600001")
        self.bill_no_input.returnPressed.connect(self._search_by_bill_no)
        bill_search_btn = QPushButton("Load Bill")
        bill_search_btn.setStyleSheet(BTN_SECONDARY)
        bill_search_btn.clicked.connect(self._search_by_bill_no)
        bill_row.addWidget(self.bill_no_input, stretch=1)
        bill_row.addWidget(bill_search_btn)
        search_form.addRow("Bill No", bill_row)
        layout.addWidget(search_box)

        self.bills_table = QTableWidget(0, 8)
        self.bills_table.setHorizontalHeaderLabels(
            [
                "Bill No",
                "Bill Date",
                "Pathologist",
                "Department",
                "Net Amount",
                "Sample No",
                "Order Status",
                "Payment",
            ]
        )
        self.bills_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.bills_table.setAlternatingRowColors(True)
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bills_table.verticalHeader().setVisible(False)
        header = self.bills_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bills_table.doubleClicked.connect(self._open_selected_bill)
        layout.addWidget(self.bills_table, stretch=1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Bill")
        open_btn.setStyleSheet(BTN_SECONDARY)
        open_btn.clicked.connect(self._open_selected_bill)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self.detail_title = QLabel("Cancel Bill")
        self.detail_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(self.detail_title)

        warn = QLabel(
            "Cancelling voids the bill and cannot be undone. Enter a reason before confirming."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(warn)

        header_box = QGroupBox("Bill Header")
        header_box.setProperty("hmsExpandFormFields", True)
        header_form = QFormLayout(header_box)
        header_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        header_form.setProperty("hmsResponsive", True)

        def _wide(field: QLineEdit) -> QLineEdit:
            field.setProperty("hmsAllowWide", True)
            field.setMaximumWidth(16777215)
            field.setMinimumWidth(420)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return field

        self.detail_bill_no = _wide(QLineEdit())
        self.detail_bill_no.setReadOnly(True)
        self.detail_bill_date = _wide(QLineEdit())
        self.detail_bill_date.setReadOnly(True)
        self.detail_patient = _wide(QLineEdit())
        self.detail_patient.setReadOnly(True)
        self.detail_doctor = _wide(QLineEdit())
        self.detail_doctor.setReadOnly(True)
        self.detail_department = _wide(QLineEdit())
        self.detail_department.setReadOnly(True)
        self.detail_net = _wide(QLineEdit())
        self.detail_net.setReadOnly(True)
        self.detail_status = _wide(QLineEdit())
        self.detail_status.setReadOnly(True)
        header_form.addRow("Bill No", self.detail_bill_no)
        header_form.addRow("Bill Date", self.detail_bill_date)
        header_form.addRow("Patient", self.detail_patient)
        header_form.addRow("Pathologist", self.detail_doctor)
        header_form.addRow("Department", self.detail_department)
        header_form.addRow("Net Amount", self.detail_net)
        header_form.addRow("Status", self.detail_status)
        layout.addWidget(header_box)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Code", "Test", "Rate", "Qty", "Amount"])
        self.lines_table.setStyleSheet(SERVICE_TABLE_STYLE)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lines_table.verticalHeader().setVisible(False)
        lines_header = self.lines_table.horizontalHeader()
        lines_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        lines_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lines_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        lines_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        lines_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.lines_table, stretch=1)

        reason_row = QHBoxLayout()
        reason_lbl = QLabel("Cancellation Reason")
        reason_lbl.setStyleSheet("font-weight: 600; color: #334155;")
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Why is this bill being cancelled? (required)")
        reason_row.addWidget(reason_lbl)
        reason_row.addWidget(self.reason_input, stretch=1)
        layout.addLayout(reason_row)

        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back to List")
        back_btn.setStyleSheet(BTN_SECONDARY)
        back_btn.clicked.connect(self._show_list_page)
        self.cancel_btn = QPushButton("Cancel This Bill")
        self.cancel_btn.setStyleSheet(BTN_DANGER)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_bill)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)
        return page

    def refresh(self) -> None:
        self._set_status("Search by patient id, name, or bill number.")

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
            self._bill_summaries = self.api.list_pathology_bills_by_patient(
                patient_no=patient.get("patient_no")
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Search Bills", str(exc))
            return
        self._bill_summaries = filter_active_bills(self._bill_summaries)
        self._populate_bills_table()
        count = len(self._bill_summaries)
        if count:
            self._set_status(f"Found {count} active bill(s) for {patient.get('patient_no')}.")
        else:
            self._set_status(f"No active pathology bills for {patient.get('patient_no')}.")
    def _search_by_bill_no(self) -> None:
        bill_no = self.bill_no_input.text().strip()
        if not bill_no:
            QMessageBox.warning(self, "Bill No", "Enter a pathology bill number.")
            return
        try:
            bill = self.api.get_pathology_bill_by_no(bill_no)
        except ApiError as exc:
            QMessageBox.warning(self, "Bill No", f"No pathology bill found: {bill_no}\n\n{exc}")
            return
        status = str(bill.get("status") or "").lower()
        if status in {"cancelled", "canceled"}:
            QMessageBox.information(self, "Bill No", f"Bill {bill_no} is already cancelled.")
            return
        self.bill_no_input.setText(bill.get("bill_no") or bill_no)
        if bill.get("patient_no"):
            self.patient_id.setText(bill.get("patient_no") or "")
            self.patient_name.setText(bill.get("patient_name") or "")
            self._patient = {
                "id": bill.get("patient_id"),
                "patient_no": bill.get("patient_no"),
                "first_name": bill.get("patient_name") or "",
            }
        self._bill_summaries = [
            {
                "id": bill.get("id"),
                "bill_no": bill.get("bill_no"),
                "bill_date": bill.get("bill_date"),
                "doctor_name": bill.get("doctor_name"),
                "department_name": bill.get("department_name"),
                "net_amount": bill.get("net_amount"),
                "sample_no": bill.get("sample_no"),
                "order_status": bill.get("order_status"),
                "payment_mode_name": bill.get("payment_mode_name"),
                "status": bill.get("status"),
            }
        ]
        self._populate_bills_table()
        self._show_bill_detail(bill)

    def _populate_bills_table(self) -> None:
        self.bills_table.setRowCount(len(self._bill_summaries))
        for row, bill in enumerate(self._bill_summaries):
            order_status = (bill.get("order_status") or "—").replace("_", " ").title()
            values = [
                bill.get("bill_no") or "",
                str(bill.get("bill_date") or ""),
                bill.get("doctor_name") or "—",
                bill.get("department_name") or "—",
                f"{float(bill.get('net_amount') or 0):.2f}",
                bill.get("sample_no") or "—",
                order_status,
                bill.get("payment_mode_name") or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, bill.get("id"))
                self.bills_table.setItem(row, col, item)

    def _selected_bill_id(self) -> str | None:
        row = self.bills_table.currentRow()
        if row < 0:
            return None
        item = self.bills_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open_selected_bill(self) -> None:
        bill_id = self._selected_bill_id()
        if not bill_id:
            QMessageBox.information(self, "Open Bill", "Select a bill from the list first.")
            return
        try:
            bill = self.api.get_pathology_bill(bill_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Open Bill", str(exc))
            return
        status = str(bill.get("status") or "").lower()
        if status in {"cancelled", "canceled"}:
            QMessageBox.information(self, "Open Bill", "This bill is already cancelled.")
            return
        self._show_bill_detail(bill)

    def _show_list_page(self) -> None:
        self._stack.setCurrentIndex(0)
        self._current_bill = None
        self.reason_input.clear()
        self._set_status("Search by patient id or bill number.")

    def _show_bill_detail(self, bill: dict) -> None:
        self._current_bill = bill
        bill_no = bill.get("bill_no") or ""
        self.detail_title.setText(f"Cancel Bill — {bill_no}")
        self.detail_bill_no.setText(bill_no)
        self.detail_bill_date.setText(str(bill.get("bill_date") or ""))
        patient_label = bill.get("patient_name") or ""
        if bill.get("patient_no"):
            patient_label = f"{bill.get('patient_no')} — {patient_label}".strip(" —")
        self.detail_patient.setText(patient_label)
        self.detail_doctor.setText(bill.get("doctor_name") or "—")
        self.detail_department.setText(bill.get("department_name") or "—")
        self.detail_net.setText(f"{float(bill.get('net_amount') or 0):.2f}")
        self.detail_status.setText(str(bill.get("status") or "—").replace("_", " ").title())

        lines = [
            line
            for line in (bill.get("lines") or [])
            if not line.get("is_panel_parent")
        ]
        self.lines_table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            self.lines_table.setItem(row, 0, QTableWidgetItem(line.get("service_code") or ""))
            self.lines_table.setItem(row, 1, QTableWidgetItem(line.get("service_name") or ""))
            self.lines_table.setItem(row, 2, QTableWidgetItem(f"{float(line.get('rate') or 0):.2f}"))
            self.lines_table.setItem(row, 3, QTableWidgetItem(str(line.get("quantity") or 0)))
            self.lines_table.setItem(row, 4, QTableWidgetItem(f"{float(line.get('amount') or 0):.2f}"))

        self.reason_input.clear()
        self._stack.setCurrentIndex(1)
        self.reason_input.setFocus()
        self._set_status(f"Review bill {bill_no}, enter reason, then cancel.")

    def _cancel_bill(self) -> None:
        if not self._current_bill:
            QMessageBox.information(self, "Cancel Bill", "Open a bill first.")
            return
        reason = self.reason_input.text().strip()
        if not reason:
            QMessageBox.warning(self, "Reason Required", "Enter a reason for cancelling this bill.")
            self.reason_input.setFocus()
            return

        bill_no = self._current_bill.get("bill_no") or ""
        confirm = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Cancel pathology bill {bill_no}?\n\nThis voids the bill and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        bill_id = self._current_bill.get("id")
        try:
            self.api.cancel_pathology_bill(bill_id, reason)
        except ApiError as exc:
            QMessageBox.warning(self, "Cancel Bill", str(exc))
            return

        QMessageBox.information(self, "Cancelled", f"Bill {bill_no} has been cancelled.")
        self._set_status(f"Bill {bill_no} cancelled.")
        self._current_bill = None
        self.reason_input.clear()
        self._stack.setCurrentIndex(0)
        # Refresh list if we still have a patient context.
        if self.patient_id.text().strip():
            self._search_bills()
        else:
            self._bill_summaries = []
            self._populate_bills_table()
