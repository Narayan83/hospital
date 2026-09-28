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


class CancellationBillReportWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._report: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Cancellation Bill Details Report")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Lists cancelled OPD, IPD, and Pathology bills with the cancellation remarks "
            "entered at cancel time."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.bill_type_combo = QComboBox()
        self.bill_type_combo.setMinimumWidth(240)
        self.bill_type_combo.addItem("All (OPD / IPD / Pathology)", "all")
        self.bill_type_combo.addItem("OPD", "opd")
        self.bill_type_combo.addItem("IPD", "ipd")
        self.bill_type_combo.addItem("Pathology", "pathology")
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setDate(QDate.currentDate())
        form.addRow("Bill Type", self.bill_type_combo)
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

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "SL",
                "Type",
                "Date",
                "Bill No.",
                "Patient Id",
                "Patient Name",
                "Amount",
                "Cancellation Remarks",
                "Cancelled At",
                "By",
            ]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(8, 120)
        self.table.setColumnWidth(9, 110)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("Select date range, then load the report.")
        self.summary.setStyleSheet("color: #475569; font-weight: bold;")
        layout.addWidget(self.summary)

    def refresh(self) -> None:
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        bill_type = self.bill_type_combo.currentData() or "all"
        try:
            self._report = self.api.get_cancellation_bill_report(
                from_date=from_date,
                to_date=to_date,
                bill_type=bill_type,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return
        self._populate_table(self._report)
        grand_total = float(self._report.get("grand_total") or 0)
        row_count = len(self._report.get("rows") or [])
        self.summary.setText(
            f"Period: {from_date} to {to_date} — {row_count} cancelled bill(s) — "
            f"Total: {grand_total:.2f}"
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

    @staticmethod
    def _format_datetime(value: str | datetime | None) -> str:
        if not value:
            return "—"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value.strftime("%d/%m/%Y %H:%M")

    def _populate_table(self, report: dict) -> None:
        rows = report.get("rows") or []
        self.table.setRowCount(len(rows) + (1 if rows else 0))
        bold_font = QFont()
        bold_font.setBold(True)

        for row_index, row in enumerate(rows):
            values = [
                str(row.get("serial_no") or ""),
                row.get("bill_type") or "",
                self._format_date(row.get("bill_date")),
                row.get("bill_no") or "",
                row.get("patient_no") or "",
                row.get("patient_name") or "",
                f"{float(row.get('net_amount') or 0):.2f}",
                row.get("cancellation_remarks") or "",
                self._format_datetime(row.get("cancelled_at")),
                row.get("cancelled_by") or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 6):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row_index, col, item)
            self.table.resizeRowToContents(row_index)

        if not rows:
            return

        total_row = len(rows)
        total_label = QTableWidgetItem("Total....")
        total_label.setFont(bold_font)
        total_label.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.setSpan(total_row, 0, 1, 6)
        self.table.setItem(total_row, 0, total_label)
        total_amount = QTableWidgetItem(f"{float(report.get('grand_total') or 0):.2f}")
        total_amount.setFont(bold_font)
        total_amount.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.setItem(total_row, 6, total_amount)

    def _print_report(self) -> None:
        if not self._report:
            QMessageBox.information(self, "Print", "Load the report before printing.")
            return
        endpoint = self.api.cancellation_bill_report_endpoint(
            from_date=self.from_date.date().toPython().isoformat(),
            to_date=self.to_date.date().toPython().isoformat(),
            bill_type=self.bill_type_combo.currentData() or "all",
        )
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title="Cancellation Bill Details Report",
            printer_name=self.printer_combo.currentData(),
            report_code="CANCELLATION_BILL_REPORT",
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _populate_printer_combo(self.printer_combo)
