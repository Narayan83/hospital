from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
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

REPORT_CONFIG = {
    "sales_register": {
        "title": "Sales Register",
        "headers": ["Bill No", "Date", "Patient", "Items", "Gross", "Discount", "Net"],
        "needs_dates": True,
    },
    "sales_summary": {
        "title": "Sales Summary",
        "headers": ["Item Code", "Item Name", "Total Qty", "Total Amount"],
        "needs_dates": True,
    },
    "schedule_h_drug_report": {
        "title": "Schedule H Drug Report",
        "headers": ["Bill No", "Date", "Patient", "Code", "Medicine", "Schedule", "Qty", "Amount"],
        "needs_dates": True,
    },
    "consolidated_stock_report": {
        "title": "Consolidated Stock Report",
        "headers": ["Type", "Code", "Name", "Unit", "Purchased", "Sold", "Balance", "Reorder"],
        "needs_dates": False,
    },
}


class PharmacyReportsWidget(QWidget):
    def __init__(self, api: ApiClient, report_key: str):
        super().__init__()
        self.api = api
        self.report_key = report_key
        self.config = REPORT_CONFIG[report_key]
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel(self.config["title"])
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        if self.config["needs_dates"]:
            filters = QGroupBox("Date Range")
            form = QFormLayout(filters)
            self.from_date = QDateEdit()
            self.from_date.setCalendarPopup(True)
            self.from_date.setDate(QDate.currentDate().addMonths(-1))
            self.to_date = QDateEdit()
            self.to_date.setCalendarPopup(True)
            self.to_date.setDate(QDate.currentDate())
            form.addRow("From", self.from_date)
            form.addRow("To", self.to_date)
            layout.addWidget(filters)
        else:
            self.from_date = None
            self.to_date = None

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Report")
        load_btn.clicked.connect(self.refresh)
        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(self.config["headers"]))
        self.table.setHorizontalHeaderLabels(self.config["headers"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #475569;")
        layout.addWidget(self.summary)

    def refresh(self) -> None:
        try:
            if self.report_key == "sales_register":
                rows = self.api.pharmacy_sales_register(
                    self.from_date.date().toPython().isoformat(),
                    self.to_date.date().toPython().isoformat(),
                )
                self._fill_table(
                    [
                        [
                            row.get("bill_no"),
                            str(row.get("bill_date")),
                            row.get("patient_name") or "—",
                            str(row.get("item_count")),
                            f"{float(row.get('gross_amount', 0)):.2f}",
                            f"{float(row.get('discount_amount', 0)):.2f}",
                            f"{float(row.get('net_amount', 0)):.2f}",
                        ]
                        for row in rows
                    ]
                )
                self.summary.setText(f"{len(rows)} sale bill(s)")
            elif self.report_key == "sales_summary":
                rows = self.api.pharmacy_sales_summary(
                    self.from_date.date().toPython().isoformat(),
                    self.to_date.date().toPython().isoformat(),
                )
                self._fill_table(
                    [
                        [
                            row.get("item_code"),
                            row.get("item_name"),
                            str(row.get("total_qty")),
                            f"{float(row.get('total_amount', 0)):.2f}",
                        ]
                        for row in rows
                    ]
                )
                self.summary.setText(f"{len(rows)} medicine line(s)")
            elif self.report_key == "schedule_h_drug_report":
                rows = self.api.pharmacy_schedule_h_report(
                    self.from_date.date().toPython().isoformat(),
                    self.to_date.date().toPython().isoformat(),
                )
                self._fill_table(
                    [
                        [
                            row.get("bill_no"),
                            str(row.get("bill_date")),
                            row.get("patient_name") or "—",
                            row.get("item_code"),
                            row.get("item_name"),
                            row.get("schedule"),
                            str(row.get("quantity")),
                            f"{float(row.get('amount', 0)):.2f}",
                        ]
                        for row in rows
                    ]
                )
                self.summary.setText(f"{len(rows)} schedule H sale line(s)")
            elif self.report_key == "consolidated_stock_report":
                rows = self.api.pharmacy_stock_report()
                self._fill_table(
                    [
                        [
                            row.get("item_type"),
                            row.get("item_code"),
                            row.get("item_name"),
                            row.get("unit") or "—",
                            str(row.get("purchased_qty")),
                            str(row.get("sold_qty")),
                            str(row.get("balance_qty")),
                            str(row.get("reorder_level") or "—"),
                        ]
                        for row in rows
                    ]
                )
                low = sum(
                    1
                    for row in rows
                    if row.get("reorder_level") is not None
                    and row.get("balance_qty", 0) <= row.get("reorder_level", 0)
                )
                self.summary.setText(f"{len(rows)} item(s); {low} below reorder level")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _fill_table(self, rows: list[list]) -> None:
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
