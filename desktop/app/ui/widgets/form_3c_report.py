from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.print_utils import _populate_printer_combo, preview_report


class Form3CReportWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._billing_types: list[dict] = []
        self._report: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Form 3C Report")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Select billing type (OPD, IPD, Lab, etc.) and date range. "
            "Bill type is shown at the top of the report — not repeated in each row."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.billing_type_combo = QComboBox()
        self.billing_type_combo.setMinimumWidth(280)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setDate(QDate.currentDate())
        form.addRow("Billing Type *", self.billing_type_combo)
        form.addRow("From Date *", self.from_date)
        form.addRow("To Date *", self.to_date)
        layout.addWidget(filters)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Report")
        load_btn.clicked.connect(self.refresh)
        print_btn = QPushButton("Print Report")
        print_btn.clicked.connect(self._print_report)
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(280)
        _populate_printer_combo(self.printer_combo)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(QLabel("Printer:"))
        btn_row.addWidget(self.printer_combo, stretch=1)
        btn_row.addWidget(print_btn)
        layout.addLayout(btn_row)

        self.billing_type_label = QLabel("")
        self.billing_type_label.setStyleSheet("font-weight: bold; color: #1e40af;")
        layout.addWidget(self.billing_type_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "SLNO",
                "Date",
                "Bill No.",
                "Payment Mode",
                "Patient Name",
                "Service Name",
                "Total Amount",
            ]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(6, 100)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("Select billing type and date range, then load the report.")
        self.summary.setStyleSheet("color: #475569; font-weight: bold;")
        layout.addWidget(self.summary)

    def refresh(self) -> None:
        billing_type_id = self.billing_type_combo.currentData()
        if not billing_type_id:
            QMessageBox.warning(self, "Billing Type", "Select a billing type first.")
            return
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        try:
            self._report = self.api.get_form_3c_report(
                billing_type_id=billing_type_id,
                from_date=from_date,
                to_date=to_date,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return
        self._populate_table(self._report)
        billing_type_name = self._report.get("billing_type_name") or ""
        grand_total = float(self._report.get("grand_total") or 0)
        row_count = len(self._report.get("rows") or [])
        self.billing_type_label.setText(f"Billing Type: {billing_type_name}")
        self.summary.setText(
            f"Period: {from_date} to {to_date} — {row_count} row(s) — Grand Total: {grand_total:.2f}"
        )

    @staticmethod
    def _format_date(value: str | date | None) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value).date()
            except ValueError:
                return value
        return value.strftime("%d/%m/%Y")

    def _populate_table(self, report: dict) -> None:
        rows = report.get("rows") or []
        self.table.setRowCount(len(rows) + 1)
        bold_font = QFont()
        bold_font.setBold(True)

        for row_index, row in enumerate(rows):
            values = [
                str(row.get("serial_no") or ""),
                self._format_date(row.get("bill_date")),
                row.get("bill_no") or "",
                row.get("payment_mode") or "",
                row.get("patient_name") or "",
                row.get("service_name") or "",
                f"{float(row.get('total_amount') or 0):.2f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, col, item)

        total_row = len(rows)
        total_label = QTableWidgetItem("Total....")
        total_label.setFont(bold_font)
        total_label.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setSpan(total_row, 0, 1, 6)
        self.table.setItem(total_row, 0, total_label)
        total_amount = QTableWidgetItem(f"{float(report.get('grand_total') or 0):.2f}")
        total_amount.setFont(bold_font)
        total_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(total_row, 6, total_amount)

    def _print_report(self) -> None:
        billing_type_id = self.billing_type_combo.currentData()
        if not billing_type_id:
            QMessageBox.warning(self, "Print", "Select a billing type first.")
            return
        if not self._report:
            QMessageBox.information(self, "Print", "Load the report before printing.")
            return
        endpoint = self.api.form_3c_report_endpoint(
            billing_type_id=billing_type_id,
            from_date=self.from_date.date().toPython().isoformat(),
            to_date=self.to_date.date().toPython().isoformat(),
        )
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title="Form 3C Report",
            printer_name=self.printer_combo.currentData(),
            report_code="FORM_3C_REPORT",
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _populate_printer_combo(self.printer_combo)
        self._load_billing_types()

    def _load_billing_types(self) -> None:
        current_id = self.billing_type_combo.currentData()
        try:
            self._billing_types = self.api.list_billing_types()
        except ApiError as exc:
            QMessageBox.warning(self, "Billing Types", str(exc))
            return
        self.billing_type_combo.clear()
        self.billing_type_combo.addItem("— Select Billing Type —", None)
        for item in sorted(self._billing_types, key=lambda row: row.get("sort_order", 0)):
            if not item.get("is_active", True):
                continue
            label = f"{item.get('name', '')} ({item.get('code', '')})"
            self.billing_type_combo.addItem(label, item.get("id"))
        if current_id:
            idx = self.billing_type_combo.findData(current_id)
            if idx >= 0:
                self.billing_type_combo.setCurrentIndex(idx)
