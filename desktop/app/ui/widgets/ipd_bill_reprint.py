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
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE, SERVICE_TABLE_STYLE


class IpdBillReprintWidget(QWidget):
    pending_patient_no: str | None = None

    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._bill_summaries: list[dict] = []
        self._current_bill: dict | None = None
        self._build_ui()

    @staticmethod
    def _wide(widget: QWidget) -> QWidget:
        widget.setProperty("hmsAllowWide", True)
        widget.setMaximumWidth(16777215)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumWidth(280)
        return widget

    @classmethod
    def request_open(cls, patient_no: str = "") -> None:
        cls.pending_patient_no = patient_no.strip() or None

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

        heading = QLabel("IPD Bill Reprint")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Enter patient id to list previous IPD discharge bills. Select a bill to view and reprint."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        search_box = QGroupBox("Find Patient")
        search_box.setProperty("hmsExpandFormFields", True)
        search_form = QFormLayout(search_box)
        search_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        search_form.setProperty("hmsResponsive", True)
        search_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient Id")
        self.patient_id.setMaximumWidth(220)
        self.patient_id.returnPressed.connect(self._search_bills)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search_bills)
        pick_btn = QPushButton("Pick Patient")
        pick_btn.clicked.connect(self._pick_patient)
        search_row.addWidget(self.patient_id)
        search_row.addWidget(search_btn)
        search_row.addWidget(pick_btn)
        search_row.addStretch(1)
        search_form.addRow("Patient Id", search_row)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self._wide(self.patient_name)
        self.patient_name.setMinimumWidth(420)
        search_form.addRow("Patient Name", self.patient_name)
        layout.addWidget(search_box)

        self.bills_table = QTableWidget(0, 8)
        self.bills_table.setHorizontalHeaderLabels(
            [
                "Bill No",
                "Bill Date",
                "Admission",
                "Doctor",
                "Ward",
                "Stay Days",
                "Net Amount",
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
        open_btn.clicked.connect(self._open_selected_bill)
        new_bill_btn = QPushButton("IPD Discharge")
        new_bill_btn.clicked.connect(lambda: self._navigate("in_patient_discharge"))
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(new_bill_btn)
        layout.addLayout(btn_row)
        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        self.detail_title = QLabel("Bill Details")
        self.detail_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        title_row.addWidget(self.detail_title)
        title_row.addStretch()
        layout.addLayout(title_row)

        read_only_hint = QLabel("Read-only view — reprint only, no changes allowed.")
        read_only_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(read_only_hint)

        header_box = QGroupBox("Bill Header")
        header_box.setProperty("hmsExpandFormFields", True)
        header_form = QFormLayout(header_box)
        header_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        header_form.setProperty("hmsResponsive", True)
        self.detail_bill_no = QLineEdit()
        self.detail_bill_no.setReadOnly(True)
        self.detail_bill_date = QLineEdit()
        self.detail_bill_date.setReadOnly(True)
        self.detail_patient = QLineEdit()
        self.detail_patient.setReadOnly(True)
        self.detail_admission = QLineEdit()
        self.detail_admission.setReadOnly(True)
        self.detail_doctor = QLineEdit()
        self.detail_doctor.setReadOnly(True)
        self.detail_ward = QLineEdit()
        self.detail_ward.setReadOnly(True)
        self.detail_stay = QLineEdit()
        self.detail_stay.setReadOnly(True)
        self.detail_discharge = QLineEdit()
        self.detail_discharge.setReadOnly(True)
        self.detail_payment = QLineEdit()
        self.detail_payment.setReadOnly(True)
        self.detail_gross = QLineEdit()
        self.detail_gross.setReadOnly(True)
        self.detail_net = QLineEdit()
        self.detail_net.setReadOnly(True)
        for field in (
            self.detail_bill_no,
            self.detail_bill_date,
            self.detail_patient,
            self.detail_admission,
            self.detail_doctor,
            self.detail_ward,
            self.detail_stay,
            self.detail_discharge,
            self.detail_payment,
            self.detail_gross,
            self.detail_net,
        ):
            self._wide(field)
        self.detail_patient.setMinimumWidth(420)
        header_form.addRow("Bill No", self.detail_bill_no)
        header_form.addRow("Bill Date", self.detail_bill_date)
        header_form.addRow("Patient", self.detail_patient)
        header_form.addRow("Admission", self.detail_admission)
        header_form.addRow("Doctor", self.detail_doctor)
        header_form.addRow("Ward", self.detail_ward)
        header_form.addRow("Stay Days", self.detail_stay)
        header_form.addRow("Discharge Date", self.detail_discharge)
        header_form.addRow("Payment", self.detail_payment)
        header_form.addRow("Gross Amount", self.detail_gross)
        header_form.addRow("Net Amount", self.detail_net)
        layout.addWidget(header_box)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Code", "Service", "Rate", "Qty", "Amount"])
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

        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back to List")
        back_btn.clicked.connect(self._show_list_page)
        preview_btn = QPushButton("Preview Bill")
        preview_btn.setStyleSheet(HEADER_BTN_STYLE)
        preview_btn.clicked.connect(self._preview_current_bill)
        print_btn = QPushButton("Print Bill")
        print_btn.setStyleSheet(HEADER_BTN_STYLE)
        print_btn.clicked.connect(self._print_current_bill)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(print_btn)
        layout.addLayout(btn_row)
        return page

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.__class__.pending_patient_no:
            self.patient_id.setText(self.__class__.pending_patient_no)
            self.__class__.pending_patient_no = None
            self._search_bills()

    def on_module_deactivated(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        self.__class__.pending_patient_no = None
        self._patient = None
        self._bill_summaries = []
        self._current_bill = None
        self.patient_id.clear()
        self.patient_name.clear()
        self.bills_table.setRowCount(0)
        self.lines_table.setRowCount(0)
        self._stack.setCurrentIndex(0)
        self.status.clear()
        self._set_status("Select a bill to view and reprint.")

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, parent=self)
        if not patient:
            return
        self._apply_patient(patient)
        self._search_bills()

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no") or "")
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))

    def _resolve_patient(self) -> dict | None:
        patient_no = self.patient_id.text().strip()
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
                self._bill_summaries = []
                self._populate_bills_table()
                QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
                return None
            self._apply_patient(items[0])
            return items[0]
        except ApiError as exc:
            QMessageBox.warning(self, "Patient", str(exc))
            return None

    def _search_bills(self) -> None:
        patient = self._resolve_patient()
        if not patient:
            return
        try:
            self._bill_summaries = self.api.list_ipd_discharges_by_patient(
                patient_no=patient.get("patient_no")
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Search Bills", str(exc))
            return
        self._populate_bills_table()
        count = len(self._bill_summaries)
        if count:
            self._set_status(f"Found {count} IPD bill(s) for {patient.get('patient_no')} — latest first.")
        else:
            self._set_status(f"No IPD bills found for {patient.get('patient_no')}.")

    def _populate_bills_table(self) -> None:
        self.bills_table.setRowCount(len(self._bill_summaries))
        for row, bill in enumerate(self._bill_summaries):
            values = [
                bill.get("bill_no") or "",
                str(bill.get("bill_date") or ""),
                bill.get("admission_no") or "—",
                bill.get("doctor_name") or "—",
                bill.get("ward_name") or "—",
                str(bill.get("stay_days") if bill.get("stay_days") is not None else "—"),
                f"{float(bill.get('net_amount') or 0):.2f}",
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
            bill = self.api.get_ipd_discharge(bill_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Open Bill", str(exc))
            return
        self._show_bill_detail(bill)

    def _show_list_page(self) -> None:
        self._stack.setCurrentIndex(0)
        self._set_status("Select a bill to view and reprint.")

    def _show_bill_detail(self, bill: dict) -> None:
        self._current_bill = bill
        bill_no = bill.get("bill_no") or ""
        self.detail_title.setText(f"Bill Details — {bill_no}")
        self.detail_bill_no.setText(bill_no)
        self.detail_bill_date.setText(str(bill.get("bill_date") or ""))
        patient_label = bill.get("patient_name") or ""
        if bill.get("patient_no"):
            patient_label = f"{bill.get('patient_no')} — {patient_label}".strip(" —")
        self.detail_patient.setText(patient_label)
        self.detail_admission.setText(bill.get("admission_no") or "—")
        self.detail_doctor.setText(bill.get("doctor_name") or "—")
        self.detail_ward.setText(bill.get("ward_name") or "—")
        stay = bill.get("stay_days")
        self.detail_stay.setText(str(stay) if stay is not None else "—")
        self.detail_discharge.setText(str(bill.get("discharge_date") or ""))
        self.detail_payment.setText(bill.get("payment_mode_name") or "—")
        self.detail_gross.setText(f"{float(bill.get('gross_amount') or 0):.2f}")
        self.detail_net.setText(f"{float(bill.get('net_amount') or 0):.2f}")

        lines = bill.get("lines") or []
        self.lines_table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            self.lines_table.setItem(row, 0, QTableWidgetItem(line.get("service_code") or ""))
            self.lines_table.setItem(row, 1, QTableWidgetItem(line.get("service_name") or ""))
            self.lines_table.setItem(row, 2, QTableWidgetItem(f"{float(line.get('rate') or 0):.2f}"))
            self.lines_table.setItem(row, 3, QTableWidgetItem(str(line.get("quantity") or 0)))
            self.lines_table.setItem(row, 4, QTableWidgetItem(f"{float(line.get('amount') or 0):.2f}"))

        self._stack.setCurrentIndex(1)
        self._set_status(f"Viewing bill {bill_no} — read only.")

    def _report_endpoint(self) -> str | None:
        if not self._current_bill:
            return None
        bill_id = self._current_bill.get("id")
        if bill_id:
            return f"/reports/ipd-bill/{bill_id}"
        bill_no = self._current_bill.get("bill_no")
        if bill_no:
            return f"/reports/ipd-bill/by-no/{bill_no}"
        return None

    def _preview_current_bill(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Preview", "No bill loaded.")
            return
        preview_report(self.api, endpoint, parent=self, title="IPD Bill Reprint", report_code="IPD_BILL")

    def _print_current_bill(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Print", "No bill loaded.")
            return
        print_report(self.api, endpoint, parent=self, report_code="IPD_BILL")
